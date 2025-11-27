from typing import Literal, List, Dict, Annotated
from langchain_core.tools import tool
import re
import json
import httpx
from typing import Optional
from pydantic import BaseModel, Field
from utils import constants as CONST
# from packaging import version as version_parser
# from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
# from dateutil.parser import parse as dateutil_parse
# from rapidfuzz import fuzz
from llms.llms import extract_release
from utils.log_init import logger

# def extract_version_info(filename: str) -> Tuple[bool, Optional[Tuple[str, Dict]], Optional[Tuple[str, Dict]]]:
#     """
#     Extract release and document version information from a filename using packaging and dateutil.

#     Args:
#         filename (str): The filename to analyze

#     Returns:
#         Tuple[bool, Optional[Tuple[str, Dict]], Optional[Tuple[str, Dict]]]:
#         (has_version, release_info, doc_info)
#     """
#     release_info = None
#     doc_info = None

#     # Extract release version (SVRXXY)
#     svr_match = re.search(r'SVR(\d{2})(\w)', filename, re.IGNORECASE)
#     if svr_match:
#         year = svr_match.group(1)
#         letter = svr_match.group(2).upper()
#         if len(year) == 2:
#             year = f"20{year}"
#         release_info = ("svr_release", {"year": int(year), "letter": letter})

#     # Extract document version (semantic or date)
#     doc_matches = re.findall(r'(?:_)?[vV](?:er)?(\d+\.\d+(?:\.\d+)?)', filename, re.IGNORECASE)
#     if doc_matches:
#         version_str = doc_matches[-1]
#         try:
#             doc_info = ("semver", {"value": version_parser.parse(version_str)})
#         except:
#             doc_info = ("semver", {"value": version_str})
#     else:
#         # Try date-based version (e.g., 240704)
#         date_match = re.search(r'\b(\d{6,8})\b', filename)
#         if date_match:
#             try:
#                 date_str = date_match.group(1)
#                 parsed_date = dateutil_parse(date_str, fuzzy=False)
#                 doc_info = ("date", {"value": parsed_date})
#             except:
#                 pass

#     has_version = release_info is not None or doc_info is not None
#     return has_version, release_info, doc_info

# def preprocess_filename(filename: str) -> str:
#     """
#     Preprocess the filename to remove extensions, release, and version info for grouping.

#     Args:
#         filename (str): The filename to preprocess

#     Returns:
#         str: Preprocessed filename for base comparison
#     """
#     logger.debug(f"Preprocessing filename: {filename}")
#     # Use pathlib to remove extension
#     name = Path(filename).stem

#     # Remove release version (e.g., "SVR24A", "for SVR24A NR")
#     name = re.sub(r'(?:\s*for\s+)?SVR\d{2}[A-Z](?:\s+NR)?', '', name, flags=re.IGNORECASE)

#     # Remove version patterns
#     version_patterns = [
#         r'[_\-\s][vV](?:er)?\d+\.\d+(?:\.\d+)?',  # matches _v1.0, v1.0.0
#         r'[_\-\s]version\d+(\.\d+)*',             # matches _version1
#         r'[_\-\s]rev\d+(\.\d+)*',                 # matches _rev1
#         r'[_\-\s]\d{6,8}\b',                      # matches date formats like 240704, 20220303
#     ]

#     for pattern in version_patterns:
#         name = re.sub(pattern, '', name, flags=re.IGNORECASE)

#     # Normalize
#     clean_name = name.lower().replace(' ', '').replace('-', '').replace('_', '')
#     logger.debug(f"Preprocessed filename: {clean_name}")
#     return clean_name.strip()

# def calculate_similarity(str1: str, str2: str) -> float:
#     """
#     Calculate similarity ratio between two strings using rapidfuzz.

#     Args:
#         str1 (str): First string
#         str2 (str): Second string

#     Returns:
#         float: Similarity ratio between 0 and 1
#     """
#     logger.debug(f"Calculating similarity between '{str1}' and '{str2}'")
#     similarity = fuzz.ratio(str1, str2) / 100.0  # Normalize to 0-1
#     logger.debug(f"Similarity ratio: {similarity}")
#     return similarity

# def filter_by_latest_release_per_similar_file(results: List[Dict[str, Any]],
#                                               similarity_threshold: float = 0.9) -> List[Dict[str, Any]]:
#     """
#     Filter results to keep only the latest release per similar file group.

#     Args:
#         results (List[Dict[str, Any]]): The search results from Watson Discovery
#         similarity_threshold (float): Minimum similarity ratio for grouping (default: 0.9)

#     Returns:
#         List[Dict[str, Any]]: Filtered results containing only the latest release per document group
#     """
#     logger.info(f"Starting filtering with {len(results)} results and similarity threshold {similarity_threshold}")
#     if not results:
#         logger.warning("No results to filter")
#         return []

#     # Extract and preprocess filenames
#     processed_items = []
#     for result in results:
#         filename = result.get('metadata', {}).get('file_name', '')
#         base_name = preprocess_filename(filename)
#         version_info = extract_version_info(filename)
#         processed_items.append((result, filename, base_name, version_info))

#     # Group by similarity
#     groups = []
#     remaining = set(range(len(processed_items)))
#     while remaining:
#         current = min(remaining)
#         current_group = [processed_items[current]]
#         base_name_i = processed_items[current][2]
#         remaining.remove(current)
#         to_remove = set()
#         for j in remaining:
#             base_name_j = processed_items[j][2]
#             if calculate_similarity(base_name_i, base_name_j) >= similarity_threshold:
#                 current_group.append(processed_items[j])
#                 to_remove.add(j)
#         remaining -= to_remove
#         groups.append(current_group)

#     logger.info(f"Grouped results into {len(groups)} groups")

#     # Process each group to keep only the latest version
#     filtered_results = []
#     for group in groups:
#         if len(group) == 1:
#             filtered_results.append(group[0][0])
#             continue

#         # Sort by release year, letter, then document version
#         sorted_items = sorted(group, key=lambda x: (
#             x[3][1][1]["year"] if x[3][1] is not None else 0,
#             x[3][1][1]["letter"] if x[3][1] is not None else "",
#             x[3][2][1]["value"] if x[3][2] is not None else ""
#         ), reverse=True)
#         filtered_results.append(sorted_items[0][0])

#     logger.info(f"Filtered from {len(results)} to {len(filtered_results)} results")
#     return filtered_results

# extract single category value, from user query, based on priority shared
def extract_priority_keyword(prompt: str) -> str | None:
    allowed_keywords = ['release', 'kpi','gpl', 'alarm', 'counter', 'mop','feature','parameter']
    prompt_lower = prompt.lower()
    for keyword in allowed_keywords:
        if keyword in prompt_lower:
            return keyword
    return None
    
# sort priority - release
def release_sort_key(doc):
    release = doc['metadata'].get('release', '')
    
    if release == "NOT_DEFINED":
        return (2, '')  # Lowest priority
    
    try:
        return (0, int(release))  # Numeric releases (highest priority)
    except ValueError:
        return (1, release)  # Alphanumeric but not numeric
    
# vector search docs    
async def qa_vector_search(query: str,
                        vendor: str = None,
                        release: str = None,
                        category: str = None,
                        similarity_threshold: float = 0.9) -> List[Dict[str, str]]:
    """
    Async function that performs vector search on Watson Discovery with automatic
    filtering of older document versions when release is not specified.

    Args:
        query (str): Search query text
        vendor (str, optional): Vendor filter
        release (str, optional): Specific release filter
        category (str, optional): Category filter
        similarity_threshold (float, optional): Threshold for filename similarity (default: 0.9)

    Returns:
        str: Formatted search results
    """
    logger.info(f"Starting vector search with query: '{query}', vendor: {vendor}, release: {release}, category: {category}")

    payload = {
        # "aggregation": "[term(enriched_text.entities.text,name:entities)]",
        "count": CONST.DOC_COUNT,
        "return": ["metadata", "extracted_metadata", "document_passages"],
        "passages": {
            "fields": ["text"],
            "enabled": True,
            "characters": CONST.WD_PASSAGE_CHARACTERS_LIMIT,
            "per_document": True,
            "find_answers": False,
            "max_per_document": CONST.PASSAGES_PER_DOCUMENT
        },
        "natural_language_query": query,
        "table_results": {
            "enabled": False
        }
    }

    filter_conditions = []
    sort_val = None
    if vendor:
        filter_conditions.append(f'metadata.vendor:"{vendor}"')
    if release:
        filter_conditions.append(f'metadata.release:"{release}"')
    if category:
        # add sort condition for category='release'
        if 'release' in category:
            sort_val="-metadata.release,-metadata.version"
            payload["sort"] = sort_val
        # consider kpi & counter together 
        if ('kpi' in category) or ('counter' in category):
            filter_conditions.append(f'(metadata.file_category:"kpi"|metadata.file_category:"counter")')
        else:
            filter_conditions.append(f'metadata.file_category:"{category}"')

    # sort_val="-metadata.release,-metadata.version"
    # payload["sort"] = sort_val

    # if category:
    #     # remove any space and split
    #     category_list = [item.strip() for item in category.split(",")]
    #     category_filter = f'''{ '|'.join(f'(metadata.file_category:"{value}")' for value in category_list) }'''
    #     filter_conditions.append(f'({category_filter})')
    if filter_conditions:
        payload["filter"] = ','.join(filter_conditions)
        logger.info(f'Applied filters: {payload["filter"]}')
    
    logger.info(f'payload --> {payload}')

    url = f'{CONST.WD_URL}/v2/projects/{CONST.WD_RAN_PROJECT_ID}/query?version={CONST.WD_VERSION}'
    # print(f'url --> {url}')
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f'Bearer {CONST.WD_BEARER_TOKEN}'
    }

    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        try:
            logger.info("Sending request to Watson Discovery")
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            res = response.json()
            results = res.get('results', [])
            # logger.info(f"Received {len(results)} results from Watson Discovery")
            # Sort in descending order based on release number if available
            results = sorted(results, key=release_sort_key, reverse=True)            
            # for result in results:
            #     metadata = result.get('metadata', {})
            #     file_name = metadata.get('file_name', 'Unknown')
            #     logger.info(f"file_name received ::{file_name}")

            # if not release and results:
            #     logger.info("Applying filtering for latest releases")
            #     results = filter_by_latest_release_per_similar_file(results, similarity_threshold)

            # formatted_results = []
            # for result in results:
            #     # logger.info(f"result: {result}")
            #     metadata = result.get('metadata', {}) # why not read extracted_metadata.filename?
            #     file_name = metadata.get('file_name', 'Unknown')
            #     formatted_results.append(f"file_name :: {file_name}")
            #     formatted_results.append("----->")
            #     passages = result.get('document_passages', [])
            #     if passages:
            #         passage_text = passages[0].get('passage_text', '')
            #         cleaned_text = re.sub(r'[-\s]+', ' ', passage_text) \
            #             .replace("<em>", "").replace("</em>", "").strip().replace("\n", "").replace("\r", "")
            #         formatted_results.append(cleaned_text)
            #     else:
            #         formatted_results.append("No passage text available")
            #     formatted_results.append("\n")

            formatted_results = []
            for result in results:
                # print(f"result: {result}")
                # metadata used instead of extracted_metadata.filename because xls worksheet names are in metadata
                metadata = result.get('metadata', {})
                filename = metadata.get('file_name', 'Unknown')

                passages = result.get('document_passages', [])
                # print(f"passages type: {type(passages)}")
                for passage in passages:
                    data = {}
                    # print(f"passage_text: {passage_text}")
                    passage_text = passage["passage_text"]
                    cleaned_text = re.sub(r'[\s]+', ' ', passage_text) \
                        .replace("<em>", "").replace("</em>", "").strip().replace("\n", "").replace("\r", "")
                    data['passage'] = cleaned_text
                    data['filename'] = filename
                    formatted_results.append(data)

            logger.info("Search completed successfully")
            # logger.info(formatted_results)
            # return "\n".join(formatted_results)
            return formatted_results
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            return f"HTTP error: {e.response.status_code}"
        except Exception as e:
            logger.error(f"Error processing search results: {e}")
            return "Error occurred while processing the search."


class DishDocsInput(BaseModel):
    query: str = Field(..., title="The search query for 5G RAN documentation")
    vendor: Optional[str] = Field(None, title="The RAN vendor (Mavenir or Samsung) only if specified in the query")
    # release: Optional[str] = Field(None, title="The RAN EMS release version if specified in the query")
    # category: Optional[str] = Field(None, title="The category (kpi, counter, alarm, gpl, mop, feature) if specified in the query")

@tool("fetch_passages", args_schema=DishDocsInput)
async def fetch_passages(
    query: Annotated[str, "The search query for 5G RAN documentation"],
    vendor: Annotated[Optional[str], "The RAN vendor (Mavenir or Samsung) only if specified in the query"] = None,    
) -> str:
    """
    Search 5G RAN documentation (release notes, solution guides, manuals, GPL parameters, etc.) for the specified query.
    This tool will return top 3 matching passages from the documentation which needs to analyzed and presented to user as summary. Do not use the output as it is for the final response.

    Args:
        query: The search query for general 5G RAN documentation.
        vendor: The RAN vendor only if specified in the query (optional). Allowed values are 'mavenir' or 'samsung'.
    
    Returns:
        A list of dictionaries containing matching passages from the documentation.

    Single call Examples:
        1. fetch_passages("What are the Cell Resel Intra and Inter Freq Info for serving band n70?")
        2. fetch_passages("Describe the a2-criteria-info of connected mobility for frequency band.")
        3. fetch_passages("How is hand over handled in Samsung RAN?", vendor="samsung")
        4. fetch_passages("What is the ORU initial registration and call home flow in Mavenir?", vendor="mavenir")

    Multiple calls Example:
        1.query: "Samsung and Mavenir ANR feature"
            a. fetch_passages("Samsung ANR feature", vendor="samsung")
            b. fetch_passages("Mavenir ANR feature", vendor="mavenir")

        2.query: "Trust store path for samsung and Mavenir"
            a. fetch_passages("Trust store path for samsung ", vendor="samsung")
            b. fetch_passages("Trust store path for mavenir ", vendor="mavenir")
    """
    # extract release number
    # query = dishDoc.query
    # vendor = dishDoc.vendor
    logger.info(f"Running RAN docs search tool with query: {query}, vendor: {vendor}")

    try:
        release = await extract_release(query)
        if release == "None":
            release = None
        # extract category
        category = extract_priority_keyword(query)
        # vector search docs
        # print("CALLING RAN docs search tool")
        results_list = await qa_vector_search(query, vendor, release, category)
        logger.info(f"Search results: {len(results_list)} results found")
        return results_list
    
        # # Use a special delimiter to join values
        # results_str = ' ||| '.join(f"{item['filename']} ::: {item['passage']}" for item in results_list)            
        # return results_str
    
    except Exception as e:
        logger.error(f"error occurred in RAN docs search tool: {e}")
        return f"An error occurred while calling the RAN docs search tool"


# # Input schema for summarization tool
# class answerQueryInput(BaseModel):
#     query: str = Field(..., title="User question.")
#     # passages: str = Field(..., title="The passages to look for an answer to the user question.")
#     passages: str = Field(..., title="The passages to look for an answer to the user question.")

# # find answer to user question from the fetched passages
# @tool("answer_query", args_schema=answerQueryInput)
# async def answer_query(
#     query: Annotated[str, "User question."],
#     passages: Annotated[str, "The passages to look for an answer to the user question."] = None,
# ) -> str:

#     """
#     Find relevant answer to the user questions from the provided passages.
#     This tool will return a summary as the answer to the user question based on the provided passages.

#     Args:
#         query: User question.
#         passages: The passages to look for answer to the user question.

#     Returns:
#         answer: Summarized answer to the user question based on the provided passages.
#         filename: List of file names from which the summary is generated.

 
#     """
#     default_response = {"answer": "No relevant information found for the query. Please rephrase query.", "filename": []}

#     # logger.info(passages)

#     reconstruct_passages = []
#     if not passages:
#         return default_response

#     # Reconstruct passages from the input string       
#     for item in passages.split(' ||| '):
#         filename, passage = item.split(' ::: ')
#         reconstruct_passages.append({"filename": filename, "passage": passage})

#     logger.info("passage reconstruction successful")

#     # Call the language model to summarize the passages
#     query_answer_json = passage_summarization(query,reconstruct_passages)
#     logger.info(f'query_answer --> {query_answer_json}')

#     # if answer available, check if it is relevant to the user query
#     # query_answer_json = json.loads(query_answer)
#     if query_answer_json["answer"]:
#         print("Calling check_relevancy")
#         relevancy = check_relevancy(query,reconstruct_passages, query_answer_json["answer"])
#         if relevancy["is_relevant"].lower() == "true":
#             return query_answer_json
#         else:
#             return default_response
#     else:
#         return default_response
