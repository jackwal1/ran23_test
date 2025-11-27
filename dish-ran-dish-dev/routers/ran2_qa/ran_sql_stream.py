import threading
import time
import traceback
from fastapi import APIRouter, status, Response
from routers.pydantic_model import ChatRequest
from fastapi import HTTPException
from utils import payload_logging
import logging
import os
from starlette.responses import StreamingResponse
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

from graph.ran2_qa.ran_sql_graph_v2 import initialize_agent

from agent.ran_config_qa_agent import initialize_ran_config_qa_agent_medium
from utils.ran2_qa.ran_sql_agent_utils import process_chunks

#from agent.ran_config_qa_agent import initialize_ran_config_qa_agent

import asyncio
import json
from utils import constants as CONST, payload_logging
from utils.error_handling_streaming_response import ErrorHandlingStreamingResponse
from typing import AsyncGenerator, Union
import utils.constants as constant
from fastapi.responses import JSONResponse
import traceback
#from typing import List, Dict, Any, Optional, Union
#from chat.gpl_chat import validator_process_chat


log_level = getattr(logging, constant.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")  # Replace 'RAN' with your app/module name


try:
    # Fetch environment variables
    url_for_pdf_links = os.environ["URL_FOR_PDF_LINKS"]
    WATSONX_MODEL_ID_MISTRAL_MEDIUM = os.environ["WATSONX_MODEL_ID_MISTRAL_MEDIUM"]
    RAN_2_SQL_AGENT_INST_SUB_ID = os.environ["RAN_2_SQL_AGENT_INST_SUB_ID"]
except Exception as e:
    print(e)
    print("Loading Environmment Variables from local .env file")
    load_dotenv()
    url_for_pdf_links = os.environ["URL_FOR_PDF_LINKS"]
    WATSONX_MODEL_ID_MISTRAL_MEDIUM = os.environ["WATSONX_MODEL_ID_MISTRAL_MEDIUM"]
    RAN_2_SQL_AGENT_INST_SUB_ID = os.environ["RAN_2_SQL_AGENT_INST_SUB_ID"]

agentic_ran_sql = APIRouter(prefix='/watsonx/ran', tags=['RAN Part - 2 : QA'])


async def process_chat_stream(message: str, thread_id: str):
    langgraph_agent = await initialize_ran_config_qa_agent_medium()
    buffer = ""
    first_chunk_processed = False  # Flag to track if the first chunk has been processed
    # Start timing for the query response
    start_time = time.perf_counter()
    #enriching the query
    validator_thread = "ran_validate_"+ thread_id

    #Assume this returns a dictionary of key-value pairs
    # response_data: Dict[str, Optional[str]] = await validator_process_chat(message, thread_id,validator_thread)
    #
    # logger.info(f'final response (params) from validator: {response_data}')
    #
    # if response_data:
    #     # Check if we have complete information and can proceed with graph call
    #     raw_value = response_data.get('missing_info', True)
    #
    #     if isinstance(raw_value, str):
    #         missing_info = raw_value.strip().lower() in ('true', '1', 'yes')
    #     else:
    #         missing_info = bool(raw_value)
    #     final_query = response_data.get('final_query')
    #     ai_message = response_data.get('ai_message')
    #
    #     if not missing_info and final_query:
    #         # We have complete information, proceed with graph call using final_query
    #         logger.info(f'Processing complete query: {final_query}')
    #         query_to_process = final_query
    #     else:
    #         # Missing information, yield AI message for clarification
    #         logger.info(f'Missing information detected, yielding AI message: {ai_message}')
    #         if ai_message:
    #             item = {'type': 'text', 'content': ai_message}
    #             yield f"data: {json.dumps(item)}"
    #             yield "\n\n"
    #             return
    #         else:
    #             # Fallback message if no AI message is provided
    #             fallback_message = "I need more information to process your request. Please provide additional details."
    #             item = {'type': 'text', 'content': fallback_message}
    #             yield f"data: {json.dumps(item)}"
    #             yield "\n\n"
    #             return
    # else:
    #     # No response data from validator, use original message
    #     logger.info("No response data from validator, using original message")
    #     query_to_process = message

    async for event in langgraph_agent.astream_events({"messages": [HumanMessage(content=message)]},
                                                            {"recursion_limit": 5,"configurable": {"thread_id": thread_id}}, version="v2"):
        # Calculate response time (latency)
        response_time = time.perf_counter() - start_time
        await process_chunks(event)
        kind = event["event"]
        metadata = event.get('metadata')
        if isinstance(metadata, dict):
            langgraph_node_value = metadata.get('langgraph_node')

        if kind == "on_chat_model_stream" and langgraph_node_value == "llm":
            # yield f"data: {json.dumps({'type': 'start', 'element_type': 'text'})}"
            # yield "\n\n"
            chunk = event["data"]["chunk"]
            content = chunk.content if hasattr(chunk, "content") else str(chunk)

            if content:  # Ensure content is not empty
                buffer += content

            # yield content
            item = {'type': 'text', 'content': content}
            yield f"data: {json.dumps(item)}"
            yield "\n\n"
            # Log the payload after the first chunk is processed
            if not first_chunk_processed:
                first_chunk_processed = True  # Set the flag to True after logging
                if constant.PAYLOAD_LOGGING:
                    try:
                        # Schedule token counting and payload logging in background
                        async def _bg_payload_task():
                            """Background task for async token counting and payload logging"""
                            try:
                                logger.log("Starting background payload logging task")

                                llm_request = json.dumps(message)
                                llm_response = json.dumps(content)

                                # Run synchronous token counting in thread pool
                                loop = asyncio.get_running_loop()
                                input_token_count, generated_token_count = await asyncio.gather(
                                    loop.run_in_executor(
                                        None,
                                        lambda: payload_logging.get_token_count(llm_request, WATSONX_MODEL_ID_MISTRAL_MEDIUM)
                                    ),
                                    loop.run_in_executor(
                                        None,
                                        lambda: payload_logging.get_token_count(llm_response, WATSONX_MODEL_ID_MISTRAL_MEDIUM)
                                    )
                                )

                                # Async payload logging
                                await payload_logging.store_summarization_payload_record(
                                    message,
                                    content,
                                    input_token_count,
                                    generated_token_count,
                                    response_time,
                                    RAN_2_SQL_AGENT_INST_SUB_ID
                                )

                                logger.log("Completed background payload logging")
                            except Exception as e:
                                logger.log(f"Background payload task failed: {str(e)}")

                        # Create and start thread with new event loop
                        def run_async_task():
                            asyncio.run(_bg_payload_task())

                        thread = threading.Thread(target=run_async_task)
                        thread.start()

                    except Exception as e:
                        logger.log(f"Error scheduling background task: {str(e)}")

            # yield f"data: {json.dumps({'type': 'end', 'element_type': 'text'})}"
            # yield "\n\n"
            # Handle end event
        elif event['name'] == "end_event":
            if buffer:  # Send any remaining buffered content
                yield buffer
            yield "end\n"  # Indicate the end of the stream
            break

async def safe_sse_stream(
        raw_gen: AsyncGenerator[bytes, None]
) -> AsyncGenerator[bytes, None]:
    """
    Wraps the raw SSE bytes generator, catches all exceptions,
    and emits a final SSE-formatted error event instead of crashing.
    """
    try:
        async for chunk in raw_gen:
            yield chunk
    except Exception as e:
        traceback.print_exc()
        # Format an SSE 'error' event
        error_message = f"data: {json.dumps({'type': 'error', 'content': 'An unexpected error occurred. Please try again.'})}\n\n"

        yield error_message.encode("utf-8")
    finally:
        # Attempt to close the underlying generator if it supports aclose()
        close = getattr(raw_gen, "aclose", None)
        if close:
            await close()



@agentic_ran_sql.post(
    "/ran_sql_stream",
    summary="RAN 2 QA AI Assistant - Agentic RAG implementation",
    status_code=status.HTTP_200_OK,
    response_description="Answer for the user question from Database using ReAct model",
)
async def query_user_question(request: ChatRequest):
    """
      ### RAN 2 QA AI Assistant - Agentic RAG implementation
     Query the Database for the user question:
     **Input:**
     - user_question: questions from the user

     **Output:**
     - A response for the user question
     """
    logger.info(f'user_question:{request.message}')
    try:
        # Validate input
        if not request.message or not request.message.strip():
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "response": "Please provide a valid question.",
                    "status": "error",
                    "error_code": "EMPTY_INPUT"
                },
                media_type="application/json",
            )

        if not request.thread_id or not request.thread_id.strip():
            # Generate a default thread_id if missing
            import uuid
            request.thread_id = str(uuid.uuid4())
            logger.warning(f"Missing thread_id, generated: {request.thread_id}")

        return ErrorHandlingStreamingResponse(
            safe_sse_stream(process_chat_stream(request.message, request.thread_id)),
            media_type="text/event-stream",
            status_code=status.HTTP_200_OK,
        )

    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        logger.error(f'user_question:{request.message}, error: {e}')
        logger.error(error_trace)

        async def error_stream():
            error_message = f"data: {json.dumps({'type': 'error', 'content': 'An unexpected error occurred. Please try again.'})}\n\n"
            yield error_message

        return ErrorHandlingStreamingResponse(
            error_stream(),
            media_type="text/event-stream"
        )