import re
from langchain.prompts import PromptTemplate
# from prompts.prompts import (QUERY_CLASSIFIER_PROMPT_TEMPLATE_LLAMA,
#                             ANALYZER_PROMPT_TEMPLATE_LLAMA, SUMMARY_PROMPT)
from llms.models import ran_qa_chatmodel, extraction_model, ran_kpi_readout_model
from prompts.ran_qa_prompt import RELEASE_USER, RELEASE_SYSTEM, CHECK_ANSWER_RELEVANCY_PROMPT, PASSAGE_SUMMARIZATION_PROMPT
from prompts.ran_device_prompt import TEST_CASE_SYSTEM, TEST_CASE_USER
from prompts.ran_kpi_readout_prompt import KPI_READOUT_SYSTEM, KPI_READOUT_USER
from langchain_ibm import WatsonxLLM
from langchain_ibm import ChatWatsonx
# from dotenv import load_dotenv
# import ast
import json
# from utils.llm_utils import call_with_timeout
from utils import constants as CONST
# from llama_index.llms.ibm import WatsonxLLM as llamaindex_WatsonxLLM
from utils.log_init import logger
# from utils.ret_cell_extraction import extract_json_from_string
# from typing_extensions import Annotated, TypedDict
from pydantic import BaseModel, Field
from utils.redis_util import get_redis_client
import asyncio

llm_llama = WatsonxLLM(
    model_id=CONST.WATSONX_MODEL_ID_LLAMA,
    params=json.loads(CONST.LLM_LLAMA_PARAMS),
    project_id=CONST.WATSONX_PROJECT_ID,
    url=CONST.WATSONX_URL,
    apikey=CONST.WATSONX_API_KEY
)


chatmodel_mistral_large_ran_2 = ChatWatsonx(
    model_id=CONST.WATSONX_MODEL_ID_MISTRAL_MEDIUM,
    project_id=CONST.WATSONX_PROJECT_ID,
    url=CONST.WATSONX_URL,
    apikey=CONST.WATSONX_API_KEY,
    params=json.loads(CONST.LLM_MISTRAL_PARAMS_CHAT_RAN_2),
    streaming=True,
)

chatmodel_mistral_medium_ran_2 = ChatWatsonx(
    model_id='mistralai/mistral-small-3-1-24b-instruct-2503', #'mistralai/mistral-medium-2505',
    project_id=CONST.WATSONX_PROJECT_ID,
    url=CONST.WATSONX_URL,
    apikey=CONST.WATSONX_API_KEY,
    params=json.loads(CONST.LLM_MISTRAL_MEDIUM_CHAT_PARAMS),
    streaming=True,
)

llama_chatmodel_react = ChatWatsonx(
    model_id=CONST.WATSONX_MODEL_ID_MISTRAL_MEDIUM,
    project_id=CONST.WATSONX_PROJECT_ID,
    url=CONST.WATSONX_URL,
    apikey=CONST.WATSONX_API_KEY,
    params=json.loads(CONST.LLM_MISTRAL_PARAMS_CHAT)
)

chatmodel_ran_automation = ChatWatsonx(
    model_id=CONST.WATSONX_MODEL_ID_LLAMA_3,
    project_id=CONST.WATSONX_PROJECT_ID,
    url=CONST.WATSONX_URL,
    apikey=CONST.WATSONX_API_KEY,
    params=json.loads(CONST.WATSONX_MODEL_ID_AUTOMATION_PARAMS),
    streaming=False,
)

# llama_chatmodel_react_ran_sql = ChatWatsonx(
#     model_id=CONST.WATSONX_MODEL_ID_MISTRAL_MEDIUM, #WATSONX_MODEL_ID_LLAMA,
#     project_id=CONST.WATSONX_PROJECT_ID,
#     url=CONST.WATSONX_URL,
#     apikey=CONST.WATSONX_API_KEY,
#     params=json.loads(CONST.LLM_MISTRAL_PARAMS_CHAT),
#     streaming=True,
# )

# mistral_med_chatmodel_react_ran_sql = ChatWatsonx(
#     model_id='mistralai/mistral-medium-2505', #WATSONX_MODEL_ID_LLAMA,
#     project_id=CONST.WATSONX_PROJECT_ID,
#     url=CONST.WATSONX_URL,
#     apikey=CONST.WATSONX_API_KEY,
#     params=json.loads(CONST.LLM_MISTRAL_PARAMS_CHAT),
#     streaming=True,
# )

llama_405_chatmodel_react = ChatWatsonx(
    model_id=CONST.WATSONX_MODEL_ID_LLAMA_405,
    project_id=CONST.WATSONX_PROJECT_ID,
    url=CONST.WATSONX_URL,
    apikey=CONST.WATSONX_API_KEY,
    params=json.loads(CONST.LLM_LLAMA_405_PARAMS_CHAT)
)

# Initialize LLM
llm_text_to_sql_model_mistral = WatsonxLLM(
    model_id = CONST.WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL,
    params=json.loads(CONST.WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL_PARAMS),
    project_id = CONST.WATSONX_PROJECT_ID,
    url = CONST.WATSONX_URL,
    apikey = CONST.WATSONX_API_KEY
)

# This function is used to summarize the passages fetched from the 5G RAN documentation based on the user query.
def passage_summarization(query, passages) -> dict[str, str]:
    
    system = PASSAGE_SUMMARIZATION_PROMPT

    # prompt_template = PromptTemplate.from_template(summary_prompt)
    # chain = prompt_template | ran_qa_chatmodel
    # summary = await chain.ainvoke({"query": query, "passages": passages})

    # logger.info(f"Output from LLM before processing -> {summary.content}")

    # final_response = extract_json_from_llm_response(summary.content)

    # user = f""" {QUERY_KPI_USER}

    user = f"""   

    Input: 
    {{
        "query": {query},
        "passages": {passages}
    }}

    Response:

    """

    # Final mistral-style prompt
    mistral_prompt = f"""
    <|system|>
    {system}
    
    <|user|>
    {user}
    
    ai_response:
    <|assistant|>
    """

    result = ran_qa_chatmodel.invoke(mistral_prompt)
    # logger.info(f"Output from LLM before processing -> {result.content}")

    result_content = (result.content).strip()
    logger.info(f"Output from LLM before processing -> {result_content}")
    result_str = result_content.replace("json","").replace("python","").replace("```","")
    # logger.info(f"Result STR -> {result_str}")
    # logger.info(f"Result type -> {type(result_str)}")
    safe_json_string = escape_json_string_literals(result_str)
    result_json = json.loads(safe_json_string)

    # result_json = extract_json_from_string(result_str)
    # logger.info(f"Result JSON -> {result_json}")
    return result_json
    # final_response = extract_json_from_llm_response(result.content)

    # result_json_string = json.dumps(result_str, ensure_ascii=False)
    # return result_json_string

# # This function is used to check relevancy of the answer
# def check_relevancy(
#         query: str,
#         passages: list[dict[str, str]] = None,
#         answer: str = None
# ) -> dict[str, str]:
    
#     system = CHECK_ANSWER_RELEVANCY_PROMPT

#     user = f"""   

#     Input: 
#     {{
#         "query": {query},
#         "passages": {passages},
#         "answer": {answer}
#     }}

#     Response:

#     """

#     llama_prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>{system}<|eot_id|><|start_header_id|>user<|end_header_id|>{user}<|eot_id|>
#     <|start_header_id|>assistant<|end_header_id|>"""

#     # Final mistral-style prompt
#     # mistral_prompt = f"""
#     # <|system|>
#     # {system}
    
#     # <|user|>
#     # {user}
    
#     # ai_response:
#     # <|assistant|>
#     # """

#     result = ran_qa_relevance_model.invoke(llama_prompt)
#     logger.info(f"Output from LLM before processing -> {result}")

#     result_str = result.replace("json","").replace("python","").replace("```","")

#     result_str_json = json.loads(result_str)

#     return result_str_json

# escape_json_string_literals function to escape newlines in JSON strings
def escape_json_string_literals(raw_str: str) -> str:
    # Escape real newlines inside double-quoted JSON values
    def escape_newlines_in_quotes(match):
        inner = match.group(1)
        escaped = inner.replace('\n', '\\n')
        return f'"{escaped}"'
    return re.sub(r'"(.*?)"', escape_newlines_in_quotes, raw_str, flags=re.DOTALL)

# extract release
async def extract_release(user_query):
    system = RELEASE_SYSTEM

    user = f""" {RELEASE_USER}
    
    Input: 
    {user_query}
    """

    ## Llama prompt
    llama_prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
    {system}<|eot_id|>
    <|start_header_id|>user<|end_header_id|>
    {user}<|eot_id|>
    <|start_header_id|>assistant<|end_header_id|>"""

    result = await llm_llama.ainvoke(llama_prompt)
    logger.info(f"Output from LLM before processing -> {result}")
    content = re.sub(r'\s+', '', result.strip())
    return content


# TypedDict
# class QueryTypeResponse(TypedDict):
#     """Type of query"""

#     has_test_case_id: Annotated[bool, False, "Whether Test case id is present in query"]
#     test_case_id: Annotated[str, ..., "The Test case id"]
#     # has_file_name: Annotated[bool, False, "Whether file name is present in query"]
#     # file_name: Annotated[str, ..., "The file name"]


# check if test case ID is present
# async def is_test_case_present(user_query):
#     system = TEST_CASE_SYSTEM

#     user = f""" {TEST_CASE_USER}
    
#     Input: 
#     {user_query}
#     """

#     ## Llama prompt
#     llama_prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
#     {system}<|eot_id|>
#     <|start_header_id|>user<|end_header_id|>
#     {user}<|eot_id|>
#     <|start_header_id|>assistant<|end_header_id|>"""

#     # structured_llm = llm_llama.with_structured_output(QueryTypeResponse)      # This did not work

#     result = await llm_llama.ainvoke(llama_prompt)
#     logger.info(f"Output from LLM before processing -> {result}")
#     # content = re.sub(r'\s+', '', result.strip())
#     content = result.replace("json","").replace("python","").replace("```","")
#     # content = re.sub(r'\s+|json|python|```', '', result.strip(), flags=re.IGNORECASE)
#     # logger.info(f"Output after LLM before processing -> {content}")
#     return content


class ExtractionResult(BaseModel):
    has_test_case: bool = Field(..., description="True if a test case id is found in the query, else false")
    test_case_id: str = Field(..., description="The exact test case id found, or empty string if none")    
    has_data_source: bool = Field(..., description="True if a filename is found in the query, else false")
    data_source: str = Field(..., description="The exact filename found, or empty string if none")
    query: str = Field(..., description="user query") 


# check for test case id & file name
async def is_test_case_present(user_query):
    system = TEST_CASE_SYSTEM

    user = f""" {TEST_CASE_USER}
    Input:
        {user_query}

    Response:

    """

    # Final mistral-style prompt
    mistral_prompt = f"""
    <|system|>
    {system}
    
    <|user|>
    {user}
    
    ai_response:
    <|assistant|>
    """

    structured_llm = extraction_model.with_structured_output(ExtractionResult) 
    result = await structured_llm.ainvoke(mistral_prompt)
    # result_content = (result.content).strip()
    # print(type(result))
    logger.info(result)
    # result_str = result.replace("json","").replace("python","").replace("```","")
    # # safe_json_string = escape_json_string_literals(result_str)
    # result_json = json.loads(result_str)
    return result


# analyze KPI readout
async def analyze_kpi_readout(input_data, redis_key):
    system = KPI_READOUT_SYSTEM

    user = f""" {KPI_READOUT_USER}

        ran_kpi_data: {input_data}

    Answer:    

    """

    # Final mistral-style prompt
    gpt_prompt = f"""
    <|system|>
    {system}
    
    <|user|>
    {user}
    
    ai_response:
    <|assistant|>
    """

    # prompt_template = PromptTemplate.from_template(user)
    # # chain = prompt_template | ran_qa_chatmodel
    # # prompt = prompt_template.format(input_data=json.dumps(input_data, indent=2))

    # Variable to accumulate all content
    accumulated_content = ""

    # Stream the result
    async for chunk in ran_kpi_readout_model.astream(gpt_prompt):
        chunk_content = chunk.content
        accumulated_content += chunk_content  # Accumulate the content

        message = {'type': 'text', 'content': f"{chunk_content}"}
        yield f"data: {json.dumps(message)}"
        yield "\n\n"


    # Store accumulated content in Redis if redis_key is provided
    if redis_key:
        # Create a task for storing data in Redis
        async def store_in_redis():
            redis_client = get_redis_client()
            # Store in Redis with expiry time (1 hour)
            logger.info(f"Accumulated Content from llm:: {accumulated_content}")

            await redis_client.set(
                redis_key,
                accumulated_content,
                expire_seconds=3600  # 1 hour in seconds
            )

        # Create the storage task
        storage_task = asyncio.create_task(store_in_redis())

        # Periodically check if storage is complete
        while not storage_task.done():
            # Emit blank message to keep connection alive
            message = {'type': 'text', 'content': ""}
            yield f"data: {json.dumps(message)}"
            yield "\n\n"

            # Wait before next check
            try:
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                # Task was cancelled
                return

        # Check if the task completed successfully or with an exception
        if storage_task.exception():
            # Task raised an exception
            exc = storage_task.exception()
            logger.error(f'Redis storage failed with exception: {exc}')
            # Optionally notify client of error, but continuing with PDF link
            # For now, we'll just log and continue

        # Add a newline before the PDF link
        newline_message = {'type': 'text', 'content': '\n'}
        yield f"data: {json.dumps(newline_message)}"
        yield "\n\n"
        newline_message = {'type': 'text', 'content': '\n'}
        yield f"data: {json.dumps(newline_message)}"
        yield "\n\n"

        # Add PDF generation link after all chunks are streamed
        pdf_link = f"{CONST.RAN_BASE_URL}markdown_to_pdf?key={redis_key}"
        link_message = {
            'type': 'text',
            'content': f'<a href="{pdf_link}" target="_blank">Generate PDF Report</a>'
        }
        yield f"data: {json.dumps(link_message)}"
        yield "\n\n"