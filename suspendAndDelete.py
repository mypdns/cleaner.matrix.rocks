import requests
import argparse
import sys
import os
import configparser
import logging
import getpass

# Default values
DEFAULT_URL = "https://matrix.rocks/api"
VERSION = "0.1.0b11"  # PEP 404 compliant versioning

# Configure logging
script_dir = os.path.dirname(os.path.abspath(__file__))
log_path = os.path.join(script_dir, "suspendAndDelete.log")
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s:%(message)s",
)


def get_api_token():
    logging.debug("Fetching API token")
    # Check if running in GitHub Actions
    if "GITHUB_ACTIONS" in os.environ:
        logging.debug("Running in GitHub Actions")
        return os.environ.get("MATRIX_ROCKS_API_TOKEN", "")

    # Read API token from the local configuration file within the repo path
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


def check_user_suspended(api_url, api_token, user_id):
    logging.debug(f"Checking if user {user_id} is suspended")
    check_suspended_endpoint = f"{api_url}/admin/check-suspended"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(
        check_suspended_endpoint, params={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        logging.error(
            f"Error checking user suspension status: {response.status_code} {response.text}"
        )
        return False
    return response.json().get("isSuspended", False)


def suspend_user(api_url, api_token, user_id):
    logging.debug(f"Suspending user {user_id}")
    suspend_endpoint = f"{api_url}/admin/suspend-user"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.post(
        suspend_endpoint, json={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        logging.error(
            f"Error suspending user: {response.status_code} {response.text}"
        )
    return response.status_code == 200


def delete_user_posts(api_url, api_token, user_id):
    logging.debug(f"Deleting posts for user {user_id}")
    delete_posts_endpoint = f"{api_url}/admin/delete-all-files-of-a-user"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.post(
        delete_posts_endpoint, json={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        logging.error(
            f"Error deleting user posts: {response.status_code} {response.text}"
        )
    return response.status_code == 200


def delete_user_files(api_url, api_token, user_id):
    logging.debug(f"Deleting files for user {user_id}")
    delete_files_endpoint = f"{api_url}/admin/delete-all-files-of-a-user"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.post(
        delete_files_endpoint, json={"userId": user_id}, headers=headers
    )
    if response.status_code != 200:
        logging.error(
            f"Error deleting user files: {response.status_code} {response.text}"
        )
    return response.status_code == 200


def delete_user_notes(api_url, api_token, user_id):
    logging.debug(f"Deleting notes for user {user_id}")
    get_notes_endpoint = f"{api_url}/users/notes"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(
        get_notes_endpoint, params={"userId": user_id}, headers=headers
    )
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
        response = requests.post(
            delete_note_endpoint, json={"noteId": note["id"]}, headers=headers
        )
        if response.status_code == 200:
            delete_note_success += 1
        else:
            logging.error(
                f"Error deleting note {note['id']}: {response.status_code} {response.text}"
            )
            delete_note_failures += 1

    logging.info(
        f"Notes deleted: {delete_note_success}, not deleted: {delete_note_failures}"
    )
    return delete_note_failures == 0


def main():
    parser = argparse.ArgumentParser(
        description="MK-Cleaner: Suspend user account and delete their posts, files, and notes"
    )
    parser.add_argument("user", help="User ID to be suspended")
    parser.add_argument(
        "--url", default=DEFAULT_URL, help="Base URL for the API"
    )
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()

    api_url = args.url
    api_token = get_api_token()
    user_id = args.user

    if not api_token:
        logging.error("API token is missing")
        sys.exit(1)

    if not check_user_suspended(api_url, api_token, user_id):
        if suspend_user(api_url, api_token, user_id):
            logging.info(f"Successfully suspended user {user_id}")
        else:
            logging.error(f"Failed to suspend user {user_id}")
    else:
        logging.info(f"User {user_id} is already suspended")

    if delete_user_posts(api_url, api_token, user_id):
        logging.info(f"Successfully deleted posts for user {user_id}")
    else:
        logging.error(f"Failed to delete posts for user {user_id}")

    if delete_user_files(api_url, api_token, user_id):
        logging.info(f"Successfully deleted files for user {user_id}")
    else:
        logging.error(f"Failed to delete files for user {user_id}")

    if delete_user_notes(api_url, api_token, user_id):
        logging.info(f"Successfully deleted notes for user {user_id}")
    else:
        logging.error(f"Failed to delete notes for user {user_id}")


if __name__ == "__main__":
    main()
