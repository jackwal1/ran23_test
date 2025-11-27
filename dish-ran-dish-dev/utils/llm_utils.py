import asyncio
from contextlib import asynccontextmanager
import logging
from utils import constants as CONST

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

default_timeout_duration_llm = 30
async def ran_fallback_response_utility():
    """ """
    starter_line = "The question is not related to the RAN documents that I have been trained on. Please provide a relevant query and I will be happy to help!"
    resp = [{"type": "text", "content": starter_line}]
    return resp

# Reusable function for timeout handling
@asynccontextmanager
async def call_with_timeout(coroutine, llm_name, timeout=default_timeout_duration_llm):
    """
    Wraps an async function call with a timeout.
    
    Args:
        coroutine: The async function to call.
        timeout_duration (int): Maximum duration in seconds before timeout.
        
    Raises:
        asyncio.TimeoutError: If the call exceeds the specified timeout.

    Returns:
        The result of the coroutine if it completes within the timeout.
    """
    try:
        # logger.info(f'conversation_id:{state["conversation_id"]} user_id:{state["user_id"]} prompt:{state['user_query']} - TIMEOUT CHECK for llm call ==> {llm_name} : START')
        # print("timeout_duration-- ", timeout)
        yield await asyncio.wait_for(coroutine, timeout=timeout)
        # logger.info(f'conversation_id:{state["conversation_id"]} user_id:{state["user_id"]} prompt:{state['user_query']} - TIMEOUT CHECK for llm call ==> {llm_name} : END')
    except asyncio.TimeoutError:
        logger.error(f' RAN-TIMEOUT CHECK for llm call ==> {llm_name} : ERROR')
        raise TimeoutError(f"Operation timed out after {timeout} seconds. llm call ==> {llm_name}")
    
    