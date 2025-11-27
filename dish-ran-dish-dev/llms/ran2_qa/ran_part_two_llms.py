import asyncio
import threading
import time
import json
from langchain_core.prompts import PromptTemplate
import traceback
from utils import payload_logging
import utils.constants as constant
from typing import Optional
from llms.llms import (llm_text_to_sql_model_mistral)
from llms.models import extraction_model
from utils import constants as CONST
import logging

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")


async def llm_ran_text_to_sql(user_question: str, prompt, subscription_id,  worksheet: Optional[str] = None) -> str:
    try:
        prompt_template = PromptTemplate.from_template(prompt)
        chain = prompt_template | llm_text_to_sql_model_mistral
        # Start timing for the query response
        start_time = time.perf_counter()
        year, month = get_current_year_month()

        #For GPL TEXT to SQL
        if worksheet:
            query = await chain.ainvoke({
                "input": user_question,
                "year" : year,
                "month" : month,
                "worksheet": worksheet

            })
        else:
            query = await chain.ainvoke({
                "input": user_question,
                "year" : year,
                "month" : month

            })
        # Remove backticks and 'sql'
        query = query.replace("```sql", "").replace("```", "").strip()

        logger.info(f"Final Query Generated ::: {query}")

        # Calculate response time (latency)
        response_time = time.perf_counter() - start_time
        print("PAYLOAFD FLAG:", constant.PAYLOAD_LOGGING)
        if constant.PAYLOAD_LOGGING:
            try:
                # Schedule token counting and payload logging in background
                async def _bg_payload_task():
                    """Background task for async token counting and payload logging"""
                    try:
                        logger.info("Starting background payload logging task")
                        
                        llm_request = json.dumps(user_question)
                        llm_response = json.dumps(query)

                        # Run synchronous token counting in thread pool
                        loop = asyncio.get_running_loop()
                        input_token_count, generated_token_count = await asyncio.gather(
                            loop.run_in_executor(
                                None, 
                                lambda: payload_logging.get_token_count(llm_request, CONST.WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL)
                            ),
                            loop.run_in_executor(
                                None,
                                lambda: payload_logging.get_token_count(llm_response, CONST.WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL)
                            )
                        )

                        # Async payload logging
                        await payload_logging.store_summarization_payload_record(
                            user_question,
                            query,
                            input_token_count,
                            generated_token_count,
                            response_time,
                            subscription_id
                        )
                        
                        logger.info("Completed background payload logging")
                    except Exception as e:
                        logger.error(f"Background payload task failed: {str(e)}")

                # Create and start thread with new event loop
                def run_async_task():
                    asyncio.run(_bg_payload_task())

                thread = threading.Thread(target=run_async_task)
                thread.start()
                
            except Exception as e:
                traceback.print_exc()
                return 'NA'
        query = f"""{query}"""
        logger.info(f'RAN QA - 2 : user_question:{user_question} :: query:{query} - llm_ran_text_to_sql')
        return query
    except Exception as e:
        traceback.print_exc()
        return 'NA'


async def llm_ran_nca_text_to_sql(user_question: str, prompt, subscription_id) -> str:
    try:
        prompt_template = PromptTemplate.from_template(prompt)
        chain = prompt_template | extraction_model
        # Start timing for the query response
        start_time = time.perf_counter()
        query_msg = await chain.ainvoke({
            "input": user_question
        })

        query = query_msg.content
        # Remove backticks and 'sql'
        query = query.replace("```sql", "").replace("```", "").strip()

        # Calculate response time (latency)
        response_time = time.perf_counter() - start_time
       # print("PAYLOAFD FLAG:", constant.PAYLOAD_LOGGING)
        if constant.PAYLOAD_LOGGING:
            try:
                # Schedule token counting and payload logging in background
                async def _bg_payload_task():
                    """Background task for async token counting and payload logging"""
                    try:
                        logger.info("Starting background payload logging task")
                        
                        llm_request = json.dumps(user_question)
                        llm_response = json.dumps(query)

                        # Run synchronous token counting in thread pool
                        loop = asyncio.get_running_loop()
                        input_token_count, generated_token_count = await asyncio.gather(
                            loop.run_in_executor(
                                None, 
                                lambda: payload_logging.get_token_count(llm_request, CONST.WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL)
                            ),
                            loop.run_in_executor(
                                None,
                                lambda: payload_logging.get_token_count(llm_response, CONST.WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL)
                            )
                        )

                        # Async payload logging
                        await payload_logging.store_summarization_payload_record(
                            user_question,
                            query,
                            input_token_count,
                            generated_token_count,
                            response_time,
                            subscription_id
                        )
                        
                        logger.info("Completed background payload logging")
                    except Exception as e:
                        logger.error(f"Background payload task failed: {str(e)}")

                # Create and start thread with new event loop
                def run_async_task():
                    asyncio.run(_bg_payload_task())

                thread = threading.Thread(target=run_async_task)
                thread.start()
                
            except Exception as e:
                traceback.print_exc()
                return 'NA'
        query = f"""{query}"""
        logger.info(f'RAN NCA: user_question:{user_question} :: query:{query}')
        return query
    except Exception as e:
        traceback.print_exc()
        return 'NA'




async def llm_ran_text_to_sql_misalignment(user_question: str, prompt, subscription_id) -> str:
    try:
        prompt_template = PromptTemplate.from_template(prompt)
        chain = prompt_template | llm_text_to_sql_model_mistral
        # Start timing for the query response
        start_time = time.perf_counter()
        year, month = get_current_year_month()
        query = await chain.ainvoke({
            "input": user_question,
            "current_year" : year,
            "current_month" : month
        })
        # Remove backticks and 'sql'
        query = query.replace("```sql", "").replace("```", "").strip()
        # Calculate response time (latency)
        response_time = time.perf_counter() - start_time

        if constant.PAYLOAD_LOGGING:
            try:
                # Schedule token counting and payload logging in background
                async def _bg_payload_task():
                    """Background task for async token counting and payload logging"""
                    try:
                        logger.info("Starting background payload logging task")
                        
                        llm_request = json.dumps(user_question)
                        llm_response = json.dumps(query)

                        # Run synchronous token counting in thread pool
                        loop = asyncio.get_running_loop()
                        input_token_count, generated_token_count = await asyncio.gather(
                            loop.run_in_executor(
                                None, 
                                lambda: payload_logging.get_token_count(llm_request, CONST.WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA)
                            ),
                            loop.run_in_executor(
                                None,
                                lambda: payload_logging.get_token_count(llm_response, CONST.WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA)
                            )
                        )

                        # Async payload logging
                        await payload_logging.store_summarization_payload_record(
                            user_question,
                            query,
                            input_token_count,
                            generated_token_count,
                            response_time,
                            subscription_id
                        )
                        
                        logger.info("Completed background payload logging")
                    except Exception as e:
                        logger.error(f"Background payload task failed: {str(e)}")

                # Schedule task without awaiting
                asyncio.create_task(_bg_payload_task())
                
            except Exception as e:
                traceback.print_exc()
                return 'NA'
        query = f"""{query}"""
        logger.info(f'RAN QA - 2 : user_question:{user_question} :: query:{query} - llm_ran_text_to_sql')
        return query
    except Exception as e:
        traceback.print_exc()
        return 'NA'

async def llm_ran_text_to_sql_cucp(user_question: str, prompt, subscription_id) -> str:
    try:
        prompt_template = PromptTemplate.from_template(prompt)
        chain = prompt_template | llm_text_to_sql_model_mistral
        # Start timing for the query response
        start_time = time.perf_counter()
        query = await chain.ainvoke({
            "input": user_question
        })
        # Remove backticks and 'sql'
        query = query.replace("```sql", "").replace("```", "").strip()
        query = f"""{query}"""
        logger.info(f'RAN QA - 2 : user_question:{user_question} :: query:{query} - llm_ran_text_to_sql')
        return query
    except Exception as e:
        traceback.print_exc()
        return 'NA'
    

def llm_ran_table_identify(user_question: str, prompt):
    try:
        prompt_template = PromptTemplate.from_template(prompt)
        chain = prompt_template | llm_text_to_sql_model_mistral
        query = chain.invoke({ "input": user_question})
        logger.info(f'user_question:{user_question} :: query:{query} - llm_ran_table_identify')
        return query
    except Exception as e:
        traceback.print_exc()
        return 'NA'


from datetime import datetime

def get_current_year_month():
    """
    Returns the current year and month as strings.

    Returns:
        Tuple[str, str]: (current_year, current_month)
    """
    now = datetime.now()
    current_year = str(now.year)
    current_month = f"{now.month:02d}"  # zero-padded, e.g., "06" for June
    return current_year, current_month