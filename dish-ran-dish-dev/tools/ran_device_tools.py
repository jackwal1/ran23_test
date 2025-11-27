from typing import List, Dict, Annotated
from langchain_core.tools import tool
import re
import httpx
from pydantic import BaseModel, Field
from utils import constants as CONST
from utils.log_init import logger
from llms.llms import is_test_case_present
import json


DEVICE_GENERAL_COLL_ID = CONST.DEVICE_GENERAL_COLL_ID.split('|')
DEVICE_CSV_COLL_ID = CONST.DEVICE_CSV_COLL_ID.split('|') # csv
collection_ids=[]
return_value=[]

# invoke watson discovery
async def invoke_watson_discovery(payload):
    """
    Function to invoke Watson Discovery with the given payload.

    Args:
        payload (dict): The payload to send to Watson Discovery.

    Returns:
        dict: The response from Watson Discovery.
    """
    url = f'{CONST.WD_URL}/v2/projects/{CONST.DEVICE_WD_PROJECT_ID}/query?version={CONST.WD_VERSION}'
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f'Bearer {CONST.WD_BEARER_TOKEN}'
    }
    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            res = response.json()
            #logger.info(f"res:{res}")
            results = res.get('results', [])
            # print(results)

            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            return {"error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Error invoking Watson Discovery: {e}")
            return {"error": "Error occurred while invoking Watson Discovery."}




# vector search docs    
async def device_vector_search(extraction_result) -> str:
    """
    Async function that performs vector search on Watson Discovery with automatic
    filtering of older document versions when release is not specified.

    Args:
        query (str): Search query text
        is_test_case (str): checks if test case id is present or not

    Returns:
        str: Formatted search results
    """
    # set booleans
    # has_test_case = False
    # has_file_name = False
    # if extraction_result["has_test_case"] == "true":
    #     has_test_case = True
    # if extraction_result["has_file_name"] == "true":
    #     has_file_name = True

    # query_type_count= False
    # Determine payload attribute values
    if (not extraction_result.has_data_source) and extraction_result.has_test_case:

        query = f'"{extraction_result.test_case_id}"'
        collection_ids = DEVICE_CSV_COLL_ID
        doc_count = 3
        return_value = []
        passages = {}
       
    # elif extraction_result.has_file_name:
    #     # query = f'extracted_metadata.filename:{extraction_result.file_name}'
    #     filter = f'extracted_metadata.filename:"{extraction_result.file_name}"'
    #     collection_ids = DEVICE_GENERAL_COLL_ID
    #     doc_count = 1
    #     return_value = ['extracted_metadata', 'metadata', 'text']
    #     passages = {}
    else:
        query = extraction_result.query
        collection_ids = DEVICE_GENERAL_COLL_ID
        doc_count = CONST.DOC_COUNT
        return_value = ['metadata', 'document_passages']
        passages = {
            "fields": ["text","title"],
            #"fields": ["text"],
            "enabled": True,
            "characters": CONST.WD_PASSAGE_CHARACTERS_LIMIT,
            "per_document": True,
            "find_answers": False,
            "max_per_document": CONST.PASSAGES_PER_DOCUMENT, 
            #"count": int(CONST.PASSAGES_PER_DOCUMENT)
        }

    # construct payload
    payload = {
        "collection_ids": collection_ids,
        "count": doc_count,
        "return": return_value,
        "passages": passages,
        "natural_language_query": query,
        "table_results": {
            "enabled": False
        }
    }
    # check for filter
    if extraction_result.has_data_source:
        payload["query"]  = f'metadata.file_name:"{extraction_result.data_source}"'
        payload.pop("natural_language_query", None)
        

    logger.info(f'payload --> {payload}')



    # Call WD to fetch results
    results = await invoke_watson_discovery(payload)
    # WD may return empty results if filename does not match exactly
    if "query" in payload and (results is None or len(results) == 0):
        logger.info("No results found from Watson Discovery")

        # remove filename from payload if present and invoke again
        payload.pop("query", None)   # Removes 'query' if it exists
        payload["natural_language_query"]  = query  # Assign original query

        logger.info(f'payload --> {payload}')

        results = await invoke_watson_discovery(payload)

    logger.info(f"Received {len(results)} results from Watson Discovery")
    #logger.info(f"Received {results} results from Watson Discovery")
    # format the results
    formatted_results = []
    if extraction_result.has_test_case:
        for result in results:
            data = {}
            # logger.info(f"result: {result}")
            data['filename'] = result.get('metadata', {}).get('file_name', 'Unknown')
            
            # remove unnecessary fields
            result.pop('extracted_metadata', None)
            result.pop('metadata', None)
            result.pop('result_metadata', None)
            result.pop('enriched_Test_Case_ID', None)
            result.pop('document_id', None)
            result.pop('document_passages', None)
            result.pop('Status', None)
            
            data['passage'] = result
            formatted_results.append(data)
    else:
        for result in results:
            #logger.info(f"result: {result}")
            # metadata used instead of extracted_metadata.filename because xls worksheet names are in metadata
            metadata = result.get('metadata', {})
            filename = metadata.get('file_name', 'Unknown')
            # if extraction_result.has_file_name :
            #     passages = result.get('text', [])
            # else:
            #     passages = result.get('document_passages', []) 

            passages = result.get('document_passages', []) 
            
            #print(f"passages type: {type(passages)}")
            for passage in passages:
                data = {}
                # print(f"passage_text: {passage_text}")
                # if extraction_result.has_file_name:
                #     # consider only 1,00,000 characters max
                #     passage_text=passage[:100000]
                # else:
                #     passage_text = passage["passage_text"]
                
                passage_text = passage["passage_text"]
                cleaned_text = re.sub(r'[\s]+', ' ', passage_text) \
                    .replace("<em>", "").replace("</em>", "").strip().replace("\n", "").replace("\r", "")
                data['passage'] = cleaned_text
                data['filename'] = filename
                formatted_results.append(data)

    logger.info("Search completed successfully")
    logger.info(formatted_results)
    # return "\n".join(formatted_results)
    return formatted_results




class DishDocsInput(BaseModel):
    query: str = Field(..., title="The search query for RAN Device documentation")

@tool("fetch_device_data", args_schema=DishDocsInput)
async def fetch_device_data(
    query: Annotated[str, "The search query for RAn Device documentation"]
) -> List[Dict[str, str]]:
    """
        Search device engineering documentation (SIM specs, certification procedures, OMA-DM requirements, etc.) for the specified query.

        Examples of queries include:
        - What are the GID values of Enterprise SIMs?
        - Which EF file controls the PLMN scanning priority?
        - what is the name for test case ID "CBX-CAG-00013"?
        - what is the test procedure for DFIT handset test case "DSH-DCT-00011" ?

        Args:
            query: The search query related to SIM, certification process, or specification/requirement topics in device engineering.
            is_test_case: Indicates if query has test case id 

        Returns:
            A list of the top 3 most relevant documentation passages.

        Examples:
          fetch_device_data('what is the test procedure for DFIT handset test case "DSH-DCT-00011" ?' , "true")
          fetch_device_data('How many weeks for MR testing?' , "false")

    """

    
    try:
        logger.info(query)

        query_result = await is_test_case_present(query)
        results = await device_vector_search(query_result)

        return results
    except Exception as e:
        logger.error(f"error occurred in RAN docs search tool: {e}")
        return f"An error occurred while calling the RAN docs search tool"
