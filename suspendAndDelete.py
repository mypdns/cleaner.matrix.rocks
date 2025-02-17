import requests
import argparse
import sys
import os
import configparser
import logging
import getpass

# Default values
DEFAULT_URL = "https://matrix.rocks/api"
VERSION = "0.1.0b35"  # Bumped version

# Configure logging
script_dir = os.path.dirname(os.path.abspath(__file__))
log_folder = os.path.join(script_dir, "logs")
if not os.path.exists(log_folder):
    os.mkdir(log_folder)


def configure_logging(userId, log_level):
    log_path = os.path.join(log_folder, f"{userId}.log")
    logging.basicConfig(
        filename=log_path,
        level=log_level,
        format="%(asctime)s %(levelname)s:%(message)s",
    )


def get_api_token():
    logging.debug("Fetching API token")
    if "GITHUB_ACTIONS" in os.environ:
        logging.debug("Running in GitHub Actions")
        return os.environ.get("MATRIX_ROCKS_API_TOKEN", "")

    config_path = os.path.join(script_dir, "config.user.ini")
    config = configparser.ConfigParser()
    config.read(config_path)

    if not config.has_section("API"):
        config.add_section("API")

    if "MATRIX_ROCKS_API_TOKEN" not in config["API"]:
        logging.error(f"Missing MATRIX_ROCKS_API_TOKEN in {config_path}")
        api_token = getpass.getpass("Enter your MATRIX_ROCKS_API_TOKEN: ")
        config["API"]["MATRIX_ROCKS_API_TOKEN"] = api_token
        with open(config_path, "w") as config_file:
            config.write(config_file)

    return config.get("API", "MATRIX_ROCKS_API_TOKEN", fallback="")


def perform_request(endpoint, api_token, userId, request_type="GET", data=None):
    headers = {"Authorization": f"Bearer {api_token}"}
    if request_type == "GET":
        logging.debug(
            f'GET request to {endpoint} with params {{"userId": {userId}}}'
        )
        response = requests.get(
            endpoint, params={"userId": userId}, headers=headers
        )
    else:
        logging.debug(f"POST request to {endpoint} with data {data}")
        response = requests.post(endpoint, json=data, headers=headers)

    logging.debug(f"Response: {response.status_code} {response.text}")
    if response.status_code != 200:
        logging.error(f"Error: {response.status_code} {response.text}")
        return False
    return response


def check_user_suspended(api_url, api_token, userId):
    logging.debug(f"Checking if user {userId} is suspended")
    endpoint = f"{api_url}/admin/check-suspended"
    response = perform_request(endpoint, api_token, userId)
    if not response:
        return False
    return response.json().get("isSuspended", False)


def suspend_user(api_url, api_token, userId, reason=None):
    logging.debug(f"Suspending user {userId}")
    endpoint = f"{api_url}/admin/suspend-user"
    data = {"userId": userId}
    if reason:
        data["reason"] = reason
    response = perform_request(
        endpoint, api_token, userId, request_type="POST", data=data
    )
    return response


def delete_user_posts(api_url, api_token, userId):
    logging.debug(f"Deleting posts for user {userId}")
    endpoint = f"{api_url}/admin/delete-all-posts-of-a-user"
    response = perform_request(
        endpoint,
        api_token,
        userId,
        request_type="POST",
        data={"userId": userId},
    )
    return response


def delete_user_files(api_url, api_token, userId):
    logging.debug(f"Deleting files for user {userId}")
    endpoint = f"{api_url}/admin/delete-all-files-of-a-user"
    response = perform_request(
        endpoint,
        api_token,
        userId,
        request_type="POST",
        data={"userId": userId},
    )
    return response


def delete_user_notes(api_url, api_token, userId):
    logging.debug(f"Deleting notes for user {userId}")
    get_notes_endpoint = f"{api_url}/users/notes"
    headers = {"Authorization": f"Bearer {api_token}"}
    logging.debug(
        f'GET request to {get_notes_endpoint} with params {{"userId": {userId}}}'
    )
    response = requests.get(
        get_notes_endpoint, params={"userId": userId}, headers=headers
    )
    logging.debug(f"Response: {response.status_code} {response.text}")
    if response.status_code != 200:
        logging.error(
            f"Error retrieving user notes: {response.status_code} {response.text}"
        )
        return False

    notes = response.json()
    delete_note_success = 0
    delete_note_failures = 0

    for note in notes:
        delete_note_endpoint = f"{api_url}/notes/delete"
        response = perform_request(
            delete_note_endpoint,
            api_token,
            note["id"],
            request_type="POST",
            data={"note_id": note["id"]},
        )
        if response:
            delete_note_success += 1
        else:
            delete_note_failures += 1

    logging.info(
        f"Notes deleted: {delete_note_success}, not deleted: {delete_note_failures}"
    )
    return delete_note_failures == 0


def main():
    parser = argparse.ArgumentParser(
        description="Suspend and delete: Suspend user account and delete their posts, files, and notes"
    )
    parser.add_argument("user", nargs="?", help="User ID to be suspended")
    parser.add_argument(
        "-u", "--user", help="User ID to be suspended", dest="user"
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL, help="Base URL for the API"
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument(
        "--API_token", help="Provide a different API token", type=str
    )
    parser.add_argument(
        "--fr", help="Suspend a remote system account", type=str
    )
    parser.add_argument(
        "--reason", help="Provide a reason for suspension", type=str
    )
    parser.add_argument(
        "--log_level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    args = parser.parse_args()

    api_url = args.url
    api_token = args.API_token if args.API_token else get_api_token()
    userId = args.user or args.user
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    configure_logging(userId, log_level)

    if not api_token:
        logging.error("API token is missing")
        sys.exit(1)

    if not check_user_suspended(api_url, api_token, userId):
        if suspend_user(api_url, api_token, userId, reason=args.reason):
            logging.info(f"Successfully suspended user {userId}")
        else:
            logging.error(f"Failed to suspend user {userId}")
    else:
        logging.info(f"User {userId} is already suspended")

    if delete_user_posts(api_url, api_token, userId):
        logging.info(f"Successfully deleted posts for user {userId}")
    else:
        logging.error(f"Failed to delete posts for user {userId}")

    if delete_user_files(api_url, api_token, userId):
        logging.info(f"Successfully deleted files for user {userId}")
    else:
        logging.error(f"Failed to delete files for user {userId}")

    if delete_user_notes(api_url, api_token, userId):
        logging.info(f"Successfully deleted notes for user {userId}")
    else:
        logging.error(f"Failed to delete notes for user {userId}")


if __name__ == "__main__":
    main()
