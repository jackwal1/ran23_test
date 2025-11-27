import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, status, HTTPException
from fastapi.responses import JSONResponse
import utils.memory_checkpoint as memory_setup
# from uuid import uuid4
import platform
import asyncio
import re
from utils.error_handling_streaming_response import ErrorHandlingStreamingResponse
from utils import user_id_injection
from chat.pydantic_model import ChatRequest, SupervisorChatRequest, kpiReadoutRequest, kpiReadoutAnalysisRequest, \
    kpiReadoutDataCollectionResponse, EmailRequest, AoiResponse, kpiReadoutDataCollectionRequest
from chat.chat_stream import safe_sse_stream, locked_safe_sse_stream, stream_generator, process_chat_stream_supervisor, process_chat_stream_device
from utils.ran_kpi_readout.kpi_main import collect_kpi_data
# from chat.message_stream import process_chat_stream_supervisor, process_chat_stream_device
import traceback
from utils.log_init import logger
from llms.llms import analyze_kpi_readout
from utils.get_distinct_aoi_by_email import get_distinct_aoi_by_email
from utils import constants as CONST
from routers import ran_open_file_v2
from utils.redis_util import get_redis_client
import io
from concurrent.futures import ThreadPoolExecutor
import textwrap
import os

# Initialize FastAPI
app = FastAPI(root_path="/ran")
# for opening files
app.include_router(ran_open_file_v2.ranQueryopenfilev2)

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://loclhost:3000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


##############################
# RAN Supervisor
##############################

@app.post(
    "/watsonx/ran/agentic_ran_supervisor",
    summary="RAN AI Assistant - Supervisor",
    status_code=status.HTTP_200_OK,
    response_description="Answer for the user question",
    tags=['RAN']
)
async def query_ran_supervisor(request: SupervisorChatRequest):
    """
     ### RAN AI Assistant - Agentic RAG implementation
    **Input:**
    - user_question: questions from the user

    **Output:**
    - A response for the user question
    """
    logger.info(f'user_question:{request.message}')
    logger.info(f'user ID:{request.user_id}')

    # Generate thread_id if missing
    if not request.thread_id or not request.thread_id.strip():
        request.thread_id = str(uuid.uuid4())
        logger.warning(f"Missing thread_id, generated: {request.thread_id}")

    lock_name = f"thread_lock:{request.thread_id}"
    lock = None
    acquired = False

    try:
        # Get the lock object from our existing Redis client
        redis_client = get_redis_client()
        lock = await redis_client.get_lock(lock_name, timeout=CONST.LOCK_TIMEOUT)




        # Attempt to acquire the lock with retries
        start_time = asyncio.get_event_loop().time()
        while True:
            # Check if we've exceeded the acquisition timeout
            if (asyncio.get_event_loop().time() - start_time) > CONST.LOCK_ACQUIRE_TIMEOUT:
                raise Exception(f"Could not acquire lock for thread {request.thread_id} within timeout")

            # Try to acquire the lock (non-blocking)
            acquired = await lock.acquire(blocking=False)

            if acquired:
                break

            # Wait before retrying
            await asyncio.sleep(CONST.LOCK_RETRY_DELAY)

        logger.info(f"Acquired lock for thread {request.thread_id}")

        try:
            # Cache user session if needed
            if request.user_id and request.thread_id:
                logger.info("Caching user Id in Redis...... ")
                await user_id_injection.register_user_session(request.thread_id, request.user_id)

            # Validate input
            if not request.message or not request.message.strip():
                # We need to release the lock and return an error
                await redis_client.release_lock(lock)
                return ErrorHandlingStreamingResponse(
                    stream_generator("Please provide a valid question."),
                    media_type="text/event-stream",
                    status_code=200,
                )

            return ErrorHandlingStreamingResponse(
                locked_safe_sse_stream(process_chat_stream_supervisor(request.message, request.thread_id), lock),
                media_type="text/event-stream",
                status_code=200,
            )

        except Exception as e:
            # If an error occurs during processing, release the lock and return error
            if lock and acquired:
                try:
                    await redis_client.release_lock(lock)
                except Exception as release_error:
                    logger.error(f"Error releasing lock: {release_error}")

            error_trace = traceback.format_exc()
            logger.error(f'user_question:{request.message}, error: {e}')
            logger.error(error_trace)

            return ErrorHandlingStreamingResponse(
                stream_generator("I encountered an issue while processing your request. Please try again."),
                media_type="text/event-stream",
                status_code=200,
            )
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f'user_question:{request.message}, error: {e}')
        logger.error(error_trace)

        return ErrorHandlingStreamingResponse(
            stream_generator("I encountered an issue while processing your request. Please try again."),
            media_type="text/event-stream"
        )


##############################
# RAN DEVICE
##############################

# ran_device = APIRouter(prefix='/watsonx/ran', tags=['RAN Device'])

@app.post(
    "/watsonx/ran/agentic_ran_device_stream",
    summary="RAN AI Assistant - Agentic RAG implementation",
    status_code=status.HTTP_200_OK,
    response_description="Answer for the user question from watson discovery using ReAct model",
    tags=['RAN Device']
)
async def query_ran_device(request: ChatRequest):
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
            request.thread_id = str(uuid.uuid4())
            logger.warning(f"Missing thread_id, generated: {request.thread_id}")

        return ErrorHandlingStreamingResponse(
            safe_sse_stream(process_chat_stream_device(request.message, request.thread_id)),
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


##############################
# RAN PM
##############################

# @app.post(
#     "/watsonx/ran/agentic_ran_pm",
#     summary="RAN AI Assistant - Agentic RAG implementation",
#     status_code=status.HTTP_200_OK,
#     response_description="Answer for the user question from watson discovery using ReAct model",
#     tags=['RAN PM']
# )
# async def query_ran_pm(request: ChatRequest):
#     """
#      ### RAN AI Assistant - Agentic RAG implementation
#     Query the watson discovery for the user question:
#     **Input:**
#     - user_question: questions from the user

#     **Output:**
#     - A response for the user question
#     """
#     logger.info(f'user_question:{request.message}')
#     try:
#         # Validate input
#         if not request.message or not request.message.strip():
#             return JSONResponse(
#                 status_code=status.HTTP_200_OK,
#                 content={
#                     "response": "Please provide a valid question.",
#                     "status": "error",
#                     "error_code": "EMPTY_INPUT"
#                 },
#                 media_type="application/json",
#             )

#         if not request.thread_id or not request.thread_id.strip():
#             # Generate a default thread_id if missing
#             request.thread_id = str(uuid.uuid4())
#             logger.warning(f"Missing thread_id, generated: {request.thread_id}")

#         return ErrorHandlingStreamingResponse(
#             safe_sse_stream(process_chat_stream_pm(request.message, request.thread_id)),
#             media_type="text/event-stream",
#             status_code=status.HTTP_200_OK,
#         )

#     except Exception as e:
#         error_trace = traceback.format_exc()
#         logger.error(f'user_question:{request.message}, error: {e}')
#         logger.error(error_trace)

#         # Create a streaming response with error message
#         # Create a streaming response with error message as a string
#         async def error_stream():
#             yield "I encountered an issue while processing your request. Please try again."

#         return ErrorHandlingStreamingResponse(
#             error_stream(),
#             media_type="text/event-stream"
#         )

##############################
# RAN KPI Readout
##############################

# @app.post(
#     "/watsonx/ran/kpi_readout",
#     summary="RAN AI Assistant - KPI Readout",
#     status_code=status.HTTP_200_OK,
#     response_description="Answer for the user question from watson discovery using ReAct model",
#     tags=['RAN KPI Readout']
# )
# async def ran_kpi_readout(request: kpiReadoutRequest):
#     """
#      ### RAN AI Assistant - Agentic RAG implementation
#     KPI Readout for the user question:
#     **Input:**
#     - user_question: questions from the user
#
#     **Output:**
#     - A response for the user question
#     """
#     logger.info(f'aoi: {request.aoi}')
#     try:
#         # Validate input
#         _AOI_RE = re.compile(r'^[A-Z]{3}$')
#         is_aoi_match = bool(_AOI_RE.fullmatch(request.aoi.strip().upper()))
#         if not is_aoi_match:
#             return JSONResponse(
#                 status_code=status.HTTP_200_OK,
#                 content={
#                     "response": "Please provide a valid AOI, a three letter keyword.",
#                     "status": "error",
#                     "error_code": "INVALID_INPUT"
#                 },
#                 media_type="application/json",
#             )
#
#         return ErrorHandlingStreamingResponse(
#             safe_sse_stream(kpi_readout(request.aoi, request.engineer)),
#             media_type="text/event-stream",
#             status_code=status.HTTP_200_OK,
#         )
#
#     except Exception as e:
#         error_trace = traceback.format_exc()
#         logger.error(f'user_question:{request.message}, error: {e}')
#         logger.error(error_trace)
#
#         # Create a streaming response with error message
#         # Create a streaming response with error message as a string
#         async def error_stream():
#             yield "I encountered an issue while processing your request. Please try again."
#
#         return ErrorHandlingStreamingResponse(
#             error_stream(),
#             media_type="text/event-stream"
#         )

import time
import re
import uuid
import json
import asyncio
import traceback
from datetime import datetime


@app.post(
    "/watsonx/ran/kpi_readout/data_collection",
    summary="RAN AI Assistant - KPI Data Collection",
    status_code=status.HTTP_200_OK,
    response_description="Streamed response with progress updates and final result",
    tags=['RAN KPI Readout'],
)
async def ran_kpi_readout_data_collection(request: kpiReadoutDataCollectionRequest):
    """
    ### RAN AI Assistant - Data Collection
    Collects KPI data and stores it in Redis cache for later analysis:
    **Input:**
    - aoi: Area of Interest (3 letter code)
    - engineer: Engineer identifier
    **Output:**
    - A streaming response with progress updates and final result
    """
    logger.info(f'aoi: {request.aoi}')

    async def generate_response():
        try:
            # Track start time for elapsed calculation
            start_time = time.time()
            # Emit start event (normal text)
            yield create_text_event("Starting data collection process...")
            yield "\n\n"


            # Validate input
            _AOI_RE = re.compile(r'^[A-Z]{3}$')
            is_aoi_match = bool(_AOI_RE.fullmatch(request.aoi.strip().upper()))
            if not is_aoi_match:
                yield create_text_event("Please provide a valid AOI, a three letter keyword.")
                yield "\n\n"
                return

            # Emit validation success (normal text)
            yield create_text_event("AOI validation successful")
            yield "\n\n"

            # Emit validation success (normal text)
            yield create_text_event("Please wait while we are collecting KPI data from sources")
            yield "\n\n"

            # Generate a unique key
            key = str(uuid.uuid4())
            logger.info(f'key: {key}')


            # Create a task for data collection
            data_task = asyncio.create_task(collect_kpi_data(request.aoi, request.engineer))

            # Counter for progress messages
            progress_count = 0

            # Periodically check if data collection is complete
            while not data_task.done():

                progress_count += 1
                elapsed_time = int(time.time() - start_time)

                # Emit progress message with elapsed time
                if progress_count % 100 == 0:
                    # Every 10th message: emit as blockquote event
                    yield create_text_event(
                        f"Still collecting data for AOI: {request.aoi}... (Elapsed: {elapsed_time}s)"
                    )
                    yield "\n\n"
                else:
                    yield create_text_event("")
                    yield "\n\n"

                # Wait for 2 seconds before next check
                try:
                    await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    # Task was cancelled, handle appropriately
                    yield create_text_event("Data collection was cancelled")
                    yield "\n\n"
                    return

            # Check if the task completed successfully or with an exception
            if data_task.exception():
                # Task raised an exception
                exc = data_task.exception()
                logger.error(f'Data collection failed with exception: {exc}')
                yield create_text_event(f"Data collection failed: {str(exc)}")
                yield "\n\n"
                return

            # Get the result from the completed task
            data = data_task.result()
            logger.info(f'Collecting data Completed.....')

            # Emit data collection completion (blockquote)
            yield create_text_event("Successfully collected all KPI data")
            yield "\n\n"

            # Get Redis client
            redis_client = get_redis_client()

            # Create a value object with all necessary information
            cache_value = {
                "data": data,
                "aoi": request.aoi,
                "engineer": request.engineer,
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f'cache_value: {cache_value}')

            # Emit data preparation (blockquote)
            yield create_text_event("Preparing data for storage")
            yield "\n\n"

            # Store in Redis with expiry time (1 hour)
            await redis_client.set(
                key,
                json.dumps(cache_value),
                expire_seconds=3600  # 1 hour in seconds
            )
            logger.info(f'Data stored in redis with 1 hr expiry')

            # Emit storage completion (blockquote)
            yield create_text_event("Data stored in cache with 1 hour expiry")
            yield "\n\n"

            # Stream success response with key (blockquote for key message)
            yield create_text_event(f"key generated: ({key}).")
            yield "\n\n"

            # Stream final success message (normal text)
            yield create_text_event("Data collected successfully.")
            yield "\n\n"

        except asyncio.CancelledError:
            # Handle client disconnect
            logger.info("Client disconnected during data collection")
            yield create_text_event("Data collection was cancelled due to client disconnect")
            yield "\n\n"
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f'aoi:{request.aoi}, error: {e}')
            logger.error(error_trace)

            # Stream error response (normal text)
            yield create_text_event("I encountered an issue while processing your request. Please try again.")
            yield "\n\n"
    def create_text_event(content):
        """Helper function to create a normal text event"""
        event = {
            'type': 'text',
            'content': content + "\n"
        }
        return f"data: {json.dumps(event)}"

    def create_blockquote_event(content):
        """Helper function to create a blockquote event using markdown >"""
        event = {
            'type': 'text',
            'content': f"> {content}"
        }
        return f"data: {json.dumps(event)}"

    return ErrorHandlingStreamingResponse(
        generate_response(),
        media_type="text/event-stream"
    )



def extract_uuid_v4(input_string: str) -> str:
    """
    Extracts the first UUID v4 from a string.
    Returns the UUID string (lowercase) if found, raises ValueError otherwise.
    """
    uuid_pattern = re.compile(
        r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',
        re.IGNORECASE
    )
    match = uuid_pattern.search(input_string)
    if not match:
        raise ValueError("UUID v4 not found in the input string")
    return match.group(0).lower()


@app.post(
    "/watsonx/ran/kpi_readout_analysis",
    summary="RAN AI Assistant - KPI Readout Analysis",
    status_code=status.HTTP_200_OK,
    response_description="RAN AI Assistant - KPI Readout Analysis",
    tags=['RAN KPI Readout']
)
async def ran_kpi_readout_analysis(request: kpiReadoutAnalysisRequest):
    """
    ### RAN AI Assistant - KPI Analysis
    Analyzes previously cached KPI data:
    **Input:**
    - key: String containing a UUID from the data collection endpoint
    **Output:**
    - A streaming response with the analysis
    """
    try:
        # Extract UUID v4 from request.key
        try:
            redis_key = extract_uuid_v4(request.key)
            logger.info(f"Extracted UUID v4 from request: {redis_key}")
        except ValueError as e:
            logger.warning(f"Failed to extract UUID from request key: {request.key} - {str(e)}")

            async def error_stream():
                error_message = {
                    'type': 'text',
                    'content': f"Invalid request key format: {request.key}. Expected a UUID v4."
                }
                yield f"data: {json.dumps(error_message)}"
                yield "\n\n"

            return ErrorHandlingStreamingResponse(
                error_stream(),
                media_type="text/event-stream"
            )

        # Get Redis client
        redis_client = get_redis_client()

        # Retrieve data from Redis using extracted UUID
        logger.info(f"Retrieving KPI data from cache for analysis - Key: {redis_key}")
        cached_data = await redis_client.get(redis_key)

        if cached_data is None:
            logger.warning(f"Data not found in cache for key: {redis_key}")

            async def error_stream():
                error_message = {
                    'type': 'text',
                    'content': f"Data not found in cache for key: {redis_key}"
                }
                yield f"data: {json.dumps(error_message)}"
                yield "\n\n"

            return ErrorHandlingStreamingResponse(
                error_stream(),
                media_type="text/event-stream"
            )

        # Parse JSON data
        cache_value = json.loads(cached_data)
        data = cache_value["data"]
        logger.info(f"Retrieved KPI data from cache for analysis - Data: {data}")

        # Remove data from cache after retrieval
        # try:
        #     await redis_client.client.delete(redis_key)
        #     logger.info(f"Successfully removed KPI data from cache for key: {redis_key}")
        # except Exception as delete_error:
        #     logger.error(f"Failed to remove data from cache for key {redis_key}: {str(delete_error)}")
        #     # Continue with analysis even if deletion fails

        # Stream analysis
        return ErrorHandlingStreamingResponse(
            analyze_kpi_readout(data, redis_key),
            media_type="text/event-stream",
            status_code=status.HTTP_200_OK,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f'key:{request.key}, error: {e}')
        logger.error(error_trace)

        # Create a streaming response with error message
        async def error_stream():
            error_message = {
                'type': 'text',
                'content': "I encountered an issue while processing your request. Please try again."
            }
            yield f"data: {json.dumps(error_message)}"
            yield "\n\n"

        return ErrorHandlingStreamingResponse(
            error_stream(),
            media_type="text/event-stream"
        )

##############################
# RAN AOI IDENTIFIER
##############################

@app.post(
    "/watsonx/ran/get_aoi_by_email",
    tags=["AOI_IDENTIFIER"],
    operation_id="get_aoi_by_email",
    summary="Retrieve distinct AOI values associated with a user email",
    status_code=status.HTTP_200_OK,
    response_description="Returns distinct AOI values associated with the user extracted from email",
    response_model=AoiResponse,
)
async def get_aoi_by_email(request: EmailRequest) -> AoiResponse:
    """
    AOI Identifier by Email
    This tool identifies distinct AOI (Area of Interest) values associated with a user's name extracted from their email address.

    The email address is processed to extract the name part (before '@'), clean it, and create search conditions.
    The search is case-insensitive and matches both full names and individual name components.

    REQUIRED PARAMETERS:
    - email: Valid email address (e.g., 'first_name.last_name@dish.com')

    RESPONSE FORMAT:
    {
        "status": "success",      // Either "success" or "fail"
        "message": "Success message", // Description of the result
        "aoi": ["AOI1", "AOI2"],   // List of distinct AOI values (only when status is "success")
        "engineer": "XYZ"
    }

    USE CASES:
    1. Find AOI for a user: {"email": "first_name.last_name@dish.com"}
    """
    logger.info(f"Processing request for email: {request.email}")

    try:
        # Call the function to get AOI values
        result = await get_distinct_aoi_by_email(request.email)

        # Check if we got valid results
        if result.get("aoi") and len(result.get("aoi")) > 0:
            return AoiResponse(
                status="success",
                message=result.get("message", "AOI values retrieved successfully"),
                aoi=result.get("aoi"),
                engineer=result.get("engineer"),
                total_count=len(result.get("aoi"))
            )
        else:
            # No AOI found - this is considered a failure
            return AoiResponse(
                status="fail",
                message=result.get("message", "No AOI found for the provided email")
            )

    except Exception as e:
        error_msg = f"System error during AOI identification: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")

        return AoiResponse(
            status="fail",
            message=error_msg
        )


@app.get(
    "/watsonx/ran/markdown_to_pdf",
    summary="Convert Markdown to PDF",
    status_code=status.HTTP_200_OK,
    response_description="Returns a PDF file converted from Markdown content",
    tags=['PDF Generation']
)
async def markdown_to_pdf(key: str):
    """
    ### Markdown to PDF Converter
    Fetches Markdown content from Redis using the provided key and converts it to a PDF file.

    **Input:**
    - key: Redis key to fetch Markdown content
    - logo_path: Optional path to logo file (supports PNG, JPG, SVG)

    **Output:**
    - A PDF file stream converted from the Markdown content
    """
    logger.info(f"Converting Markdown to PDF for key: {key}")

    try:
        # Get Redis client
        redis_client = get_redis_client()

        # Retrieve Markdown content from Redis
        logger.info(f"Retrieving Markdown content from Redis - Key: {key}")
        markdown_content = await redis_client.get(key)

        if markdown_content is None:
            logger.warning(f"Markdown content not found in Redis for key: {key}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Content not found for key: {key}"
            )

        logger.info(f"Retrieved Markdown content from Redis - Length: {len(markdown_content)}")

        # Define synchronous conversion function using markdown-pdf and PyMuPDF
        def convert_markdown_to_pdf(markdown_text: str, logo_path: str = None) -> bytes:
            """Convert Markdown to PDF with professional styling and add logo using PyMuPDF."""

            try:
                # Add missing import
                import tempfile

                # ------------------------
                # 1) Preprocessing
                # ------------------------
                # Remove common leading indentation from triple-quoted strings
                markdown_text = textwrap.dedent(markdown_text).lstrip('\n')

                # Normalize lines: strip trailing whitespace only
                markdown_text = '\n'.join(line.rstrip() for line in markdown_text.splitlines())

                # If the first non-empty line is bold-only, convert to H1
                lines = markdown_text.split('\n')
                for i, ln in enumerate(lines):
                    if ln.strip() == '':
                        continue
                    s = ln.strip()
                    if s.startswith('**') and s.endswith('**') and len(s) > 4:
                        content = s.strip('*').strip()
                        lines[i] = '# ' + content
                    break
                markdown_text = '\n'.join(lines)

                # ------------------------
                # 2) Create PDF with MarkdownPdf
                # ------------------------
                from markdown_pdf import MarkdownPdf, Section

                # Auto-detect wide tables (≥5 visible columns)
                lines_for_detection = [ln.strip() for ln in markdown_text.splitlines()]
                has_wide_table = False
                max_columns = 0
                for line in lines_for_detection:
                    if line.startswith('|') and line.endswith('|'):
                        parts = [p.strip() for p in line.split('|')[1:-1]]
                        visible_cols = len([p for p in parts if p != ''])
                        if visible_cols > max_columns:
                            max_columns = visible_cols
                        if visible_cols >= 5:
                            has_wide_table = True

                # Check if the content starts with a level 1 heading for TOC generation
                has_level1_heading = any(line.startswith('# ') for line in lines_for_detection)
                toc_level = 2 if has_level1_heading else 0

                pdf = MarkdownPdf(toc_level=toc_level)

                # ------------------------
                # 3) CSS - Standard margins (will be adjusted in PyMuPDF)
                # ------------------------
                css = """
                    /* Basic page setup - standard margins (will be adjusted in PyMuPDF) */
                    @page {
                        size: A4;
                        margin: 20px; /* Small margin, content will be repositioned in PyMuPDF */
                    }

                    /* Body styling */
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                        line-height: 1.5;
                        color: #2d3748;
                        margin: 0;
                        padding: 0;
                        font-size: 12px;
                        background: white;
                    }

                    /* Headings */
                    h1, h2, h3, h4, h5, h6 {
                        color: #1a202c;
                        margin-top: 24px;
                        margin-bottom: 12px;
                        font-weight: 600;
                    }

                    h1 { 
                        font-size: 24px; 
                        border-bottom: 2px solid #1a202c; 
                        padding-bottom: 10px; 
                        margin-top: 0;
                    }
                    h2 { 
                        font-size: 20px; 
                        border-bottom: 1px solid #e2e8f0; 
                        padding-bottom: 8px; 
                    }
                    h3 { 
                        font-size: 16px; 
                    }

                    /* Paragraphs and lists */
                    p, ul, ol { 
                        margin: 0 0 16px 0;
                    }

                    /* Tables */
                    table {
                        width: 100%;
                        border-collapse: collapse;
                        border-spacing: 0;
                        font-size: 11px;
                        margin: 20px 0;
                    }

                    th, td {
                        border: 1px solid #e2e8f0;
                        padding: 4px;
                        text-align: left;
                        vertical-align: top;
                    }

                    th {
                        font-weight: 600;
                        color: #2d3748;
                        border-bottom: 2px solid #cbd5e0;
                    }

                    /* Enhanced table pagination */
                    thead {
                        display: table-header-group;
                    }

                    tbody {
                        display: table-row-group;
                    }

                    tr {
                        page-break-inside: avoid;
                        page-break-after: auto;
                    }

                    /* Code blocks */
                    pre {
                        background-color: #f7fafc;
                        border: 1px solid #e2e8f0;
                        border-radius: 4px;
                        padding: 12px;
                        overflow: auto;
                        font-size: 10px;
                        margin: 16px 0;
                        page-break-inside: avoid;
                    }

                    code {
                        font-family: 'Courier New', monospace;
                        background-color: rgba(27,31,35,0.05);
                        border-radius: 3px;
                        padding: 0.2em 0.4em;
                        font-size: 0.9em;
                    }

                    /* Horizontal rule */
                    hr {
                        border: 0;
                        height: 1px;
                        background: #e2e8f0;
                        margin: 24px 0;
                    }

                    /* Blockquotes */
                    blockquote {
                        margin: 0;
                        padding: 0 16px;
                        color: #4a5568;
                        border-left: 4px solid #cbd5e0;
                    }

                    /* Strong text */
                    strong, b {
                        font-weight: 600;
                    }

                    /* Emphasized text */
                    em, i {
                        font-style: italic;
                    }
                """

                # Choose paper size based on table width
                if max_columns >= 7:
                    paper_size = "A3"  # Use A3 for very wide tables
                elif has_wide_table:
                    paper_size = "A4-L"  # Landscape for moderately wide tables
                else:
                    paper_size = "A4"  # Portrait for narrow tables

                section = Section(markdown_text, paper_size=paper_size)
                pdf.add_section(section, user_css=css)

                # metadata
                pdf.meta["title"] = "KPI Analysis Report"
                pdf.meta["author"] = "IBM watsonx RAN agent"
                pdf.meta["subject"] = "RAN Performance Analysis"
                pdf.meta["keywords"] = "KPI, RAN, Performance, Analysis"

                # Generate PDF into bytes
                output = io.BytesIO()
                pdf.save_bytes(output)
                pdf_bytes = output.getvalue()

                # ------------------------
                # 4) Add header, footer, lines, and reposition content using PyMuPDF
                # ------------------------
                if logo_path and os.path.exists(logo_path):
                    try:
                        import pymupdf

                        # Create temporary files for processing
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
                            tmp_pdf.write(pdf_bytes)
                            tmp_pdf_path = tmp_pdf.name

                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as out_pdf:
                            out_pdf_path = out_pdf.name

                        # Add header, footer, lines, and reposition content
                        restructure_pdf_with_header_footer(
                            input_pdf_path=tmp_pdf_path,
                            output_pdf_path=out_pdf_path,
                            logo_image_path=logo_path,
                            title="KPI Analysis Report"  # Pass the title explicitly
                        )

                        # Read the modified PDF
                        with open(out_pdf_path, 'rb') as f:
                            pdf_bytes = f.read()

                        # Clean up temporary files
                        os.unlink(tmp_pdf_path)
                        os.unlink(out_pdf_path)

                        logger.info(f"PDF restructured with header/footer successfully")

                    except Exception as e:
                        logger.warning(f"Failed to restructure PDF with header/footer: {str(e)}")
                    finally:
                        # Clean up temporary files (this will run even if an exception occurs)
                        # Check if file exists before attempting to delete
                        if os.path.exists(tmp_pdf_path):
                            try:
                                os.unlink(tmp_pdf_path)
                            except Exception as e:
                                logger.warning(f"Failed to delete temporary file {tmp_pdf_path}: {str(e)}")

                        if os.path.exists(out_pdf_path):
                            try:
                                os.unlink(out_pdf_path)
                            except Exception as e:
                                logger.warning(f"Failed to delete temporary file {out_pdf_path}: {str(e)}")

                return pdf_bytes

            except Exception as e:
                logger.error(f"Error in PDF conversion: {str(e)}")
                logger.error(traceback.format_exc())
                raise Exception(f"PDF conversion failed: {str(e)}")

        # Function to restructure PDF with header/footer and reposition content
        def restructure_pdf_with_header_footer(input_pdf_path, output_pdf_path, logo_image_path,
                                               title="KPI Analysis Report"):
            """
            Creates a new PDF with proper header/footer layout and repositions existing content.
            Preserves the original PDF metadata and ensures the title is set correctly.

            This approach completely rebuilds each page to ensure no overlap:
            1. Creates a new blank page
            2. Adds header elements (logo, text, line)
            3. Copies original content but shifts it down to make room for header
            4. Adds footer elements (line, text, page numbers)

            Args:
                input_pdf_path (str): Path to the input PDF file.
                output_pdf_path (str): Path to save the output PDF file.
                logo_image_path (str): Path to the logo image file.
                title (str): Title to set in the PDF metadata.
            """
            import pymupdf

            # Open the original PDF
            original_doc = pymupdf.open(input_pdf_path)

            # Get the metadata from the original document
            original_metadata = original_doc.metadata

            # Create a new PDF document
            new_doc = pymupdf.open()

            # Update the title in the metadata
            original_metadata['title'] = title

            # Set the updated metadata in the new document
            new_doc.set_metadata(original_metadata)

            # Define layout dimensions (in points)
            header_height = 70  # Total header area height
            header_line_y = 65  # Header line position
            content_start_y = 50  # Where content should start
            footer_height = 90  # Total footer area height
            footer_line_y = None  # Will be calculated based on page height
            content_end_y = None  # Will be calculated based on page height
            line_margin = 20
            line_width = 1.0

            # Process each page
            for page_num in range(original_doc.page_count):
                original_page = original_doc[page_num]
                page_rect = original_page.rect

                # Calculate footer position based on page height
                footer_line_y = page_rect.height - footer_height + 15  # 20 points from bottom of footer area
                content_end_y = footer_line_y - 1  # Content ends 1 points above footer line

                # Create a new page in the new document
                new_page = new_doc.new_page(width=page_rect.width, height=page_rect.height)

                # Draw header line (separates header from content)
                header_line_start = pymupdf.Point(line_margin, header_line_y)
                header_line_end = pymupdf.Point(page_rect.width - line_margin, header_line_y)

                try:
                    new_page.draw_line(header_line_start, header_line_end, width=line_width, color=(0, 0, 0))
                except Exception as e:
                    logger.warning(f"Failed to draw header line on page {page_num + 1}: {str(e)}")

                # Draw footer line (separates content from footer)
                footer_line_start = pymupdf.Point(line_margin, footer_line_y)
                footer_line_end = pymupdf.Point(page_rect.width - line_margin, footer_line_y)

                try:
                    new_page.draw_line(footer_line_start, footer_line_end, width=line_width, color=(0, 0, 0))
                except Exception as e:
                    logger.warning(f"Failed to draw footer line on page {page_num + 1}: {str(e)}")

                # Add logo to header area
                if logo_image_path:
                    logo_width = 80
                    logo_height = 25
                    logo_margin = 20

                    # Position logo in top-right corner of header area
                    logo_x = page_rect.width - logo_width - logo_margin
                    logo_y = (header_height - logo_height) / 2  # Center vertically in header area

                    logo_rect = pymupdf.Rect(logo_x, logo_y, logo_x + logo_width, logo_y + logo_height)

                    # Try multiple approaches to insert the logo
                    logo_inserted = False

                    # Approach 1: insert_image method
                    try:
                        if hasattr(new_page, 'insert_image'):
                            new_page.insert_image(logo_rect, filename=logo_image_path, overlay=True)
                            logo_inserted = True
                            logger.info(f"Logo inserted using insert_image method on page {page_num + 1}")
                    except Exception as e:
                        logger.warning(f"insert_image method failed on page {page_num + 1}: {str(e)}")

                    # Approach 2: show_pdf_page method
                    if not logo_inserted:
                        try:
                            if hasattr(new_page, 'show_pdf_page'):
                                img_doc = pymupdf.open(logo_image_path)
                                new_page.show_pdf_page(logo_rect, img_doc, 0)
                                logo_inserted = True
                                logger.info(f"Logo inserted using show_pdf_page method on page {page_num + 1}")
                                img_doc.close()
                        except Exception as e:
                            logger.warning(f"show_pdf_page method failed on page {page_num + 1}: {str(e)}")

                    # Approach 3: pixmap method
                    if not logo_inserted:
                        try:
                            img_pixmap = pymupdf.Pixmap(logo_image_path)
                            if hasattr(new_page, 'insert_image'):
                                new_page.insert_image(logo_rect, pixmap=img_pixmap, overlay=True)
                                logo_inserted = True
                                logger.info(f"Logo inserted using pixmap method on page {page_num + 1}")
                            img_pixmap = None
                        except Exception as e:
                            logger.warning(f"Pixmap method failed on page {page_num + 1}: {str(e)}")

                # Add header text in header area
                header_text = title  # Use the passed title parameter
                header_x = line_margin
                header_y = (header_height - 15) / 2 + 15  # Center vertically, adjust for font baseline

                try:
                    if hasattr(new_page, 'insert_text'):
                        position = pymupdf.Point(header_x, header_y)
                        new_page.insert_text(position, header_text, fontsize=14, fontname="helbo")
                except Exception as e:
                    logger.warning(f"Failed to insert header text on page {page_num + 1}: {str(e)}")

                # Copy original content to the new page, but shifted down
                # This is the key fix - we're repositioning the content
                content_rect = pymupdf.Rect(
                    0, content_start_y,  # Left, Top (shifted down)
                    page_rect.width, content_end_y  # Right, Bottom
                )

                try:
                    new_page.show_pdf_page(content_rect, original_doc, page_num)
                except Exception as e:
                    logger.warning(f"Failed to copy content to page {page_num + 1}: {str(e)}")

                # Helper function to calculate text position
                def calculate_text_position(text, font_size=15, target_x=None, target_y=None, alignment='left'):
                    """Calculate text position based on alignment"""
                    char_width = font_size * 0.6  # Approximate character width
                    text_width = len(text) * char_width

                    if alignment == 'right' and target_x is not None:
                        return target_x - text_width, target_y
                    elif alignment == 'center' and target_x is not None:
                        return target_x - (text_width / 2), target_y
                    else:  # left alignment
                        return target_x, target_y

                # Add footer content in footer area
                footer_content_start_y = footer_line_y + 15  # Start 15 points below footer line
                margin = 10

                # Page number (bottom-right of footer area)
                page_text = f"Page {page_num + 1} of {original_doc.page_count}"
                page_x, page_y = calculate_text_position(
                    page_text,
                    font_size=10,
                    target_x=page_rect.width - margin,
                    target_y=footer_content_start_y + 20,  # Position in footer area
                    alignment='right'
                )

                try:
                    if hasattr(new_page, 'insert_text'):
                        position = pymupdf.Point(page_x, page_y)
                        new_page.insert_text(position, page_text, fontsize=10, fontname="helv")
                except Exception as e:
                    logger.warning(f"Failed to insert page number on page {page_num + 1}: {str(e)}")

                # Footer text (bottom-left of footer area)
                footer_text = "Generated by IBM watsonx RAN"
                footer_x, footer_y = margin, footer_content_start_y + 20

                try:
                    if hasattr(new_page, 'insert_text'):
                        position = pymupdf.Point(footer_x, footer_y)
                        new_page.insert_text(position, footer_text, fontsize=10, fontname="helv")
                except Exception as e:
                    logger.warning(f"Failed to insert footer text on page {page_num + 1}: {str(e)}")

                # Add date/time stamp
                from datetime import datetime
                date_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                date_x, date_y = calculate_text_position(
                    date_text,
                    font_size=8,
                    target_x=page_rect.width / 2,
                    target_y=footer_content_start_y + 20,
                    alignment='center'
                )

                try:
                    if hasattr(new_page, 'insert_text'):
                        position = pymupdf.Point(date_x, date_y)
                        new_page.insert_text(position, date_text, fontsize=8, fontname="helv")
                except Exception as e:
                    logger.warning(f"Failed to insert date stamp on page {page_num + 1}: {str(e)}")

            # Close the original document
            original_doc.close()

            # Save the new document with compression
            new_doc.save(output_pdf_path, deflate=True, clean=True)
            new_doc.close()

        logo_path = await user_id_injection.find_repo_image("IBM_watsonx_logo.svg.png")

        # Run PDF conversion in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            pdf_bytes = await loop.run_in_executor(
                pool, convert_markdown_to_pdf, markdown_content, logo_path
            )

        logger.info(f"Successfully converted Markdown to PDF - Size: {len(pdf_bytes)} bytes")

        # Return streaming response with PDF
        pdf_stream = io.BytesIO(pdf_bytes)

        return ErrorHandlingStreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=KPI Analysis Report - {key}.pdf",
                "Content-Length": str(len(pdf_bytes)),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f'key:{key}, error: {e}')
        logger.error(error_trace)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating PDF: {str(e)}"
        )

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@app.on_event("shutdown")
async def shutdown_event():
    await memory_setup.cleanup()


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug", timeout_keep_alive=300)


if __name__ == "__main__":
    main()
