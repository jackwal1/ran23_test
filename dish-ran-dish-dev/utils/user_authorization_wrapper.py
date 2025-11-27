import httpx
import os
import logging
import traceback
from fastapi import HTTPException, status
import utils.constants as constant

# Configure logging
log_level = getattr(logging, constant.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")


async def validate_email_address(user_email: str, auth_token: str) -> dict:
    """
    Makes an asynchronous GET request to the URL from environment variable with user email and auth token.

    Args:
        user_email (str): User email address.
        auth_token (str): Authentication token.

    Returns:
        dict: The response JSON if successful, else an error message.
    """
    url = constant.validate_email_api_endpoint
    headers = {"Content-Type": "application/json"}
    url = f"{url}?email_address={user_email}&token={auth_token}"

    logger.info(f"Transaction initiated for user: {user_email}")
    logger.info(f"Final URL : {url}")

    async with httpx.AsyncClient() as client:
        try:
            logger.info("Sending POST request...")
            response = await client.post(url, headers=headers, timeout=10)

            logger.info("Response received, checking status...")
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx, 5xx)

            response_json = response.json()
            logger.info(f"Response JSON: {response_json}")

            logger.info("Request successful, returning response JSON.")
            return {"status": "success", "message": "Request successful", "data": response_json}

        except httpx.TimeoutException as e:
            logger.error(f"Request timed out for {user_email}: {str(e)}", exc_info=True)
            return {"status": "fail", "message": "Request timed out", "data": None}

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {user_email}: {str(e)} - Response: {e.response.text}", exc_info=True)
            return {"status": "fail", "message": f"HTTP error: {e.response.status_code}", "data": None}

        except httpx.RequestError as e:
            logger.error(f"Network error for {user_email}: {str(e)}", exc_info=True)
            return {"status": "fail", "message": "Network error", "data": None}

        except Exception as e:
            logger.error(f"Unexpected error for {user_email}: {str(e)}", exc_info=True)
            return {"status": "fail", "message": "An unexpected error occurred", "data": None}


async def get_user_token(username: str, auth_token: str) -> dict:
    """
    Makes an asynchronous POST request to retrieve a user token based on the username.

    Args:
        username (str): The email address (username) for which the token is being requested.
        auth_token(str): optional

    Returns:
        dict: The response JSON if successful, else an error message.
    """
    url = constant.user_token_generate_api_endpoint
    #headers = {"Content-Type": "application/json"}

    username = username.split("@")[0]
    logger.info(f"Transaction initiated for user: {username}")

    data = {"username": username}

    logger.info(f"Preparing request to {url} with data: {data}")

    async with httpx.AsyncClient(verify=False) as client:  # Set verify=False here
        try:
            logger.info("Sending POST request...")
            response = await client.post(url, data=data, timeout=30)

            logger.info("Response received, checking status...")
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx, 5xx)

            response_json = response.json()
            logger.info(f"Response JSON: {response_json}")

            logger.info("Request successful, returning response JSON.")
            return {"status": "success", "message": "Request successful", "data": response_json}

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}", exc_info=True)
            traceback.print_exc()
            return {"status": "fail", "message": f"Request failed: {e}", "data": None}

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}", exc_info=True)
            traceback.print_exc()
            return {"status": "fail", "message": f"HTTP error occurred: {e}", "data": None}

        except httpx.TimeoutException as e:
            logger.error(f"Request timed out: {e}", exc_info=True)
            traceback.print_exc()
            return {"status": "fail", "message": f"Request timed out: {e}", "data": None}

        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            traceback.print_exc()
            return {"status": "fail", "message": f"An unexpected error occurred: {e}", "data": None}
