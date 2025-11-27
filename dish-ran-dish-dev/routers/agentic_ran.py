import asyncio
import logging
import threading
import time
from fastapi import APIRouter, status, Response
from routers.pydantic_model import ChatRequest,ChatResponse, ClassifyQueryResponse
from fastapi import HTTPException
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from graph.agent_graph_nodes import initialize_agent
from utils.network_agent_utils import process_chunks,process_chunks_non_streaming
from fastapi.responses import JSONResponse
from fastapi import status
import traceback
import json
from utils import constants as CONST, payload_logging, query_classifier
from utils.error_handling_streaming_response import ErrorHandlingStreamingResponse
from typing import AsyncGenerator, Union
import utils.constants as constant

log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")  # Replace 'RAN' with your app/module name


try:
    # Fetch environment variables
    url_for_pdf_links = os.environ["FILE_ENDPOINT"]
    WATSONX_MODEL_ID_MISTRAL_LARGE = os.environ["WATSONX_MODEL_ID_MISTRAL_LARGE"]
    RAN_1_SQL_AGENT_INST_SUB_ID = os.environ["RAN_1_SQL_AGENT_INST_SUB_ID"]
except Exception as e:
    print(e)
    logger.info("Loading Environmment Variables from local .env file")
    load_dotenv()
    url_for_pdf_links = os.environ["FILE_ENDPOINT"]
    WATSONX_MODEL_ID_MISTRAL_LARGE = os.environ["WATSONX_MODEL_ID_MISTRAL_LARGE"]
    RAN_1_SQL_AGENT_INST_SUB_ID = os.environ["RAN_1_SQL_AGENT_INST_SUB_ID"]

agentic_ran = APIRouter(prefix='/watsonx/ran', tags=['RAN Part - 1'])


'''async def process_chat_stream1(message: str, thread_id: str):
    langgraph_agent = await initialize_agent()
    async  for step in langgraph_agent.astream(
            {"messages": [HumanMessage(content=message)]},
            {"configurable": {"thread_id": thread_id}},
    ):
        for node, values in step.items():
            print(f"stream_response -> {node}")
            print(f"stream_response -> {values}")
            node_output = {"node": node}
            yield json.dumps(node_output).encode("utf-8") + b"\n\n"'''


async def process_chat(message: str, thread_id: str):
    langgraph_agent = await initialize_agent()
    full_response = []
    sources = []  # To store all sources

    async for step in langgraph_agent.astream(
            {"messages": [HumanMessage(content=message)]},
            {"recursion_limit": 10,
             "configurable": {"thread_id": thread_id}}
    ):
        await process_chunks_non_streaming(step)
        for node, values in step.items():
            logger.info("node------------", node)
            if node == 'tools' and "messages" in values:
                #print(values['messages'])
                # Process all messages instead of just the first one
                for tool_message in values['messages']:
                    logger.info("tool_message------------", tool_message)
                    tool_message_text = tool_message.content
                    # Extract sources from tool output
                    if isinstance(tool_message_text, str):
                        lines = tool_message_text.split('\n')
                        current_file = None
                        current_url = None

                        for line in lines:
                            if line.startswith('file_name ::'):
                                current_file = line.replace('file_name ::', '').strip()
                            #elif line.startswith('s3_source_URL ::'):
                                #current_url = line.replace('s3_source_URL ::', '').strip()
                                #if current_file and current_url:
                                    #sources.append((current_file, current_url))
                                sources.append(current_file)

            if node == 'agent' and "messages" in values:
                message = values['messages'][0]  # Note: Still taking first message here as per original
                content = message.content
                full_response.append(content)

    # Create the sources section with HTML anchor tags
    if sources:
        full_response.append("\n\n**Sources:**")
        # Remove duplicates while maintaining order
        unique_sources = list(dict.fromkeys(sources))
        for file_name in unique_sources:
            full_response.append(f'\n• <a href="https://icte-ui-icte.apps.watsonx.cpni-wl-dw-d.aws.dishcloud.io/ran/watsonx/ran/ran_open_file_v2?file_name={file_name}" target="_blank">{file_name}</a>')

    return "".join(full_response)

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
        # Format an SSE 'error' event
        err_event = f"event: error\n" + \
                    f"data: I encountered an issue: {str(e)}\n\n"
        yield err_event.encode("utf-8")
    finally:
        # Attempt to close the underlying generator if it supports aclose()
        close = getattr(raw_gen, "aclose", None)
        if close:
            await close()


async def process_chat_stream(message: str, thread_id: str):
    """
    Process chat messages using langgraph with streaming implementation that properly
    handles ToolMessage events and appends sources as markdown HTML anchor tags after
    the model stream completes.

    The function processes events in this sequence:
    1. Streams model content in real-time
    2. Collects sources from ToolMessage events during streaming
    3. Appends formatted source links after content streaming ends

    Args:
        message (str): The input message to process
        thread_id (str): Unique identifier for the chat thread

    Yields:
        str: Content chunks including model output and source information
    """
    try:
        langgraph_agent = await initialize_agent()
        first_chunk_processed = False  # Flag to track if the first chunk has been processed

        # Initialize our source collection to gather sources during streaming
        sources = []
        is_streaming_complete = False
        # Start timing for the query response
        start_time = time.perf_counter()

        async for event in langgraph_agent.graph.astream_events(
                {"messages": [HumanMessage(content=message)]},
                {"recursion_limit": 10, "configurable": {"thread_id": thread_id}},
                version="v2"
        ):
            # Calculate response time (latency)
            response_time = time.perf_counter() - start_time
            await process_chunks(event)
            event_type = event["event"]
            metadata = event.get('metadata')
            if isinstance(metadata, dict):
                langgraph_node_value = metadata.get('langgraph_node')

            if event_type == "on_chat_model_stream" and langgraph_node_value == "llm":
                # Handle the main content streaming from the language model
                chunk = event["data"]["chunk"]
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                item = {'type': 'text', 'content': content}
                yield f"data: {json.dumps(item)}"
                yield "\n\n"
                #yield content

            elif event_type == "on_tool_end":
                logger.info(event)
                # Extract source information from ToolMessage
                tool_output = event["data"]["output"]

                if isinstance(tool_output, str):
                    # Split content into lines, handling potential line breaks
                    lines = tool_output.split('\n')
                    current_file = None

                    for line in lines:
                        # Extract file name using string operations
                        if line.startswith('file_name ::'):
                            current_file = line.replace('file_name ::', '').strip()

                        # When we have file name, store them
                        if current_file:
                            source_tuple = (current_file)
                            if source_tuple not in sources:
                                sources.append(source_tuple)
                                # Reset for next pair
                                current_file = None

                # Log the payload after the first chunk is processed
                if not first_chunk_processed:
                    # Ensure flag is updated even if PAYLOAD_LOGGING is disabled
                    first_chunk_processed = True
                    if constant.PAYLOAD_LOGGING:
                        try:
                            # Schedule token counting and payload logging in background
                            async def _bg_payload_task():
                                """Background task for async token counting and payload logging"""
                                try:
                                    logger.info("Starting background payload logging task")

                                    # Log the payload information for RAG (Retrieve and Generate)
                                    request = {
                                        "tool_output": tool_output
                                    }
                                    
                                    llm_request = json.dumps(message)
                                    llm_response = json.dumps(content)

                                    # Run synchronous token counting in thread pool
                                    loop = asyncio.get_running_loop()
                                    input_token_count, generated_token_count = await asyncio.gather(
                                        loop.run_in_executor(
                                            None, 
                                            lambda: payload_logging.get_token_count(llm_request, WATSONX_MODEL_ID_MISTRAL_LARGE)
                                        ),
                                        loop.run_in_executor(
                                            None,
                                            lambda: payload_logging.get_token_count(llm_response, WATSONX_MODEL_ID_MISTRAL_LARGE)
                                        )
                                    )

                                    # Async payload logging
                                    await payload_logging.store_rag_payload_record(
                                        request,
                                        content,
                                        input_token_count,
                                        generated_token_count,
                                        response_time,
                                        RAN_1_SQL_AGENT_INST_SUB_ID,
                                        message
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
                            logger.error(f"Error scheduling background task: {str(e)}")

            elif event_type == "on_chain_end":
                # Mark streaming as complete when the chain ends
                is_streaming_complete = True

        # After all streaming is complete, append sources if we have any
        if is_streaming_complete and sources:
            # Add formatting for the sources section
            source_item = {'type': 'text', 'content': "\n\n**Sources:**\n"}
            yield f"data: {json.dumps(source_item)}"
            yield "\n\n"

            # Generate and yield source links individually
            for file_name in sources:
                # Format each source as a markdown bullet point with HTML anchor tag
                source_link = f'• <a href="{url_for_pdf_links}{file_name}" target="_blank">{file_name}</a>\n'
                source_file_item = {'type': 'text', 'content': source_link}
                yield f"data: {json.dumps(source_file_item)}"
                yield "\n\n"

    except Exception as e:
        logger.error(f"Error in streaming process: {str(e)}")
        logger.error(traceback.format_exc())
        error_message = {'type': 'error', 'content': "I encountered an issue while processing your request. Please try again."}
        yield f"data: {json.dumps(error_message)}"
        yield "\n\n"

@agentic_ran.post(
    "/agentic_ran",
    summary="RAN AI Assistant - Agentic RAG implementation",
    status_code=status.HTTP_200_OK,
    response_description="Answer for the user question from Watson Discovery using ReAct model",
    response_class=JSONResponse,
)
async def query_user_question(request: ChatRequest):
    """
    ### RAN AI Assistant - Agentic RAG implementation
    Query the Watson Discovery for the user question:
    **Input:**
    - user_question: questions from the user

    **Output:**
    - A response for the user question
    """
    logger.info(f'user_question: {request.message}')
    try:
        response = await process_chat(request.message, request.thread_id)
        logger.info(f'final response: {response}')
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"response": response},
            media_type="application/json",
        )
    except Exception as e:
        traceback.print_exc()
        logger.error(f'user_question: {request.message}, error: {e} - query : ERROR')
        raise HTTPException(
            status_code=500, detail=f"Error occurred: {str(e)}"
        )



@agentic_ran.post(
    "/agentic_ran_stream",
    summary="RAN AI Assistant - Agentic RAG implementation",
    status_code=status.HTTP_200_OK,
    response_description="Answer for the user question from watson discovery using ReAct model",
)
async def query_user_question(request: ChatRequest):
    """
     ### RAN AI Assistant - Agentic RAG implementation
    Query the watson discovery for the user question:
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
        error_trace = traceback.format_exc()
        logger.error(f'user_question:{request.message}, error: {e}')
        logger.error(error_trace)

        # Create a streaming response with error message
        # Create a streaming response with error message as a string
        async def error_stream():
            yield "I encountered an issue while processing your request. Please try again."

        return ErrorHandlingStreamingResponse(
            error_stream(),
            media_type="text/event-stream"
        )

@agentic_ran.post(
    "/classify_query",
    summary="Classify a user's query into a predefined category",
    status_code=status.HTTP_200_OK,
    response_description="Classification result including category",
    response_model=ClassifyQueryResponse,
)
async def query_user_question(request: ChatRequest):
    """
    Classifies a user query into a predefined category based on the content of the message.

    This endpoint accepts a user message and conversation thread ID, then uses a language model
    and conversation history to predict the most relevant category.

    Parameters:
    - request (ChatRequest): Contains the `message` (user query) and `thread_id` (conversation identifier).

    Returns:
    - dict: {
        "classification": str,
      }

    Raises:
    - HTTPException: Returns a 500 error if classification fails.
    """
    logger.info(f'user_question:{request.message}')
    try:
        result = await query_classifier.process_user_query(request.thread_id, request.message)

        # Find the key corresponding to the result value
        result_key = next((k for k, v in CONST.CATEGORY_MAPPING.items() if v == result), None)

        return ClassifyQueryResponse(classification = result_key)
    except Exception as e:
        logger.error(f'user_question:{request.message}, error: {e} - query : ERROR')
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")
