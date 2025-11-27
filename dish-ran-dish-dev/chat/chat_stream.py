import time
from langchain_core.messages import HumanMessage
from .chunks import process_chunks
import traceback
import json
from typing import AsyncGenerator, Dict, Optional
# from agent import ran_device_agent, supervisor_agent
# from agent.supervisor_agent import initialize_supervisor_agent
from agent import ran_device_agent, supervisor_agent, ran_pm_agent, ran_qa_agent
from utils.log_init import logger
from redis.asyncio.lock import Lock
from utils.redis_util import get_redis_client

from utils import constants as CONST
import asyncio

# from base_agent_asset import Telco_Agent
# from graph.ran_classifier_agent import initialize_agent as ran_classifier_agent
# from graph.ran_validator_agent import initialize_agent as ran_validator_agent
# from graph.gpl_classifier_agent import initialize_agent as gpl_classifier_agent
# from typing import List, Dict, Any, Optional, Union
# from utils.query_classifier_v2 import  extract_json_from_string

# # Global dictionary to store initialized agents
# AGENTS = {}

# # initialize agents 
# AGENTS["ran_device"] = ran_device_agent.initialize_ran_device_agent     
# AGENTS["supervisor"] = supervisor_agent.initialize_supervisor_agent

# async def _initialise_all_agents():
#     ran_device = await ran_device_agent.initialize_ran_device_agent()
#     supervisor = await supervisor_agent.initialize_supervisor_agent()
#     return {
#         "ran_device": ran_device,
#         "supervisor": supervisor
#     }

# # Synchronous wrapper to run async initialization at module load time
# def initialize_agents():
#     try:
#         # Get or create an event loop
#         loop = asyncio.get_event_loop()
#     except RuntimeError:
#         # Create a new event loop if none exists
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
    
#     # Run the async initialization
#     loop.run_until_complete(initialize_agents_async())

# # Call initialization at module load time
# initialize_agents()

supervisor_agent_runner = None
device_agent_runner = None
pm_agent_runner = None


# process chat stream - generic
async def process_chat_stream_supervisor(message: str, thread_id: str):
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
        # initialize agent
        global supervisor_agent_runner
        if supervisor_agent_runner is None:
            supervisor_agent_runner = await supervisor_agent.initialize_supervisor_agent()
            logger.info("supervisor agent initialized")
        # Start timing for the query response
        start_time = time.perf_counter()
        # print(f"##### --> streaming events")
        async for event in supervisor_agent_runner.astream_events(
                {"messages": [HumanMessage(content=message)]},
                {"recursion_limit": 10, "configurable": {"thread_id": thread_id}},
                version="v2"
        ):
            # Calculate response time (latency)
            response_time = time.perf_counter() - start_time

            # Handle custom events (Fixed version)
            if event["event"] == "on_custom_event":
                # Log the event structure for debugging
                logger.info(f"Custom event received: {event}")

                # The custom event structure might be different than expected
                # Let's handle both possible structures
                custom_event_data = event.get("data", {})

                # Structure 1: { "name": "event_name", "data": { ... } }
                if isinstance(custom_event_data, dict) and "name" in custom_event_data:
                    event_name = custom_event_data.get("name")
                    event_payload = custom_event_data.get("data", {})
                # Structure 2: Direct payload { "error": "...", "message": "..." }
                elif isinstance(custom_event_data, dict) and "error" in custom_event_data:
                    event_name = "llm_error"  # Assume it's an error event
                    event_payload = custom_event_data
                else:
                    # Unknown structure, log and skip
                    logger.warning(f"Unknown custom event structure: {custom_event_data}")
                    continue

                # Process llm_error events
                if event_name == "llm_error":
                    error_message = {
                        'type': 'text',
                        'content': event_payload.get("message",
                                                     "I encountered an error while invoking LLM. Please try again later."),
                    }
                    yield f"data: {json.dumps(error_message)}"
                    yield "\n\n"
                    continue

            await process_chunks(event)
            event_type = event["event"]
            metadata = event.get('metadata')
            if isinstance(metadata, dict):
                langgraph_node_value = metadata.get('langgraph_node')
            if event_type == "on_chat_model_stream" and langgraph_node_value == "llm":
                # Handle the main content streaming from the language model
                chunk = event["data"]["chunk"]
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                # print(f"##### --> content: {content}")
                item = {'type': 'text', 'content': content}
                yield f"data: {json.dumps(item)}"
                yield "\n\n"
    except Exception as e:
        logger.error(f"Error in streaming process: {str(e)}")
        logger.error(traceback.format_exc())
        error_message = {'type': 'error',
                         'content': "I encountered an issue while processing your request. Please try again."}
        yield f"data: {json.dumps(error_message)}"
        yield "\n\n"


# Device agent
async def process_chat_stream_device(message: str, thread_id: str):
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
        agent (str): relevant agent name

    Yields:
        str: Content chunks including model output and source information
    """
    try:
        # initialize agent
        global device_agent_runner
        if device_agent_runner is None:
            device_agent_runner = await ran_device_agent.initialize_ran_device_agent()
            logger.info("device agent initialized")

        # Start timing for the query response
        start_time = time.perf_counter()

        # print(f"##### --> streaming events")

        async for event in device_agent_runner.astream_events(
                {"messages": [HumanMessage(content=message)], "thread_id": thread_id},
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
                # print(f"##### --> content: {content}")
                item = {'type': 'text', 'content': content}
                yield f"data: {json.dumps(item)}"
                yield "\n\n"

    except Exception as e:
        logger.error(f"Error in streaming process: {str(e)}")
        logger.error(traceback.format_exc())
        error_message = {'type': 'error',
                         'content': "I encountered an issue while processing your request. Please try again."}
        yield f"data: {json.dumps(error_message)}"
        yield "\n\n"


# async def process_chat_stream_qa(message: str, thread_id: str):
#     """
#     Process chat messages using langgraph with streaming implementation that properly
#     handles ToolMessage events and appends sources as markdown HTML anchor tags after
#     the model stream completes.

#     The function processes events in this sequence:
#     1. Streams model content in real-time
#     2. Collects sources from ToolMessage events during streaming
#     3. Appends formatted source links after content streaming ends

#     Args:
#         message (str): The input message to process
#         thread_id (str): Unique identifier for the chat thread

#     Yields:
#         str: Content chunks including model output and source information
#     """
#     try:
#         # initialize agent
#         global pm_agent_runner
#         if pm_agent_runner is None:
#             pm_agent_runner = await ran_qa_agent.initialize_ran_qa_agent()
#             logger.info("QA agent initialized")

#         # Start timing for the query response
#         start_time = time.perf_counter()

#         # print(f"##### --> streaming events")

#         async for event in pm_agent_runner.astream_events(
#                 {"messages": [HumanMessage(content=message)], "thread_id": thread_id},
#                 {"recursion_limit": 10, "configurable": {"thread_id": thread_id}},
#                 version="v2"
#         ):
#             # Calculate response time (latency)
#             response_time = time.perf_counter() - start_time
#             await process_chunks(event)
#             event_type = event["event"]
#             metadata = event.get('metadata')
#             if isinstance(metadata, dict):
#                 langgraph_node_value = metadata.get('langgraph_node')

#             if event_type == "on_chat_model_stream" and langgraph_node_value == "llm":
#                 # Handle the main content streaming from the language model
#                 chunk = event["data"]["chunk"]
#                 content = chunk.content if hasattr(chunk, "content") else str(chunk)
#                 # print(f"##### --> content: {content}")
#                 item = {'type': 'text', 'content': content}
#                 yield f"data: {json.dumps(item)}"
#                 yield "\n\n"

#     except Exception as e:
#         logger.error(f"Error in streaming process: {str(e)}")
#         logger.error(traceback.format_exc())
#         error_message = {'type': 'error', 'content': "I encountered an issue while processing your request. Please try again."}
#         yield f"data: {json.dumps(error_message)}"
#         yield "\n\n"


# safe_sse_stream
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


async def stream_generator(error_message: str):
    """Generator function to create a streaming error response in SSE format"""
    yield f"data: {json.dumps({'type': 'text', 'content': error_message})}"


async def locked_safe_sse_stream(
        raw_gen: AsyncGenerator[bytes, None],
        lock: Optional[Lock] = None
) -> AsyncGenerator[bytes, None]:
    """
    Wraps the raw SSE bytes generator, catches all exceptions,
    and emits a final SSE-formatted error event instead of crashing.
    Also manages the lock lifecycle if provided.
    """
    try:
        async for chunk in raw_gen:
            yield chunk
    except Exception as e:
        traceback.print_exc()
        # Format an SSE 'error' event
        err_event = f"data: {json.dumps({'type': 'text', 'content': 'I encountered an issue while processing your request. Please try again.'})}"

        yield err_event.encode("utf-8")
    finally:
        # Release the lock if provided
        if lock:
            logger.info("lock is provided")
            try:
                logger.info("Attempting for Lock release after streaming completed")
                await get_redis_client().release_lock(lock)
                logger.info("Lock released after streaming completed")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")

        # Attempt to close the underlying generator if it supports aclose()
        close = getattr(raw_gen, "aclose", None)
        if close:
            await close()


