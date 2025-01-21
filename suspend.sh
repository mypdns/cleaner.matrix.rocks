#!/bin/bash

# Default values
DEFAULT_URL="https://matrix.rocks/api"
VERSION="0.1.0b36"

# Configure logging
LOG_DIR="./logs"
mkdir -p "$LOG_DIR"

configure_logging() {
    local userId=$1
    local log_level=$2
    LOG_FILE="$LOG_DIR/${userId}.log"
}

get_api_token() {
    if [ -n "$GITHUB_ACTIONS" ]; then
        echo "$MATRIX_ROCKS_API_TOKEN"
    else
        CONFIG_FILE="./config.user.ini"
        if [ ! -f "$CONFIG_FILE" ]; then
            touch "$CONFIG_FILE"
        fi
        source "$CONFIG_FILE"
        if [ -z "$MATRIX_ROCKS_API_TOKEN" ]; then
            read -sp "Enter your MATRIX_ROCKS_API_TOKEN: " api_token
            echo "MATRIX_ROCKS_API_TOKEN=$api_token" >>"$CONFIG_FILE"
        else
            echo "$MATRIX_ROCKS_API_TOKEN"
        fi
    fi
}

perform_request() {
    local endpoint=$1
    local api_token=$2
    local userId=$3
    local request_type=$4
    local data=$5

    headers=("Authorization: Bearer $api_token")

    if [ "$request_type" == "GET" ]; then
        echo "GET request to $endpoint with params {\"userId\": $userId}"
        response=$(curl -s -w "%{http_code}" -o response.txt -G "$endpoint" --data-urlencode "userId=$userId" -H "Authorization: Bearer $api_token")
    else
        echo "POST request to $endpoint with data $data"
        response=$(curl -s -w "%{http_code}" -o response.txt -X POST "$endpoint" -H "Content-Type: application/json" -H "Authorization: Bearer $api_token" -d "$data")
    fi

    http_code=$(tail -c 3 response.txt)
    response_body=$(head -c -3 response.txt)
    echo "Response: $http_code $response_body"

    if [ "$http_code" -ne 200 ]; then
        echo "Error: $http_code $response_body" >>"$LOG_FILE"
        return 1
    fi
    echo "$response_body"
}

check_user_suspended() {
    local api_url=$1
    local api_token=$2
    local userId=$3

    echo "Checking if user $userId is suspended"
    local endpoint="$api_url/admin/check-suspended"
    response=$(perform_request "$endpoint" "$api_token" "$userId" "GET")
    if [ -z "$response" ]; then
        return 1
    fi
    echo "$response" | jq -r '.isSuspended'
}

suspend_user() {
    local api_url=$1
    local api_token=$2
    local userId=$3
    local reason=$4

    echo "Suspending user $userId"
    local endpoint="$api_url/admin/suspend-user"
    local data="{\"userId\": \"$userId\", \"reason\": \"$reason\"}"
    perform_request "$endpoint" "$api_token" "$userId" "POST" "$data"
}

delete_user_posts() {
    local api_url=$1
    local api_token=$2
    local userId=$3

    echo "Deleting posts for user $userId"
    local endpoint="$api_url/admin/delete-all-posts-of-a-user"
    local data="{\"userId\": \"$userId\"}"
    perform_request "$endpoint" "$api_token" "$userId" "POST" "$data"
}

delete_user_files() {
    local api_url=$1
    local api_token=$2
    local userId=$3

    echo "Deleting files for user $userId"
    local endpoint="$api_url/admin/delete-all-files-of-a-user"
    local data="{\"userId\": \"$userId\"}"
    perform_request "$endpoint" "$api_token" "$userId" "POST" "$data"
}

delete_user_notes() {
    local api_url=$1
    local api_token=$2
    local userId=$3

    echo "Deleting notes for user $userId"
    local get_notes_endpoint="$api_url/users/notes"
    echo "GET request to $get_notes_endpoint with params {\"userId\": $userId}"
    response=$(curl -s -G "$get_notes_endpoint" --data-urlencode "userId=$userId" -H "Authorization: Bearer $api_token")
    echo "Response: $response"

    notes=$(echo "$response" | jq -c '.[]')
    delete_note_success=0
    delete_note_failures=0

    for note in $notes; do
        note_id=$(echo "$note" | jq -r '.id')
        delete_note_endpoint="$api_url/notes/delete"
        local data="{\"note_id\": \"$note_id\"}"
        response=$(perform_request "$delete_note_endpoint" "$api_token" "$note_id" "POST" "$data")
        if [ $? -eq 0 ]; then
            ((delete_note_success++))
        else
            ((delete_note_failures++))
        fi
    done

    echo "Notes deleted: $delete_note_success, not deleted: $delete_note_failures"
    return $delete_note_failures
}

main() {
    while [[ "$1" =~ ^- && ! "$1" == "--" ]]; do
        case $1 in
        -u | --user)
            shift
            user="$1"
            ;;
        --url)
            shift
            api_url="$1"
            ;;
        --version)
            echo "$VERSION"
            exit 0
            ;;
        --API_token)
            shift
            api_token="$1"
            ;;
        --fr)
            shift
            fr="$1"
            ;;
        --reason)
            shift
            reason="$1"
            ;;
        --log_level)
            shift
            log_level="$1"
            ;;
        esac
        shift
    done
    if [[ "$1" == '--' ]]; then shift; fi
    user="${user:-$1}"

    api_url="${api_url:-$DEFAULT_URL}"
    api_token="${api_token:-$(get_api_token)}"
    log_level="${log_level:-INFO}"
    configure_logging "$user" "$log_level"

    if [ -z "$api_token" ]; then
        echo "API token is missing" >>"$LOG_FILE"
        exit 1
    fi

    suspended=$(check_user_suspended "$api_url" "$api_token" "$user")
    if [ "$suspended" != "true" ]; then
        suspend_user "$api_url" "$api_token" "$user" "$reason"
        if [ $? -eq 0 ]; then
            echo "Successfully suspended user $user"
        else
            echo "Failed to suspend user $user" >>"$LOG_FILE"
        fi
    else
        echo "User $user is already suspended"
    fi

    delete_user_posts "$api_url" "$api_token" "$user"
    delete_user_files "$api_url" "$api_token" "$user"
    delete_user_notes "$api_url" "$api_token" "$user"
}

main "$@"
