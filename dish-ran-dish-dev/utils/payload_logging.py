import logging
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson_openscale import APIClient
from ibm_watson_openscale.data_sets import DataSetTypes, TargetTypes
import requests
from typing import Dict, Any, Optional
import utils.constants as constant
from utils import constants as CONST

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

# Global variable for WOS client
wos_client: Optional[APIClient] = None

# Initialize WOS client at application startup
try:
    authenticator = IAMAuthenticator(apikey=constant.WOS_APIKEY)
    wos_client = APIClient(
        authenticator=authenticator,
        service_instance_id=constant.WOS_SERVICE_INSTANCE_ID,
        service_url=constant.WOS_URL
    )
    logger.info("WOS client initialized successfully at application startup.")
except Exception as e:
    logger.error(f"Failed to initialize WOS client at startup: {e}", exc_info=True)

# Utility to get dataset ID
def get_payload_logging_dataset_id(wos_client: APIClient, subscription_id: str) -> str:
    datasets = wos_client.data_sets.list(
        type=DataSetTypes.PAYLOAD_LOGGING,
        target_target_id=subscription_id,
        target_target_type=TargetTypes.SUBSCRIPTION
    ).result.data_sets

    if datasets:
        return datasets[0].metadata.id
    raise ValueError(f"No payload logging dataset found for Subscription ID: {subscription_id}")

# Utility to store payload record for summarization
async def store_summarization_payload_record(
    request_data,
    response_data,
    input_token_count,
    generated_token_count,
    response_time,
    subscription_id
):
    try:
        logger.info(f"Starting to store payload record for Subscription ID: {subscription_id}")

        request = {"parameters": {"template_variables": {"input": request_data}}}

        # Prepare response
        response = {
            "results": [
                {
                    "generated_text": response_data,
                    "input_token_count": input_token_count,
                    "generated_token_count": generated_token_count
                }
            ]
        }

        dataset_id: str = get_payload_logging_dataset_id(wos_client, subscription_id)

        # Prepare payload record
        payload_record = {
            'request': request,
            'response': response,
            'response_time': response_time
        }

        response = wos_client.data_sets.store_records(data_set_id=dataset_id, request_body=[payload_record])
        logger.info(f"Payload record stored successfully for Subscription ID: {subscription_id}")

    except Exception as e:
        logger.error(
        f"Unexpected error occurred while storing payload record for Subscription Id: {subscription_id}. Error: {str(e)}",
        exc_info=True  # This logs the full traceback
    )

# Utility to store payload record for RAG
async def store_rag_payload_record(
    request_data,
    response_data,
    input_token_count,
    generated_token_count,
    response_time,
    subscription_id,
    question
):
    try:
        logger.info(f"Starting to store RAG payload record for Subscription ID: {subscription_id}")

        # Prepare request dynamically
        request: Dict[str, Any] = {
            "parameters": {
                "template_variables": {
                    "question": question
                }
            }
        }

        # Dynamically add contexts using the keys from request_data
        for key, value in request_data.items():
            if value:  # Only add non-empty values
                request["parameters"]["template_variables"][key] = value

        # Prepare response
        response: Dict[str, Any] = {
            "results": [
                {
                    "generated_text": response_data,
                    "input_token_count": input_token_count,
                    "generated_token_count": generated_token_count
                }
            ]
        }

        dataset_id: str = get_payload_logging_dataset_id(wos_client, subscription_id)

        # Prepare payload record
        payload_record = {
            'request': request,
            'response': response,
            'response_time': response_time
        }
        wos_client.data_sets.store_records(data_set_id=dataset_id, request_body=[payload_record])
        logger.info(f"RAG payload record stored successfully for Subscription ID: {subscription_id}")

    except Exception as e:
        logger.error(
        f"Unexpected error occurred while storing RAG payload record for Subscription Id: {subscription_id}. Error: {str(e)}",
        exc_info=True  # This logs the full traceback
    )

# Function to generate access token
def generate_access_token() -> str:
    headers: Dict[str, str] = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    data: Dict[str, str] = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": constant.WATSONX_API_KEY,
        "response_type": "cloud_iam"
    }
    response = requests.post(constant.IAM_URL + "/identity/token", data=data, headers=headers)
    response.raise_for_status()
    return response.json()["access_token"]

def get_token_count(text: str, model_id: str) -> int:
    """
    Get the token count for a given text using the Watsonx API.
    """
    access_token: str = generate_access_token()  # Generate the access token
    url: str = f"{constant.WATSONX_URL}/ml/v1/text/tokenization?version=2023-05-02"
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload: Dict[str, Any] = {
        "model_id": model_id,
        "input": text,
        "parameters": {
            "return_tokens": True
        },
        "project_id": constant.WATSONX_PROJECT_ID
    }

    response = requests.post(url, headers=headers, json=payload)
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response = response.json()["result"]["token_count"]
    except Exception as e:
        logger.error(f"Request failed: {e}, Response: {response.text if response else 'No response'}")
        response = 0 
    return response