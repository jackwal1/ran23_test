import logging
from starlette.responses import StreamingResponse
import json
import traceback
from utils import constants as CONST

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

class ErrorHandlingStreamingResponse(StreamingResponse):
    async def __call__(self, scope, receive, send):
        try:
            # Delegate to Starlette's StreamingResponse for normal streaming
            await super().__call__(scope, receive, send)
        except Exception as e:
            traceback.print_exc()
            # Send generic error message in SSE format
            error_message = f"data: {json.dumps({'type': 'error', 'content': 'An unexpected error occurred. Please try again.'})}\n\n"
            await send({
                "type": "http.response.body",
                "body": error_message.encode('utf-8'),
                "more_body": False,
            })