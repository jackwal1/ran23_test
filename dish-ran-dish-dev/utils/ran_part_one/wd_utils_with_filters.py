import logging
import traceback
import os
from dotenv import load_dotenv
import httpx
from ibm_cloud_sdk_core.api_exception import ApiException
from utils import constants as CONST


# Setup the logging configuration
log_level = getattr(logging,CONST.LOG_LEVEL )
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(filename)s - Line: %(lineno)d - %(message)s"
)
logger = logging.getLogger()
try:
    # STEP-1: Read the env variables
    WD_BEARER_TOKEN = os.environ["WD_BEARER_TOKEN"]
    WD_VERSION = os.environ["WD_VERSION"]
    WD_URL = os.environ["WD_URL"]
    WD_RAN_PROJECT_ID = os.environ["WD_RAN_PROJECT_ID"]
    WD_PASSAGE_CHARACTERS_LIMIT = int(os.environ["WD_PASSAGE_CHARACTERS_LIMIT"])
except Exception as e:
    print(e)
    print("Loading Environmment Variables from local .env file")
    load_dotenv()
    WD_BEARER_TOKEN = os.environ["WD_BEARER_TOKEN"]
    WD_VERSION = os.environ["WD_VERSION"]
    WD_URL = os.environ["WD_URL"]
    WD_RAN_PROJECT_ID = os.environ["WD_RAN_PROJECT_ID"]
    WD_PASSAGE_CHARACTERS_LIMIT = int(os.environ["WD_PASSAGE_CHARACTERS_LIMIT"])

WD_URL_QUERY = f"{WD_URL}/v2/projects/{WD_RAN_PROJECT_ID}/query?version={WD_VERSION}"

# Step 3: Query entities after processing is complete
async def wd_query_entities(user_query, filter_params=None):
    try:
        logger.info(f'ran-wd_query_entities :: START')
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {WD_BEARER_TOKEN}",
        }
        payload = {
            "count": 3,
            "return": ["title", "metadata"],
            "passages": {
                "enabled": True,
                "characters": WD_PASSAGE_CHARACTERS_LIMIT,
                "per_document": True,
                "find_answers": True,
                "fields": ["text"],
            },
            "natural_language_query": user_query,
            "table_results": {"enabled": False},
        }
        
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(WD_URL_QUERY, headers=headers, json=payload)

        if response.status_code == 200:
            logger.info(f'ran-wd_query_entities :: END')
            return response.json()
        else:
            logger.info(f'Error occurred, please check the server: {response.status_code}, {response.text}')
            logger.info(f'ran-wd_query_entities :: END')
            return {}
    except Exception as e:
        logger.error(f"Exception in wd_query_entities: {str(e)}")
        print(traceback.format_exc())
        return {}
    
async def wd_query_format_response(data):
    try:
        # Preprocess the results
        logger.info(f'ran-wd_query_format_response :: START')
        # data_json_string=json.dumps(watsonx_output)
        # data = json.loads(data_json_string)
        # with open('output_1.json', 'w') as json_file:
        #     json.dump(data, json_file, indent=4)
        result_dict = {
                "s3_url": [
                    doc.get('metadata', {}).get('s3_url', 'NA') for doc in data['results']
                ],
                "confidence_score": [doc.get('result_metadata', {}).get('confidence', 0) for doc in data['results']],
                "passages" : ' '.join([
                    ' '.join([
                        s.get('passage_text', '')
                        .replace("<em>", " ")
                        .replace("</em>", " ")
                        .replace("\n", " ")
                        .replace("\t", " ") or ''
                        for s in doc.get('document_passages', [])
                    ]) if isinstance(doc.get('document_passages', []), list) and doc.get('document_passages', []) else ''
                    for doc in data['results']
                ])
            }
        
        logger.info(f'ran-wd_query_format_response :: END - {len(result_dict.get("passages"))}')
        return result_dict
    except Exception as e:
        return None

async def main_wd_query_and_process(user_query):
    ## prepare vendor and release
    logger.info(f'ran-main_wd_query_and_process :: END')
    try:
        resp = await wd_query_entities(user_query) # don't pass filter for now
        if resp:
            response_formated = await wd_query_format_response(resp)
            logger.info(f'ran-main_wd_query_and_process :: END')
            return response_formated
        else:
            logger.info(f'ran-main_wd_query_and_process :: END')
            return None
    except ApiException as e:
            logger.error(f'ran-main_wd_query_and_process :: ApiException occurred :: Attempttng again :: {str(e)}')
            resp = await wd_query_entities(user_query) # don't pass filter for now
            if resp:
                response_formated = await wd_query_format_response(resp)
                logger.info(f'ran-main_wd_query_and_process :: END')
                return response_formated
            else:
                logger.info(f'ran-main_wd_query_and_process :: END')
                return None                 
    except Exception as e:
        print("e")
        logger.error(f'ran-main_wd_query_and_process :: ERROR')
        return None