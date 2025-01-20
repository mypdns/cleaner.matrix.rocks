import requests
import argparse
import sys
import os
import configparser

# Default values
DEFAULT_URL = "https://matrix.rocks/api"
VERSION = "0.1.0b2"  # PEP 404 compliant versioning

def get_api_token():
    # Check if running in GitHub Actions
    if 'GITHUB_ACTIONS' in os.environ:
        return os.environ.get('MATRIX_ROCKS_API_TOKEN', '')

    # Read API token from the configuration file
    config_path = os.path.expanduser('~/.config/myPrivacyDNS/config.user.ini')
    config = configparser.ConfigParser()
    config.read(config_path)

    return config.get('DEFAULT', 'MATRIX_ROCKS_API_TOKEN', fallback='')

def check_user_suspended(api_url, api_token, user_id):
    check_suspended_endpoint = f"{api_url}/admin/check-suspended"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(
        check_suspended_endpoint, params={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        print(
            f"Error checking user suspension status: {response.status_code} {response.text}",
            file=sys.stderr,
        )
        return False
    return response.json().get("isSuspended", False)

def suspend_user(api_url, api_token, user_id):
    suspend_endpoint = f"{api_url}/admin/suspend-user"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.post(
        suspend_endpoint, json={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        print(
            f"Error suspending user: {response.status_code} {response.text}",
            file=sys.stderr,
        )
    return response.status_code == 200

def delete_user_posts(api_url, api_token, user_id):
    delete_posts_endpoint = f"{api_url}/admin/delete-all-files-of-a-user"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.post(
        delete_posts_endpoint, json={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        print(
            f"Error deleting user posts: {response.status_code} {response.text}",
            file=sys.stderr,
        )
    return response.status_code == 200

def delete_user_files(api_url, api_token, user_id):
    delete_files_endpoint = f"{api_url}/admin/delete-all-files-of-a-user"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.post(
        delete_files_endpoint, json={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        print(
            f"Error deleting user files: {response.status_code} {response.text}",
            file=sys.stderr,
        )
    return response.status_code == 200

def delete_user_notes(api_url, api_token, user_id):
    get_notes_endpoint = f"{api_url}/users/notes"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(
        get_notes_endpoint, params={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        print(
            f"Error retrieving user notes: {response.status_code} {response.text}",
            file=sys.stderr,
        )
        return False

    notes = response.json()
    delete_note_success = 0
    delete_note_failures = 0

    for note in notes:
        delete_note_endpoint = f"{api_url}/notes/delete"
        response = requests.post(
            delete_note_endpoint, json={"noteId": note["id"]}, headers=headers
        )
        if response.status_code == 200:
            delete_note_success += 1
        else:
            print(
                f"Error deleting note {note['id']}: {response.status_code} {response.text}",
                file=sys.stderr,
            )
            delete_note_failures += 1

    print(f"Notes deleted: {delete_note_success}, not deleted: {delete_note_failures}")
    return delete_note_failures == 0

def main():
    parser = argparse.ArgumentParser(
        description="MK-Cleaner: Suspend user account and delete their posts, files, and notes"
    )
    parser.add_argument("user", help="User ID to be suspended")
    parser.add_argument("--url", default=DEFAULT_URL, help="Base URL for the API")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()

    api_url = args.url
    api_token = get_api_token()
    user_id = args.user

    if not api_token:
        print("API token is missing", file=sys.stderr)
        sys.exit(1)

    if not check_user_suspended(api_url, api_token, user_id):
        if suspend_user(api_url, api_token, user_id):
            print(f"Successfully suspended user {user_id}")
        else:
            print(f"Failed to suspend user {user_id}", file=sys.stderr)
    else:
        print(f"User {user_id} is already suspended")

    if delete_user_posts(api_url, api_token, user_id):
        print(f"Successfully deleted posts for user {user_id}")
    else:
        print(f"Failed to delete posts for user {user_id}", file=sys.stderr)

    if delete_user_files(api_url, api_token, user_id):
        print(f"Successfully deleted files for user {user_id}")
    else:
        print(f"Failed to delete files for user {user_id}", file=sys.stderr)

    if delete_user_notes(api_url, api_token, user_id):
        print(f"Successfully deleted notes for user {user_id}")
    else:
        print(f"Failed to delete notes for user {user_id}", file=sys.stderr)

if __name__ == "__main__":
    main()