import os
import logging
from dotenv import load_dotenv
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from utils import constants as CONST

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")


try:
    # Fetch environment variables
    WATSONX_URL = os.environ["WATSONX_URL"]
    WATSONX_APIKEY = os.environ["WATSONX_API_KEY"]
    WATSONX_PROJECT_ID = os.environ["WATSONX_PROJECT_ID"]
    WATSONX_MODEL_ID_MISTRAL_MEDIUM = os.environ["WATSONX_MODEL_ID_MISTRAL_MEDIUM"]

except Exception as e:
    #print(e)
    print("Loading Environmment Variables from local .env file")
    load_dotenv()
    WATSONX_URL = os.environ["WATSONX_URL"]
    WATSONX_APIKEY = os.environ["WATSONX_API_KEY"]
    WATSONX_PROJECT_ID = os.environ["WATSONX_PROJECT_ID"]
    WATSONX_MODEL_ID_MISTRAL_MEDIUM = os.environ["WATSONX_MODEL_ID_MISTRAL_MEDIUM"]

watsonx_endpoint = ModelInference(
    model_id=WATSONX_MODEL_ID_MISTRAL_MEDIUM,
    credentials=Credentials(
        url=WATSONX_URL,
        api_key=WATSONX_APIKEY,),
    project_id=WATSONX_PROJECT_ID,
)

def get_tokens(str):
    tokenized_response = watsonx_endpoint.tokenize(prompt=str, return_tokens=False)
    return tokenized_response.get('result').get('token_count')