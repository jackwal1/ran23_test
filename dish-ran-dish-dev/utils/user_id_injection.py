from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from utils.log_init import logger
from typing import Optional, Any, Coroutine
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from utils.redis_util import get_redis_client
import json
import asyncio

# ================================
# 1. USER SESSION MANAGEMENT
# ================================

async def register_user_session(thread_id: str, user_id: str):
    """Map thread_id to user_id"""
    logger.info(f"Redis client loaded for registration")
    redis = get_redis_client()
    await redis.set(thread_id, user_id, expire_seconds=86400)
    logger.info(f"✅ Registered session: {thread_id} -> {user_id}")


async def get_user_from_thread(thread_id: str) -> str:
    """Get user_id from thread_id"""
    if not thread_id:
        logger.warning("No thread_id provided")
        return None

    logger.info(f"Redis client loaded for retrieval")
    redis = get_redis_client()
    user_id = await redis.get(thread_id)

    if user_id:
        logger.info(f"✅ User ID for session: {thread_id} -> {user_id}")
    else:
        logger.warning(f"❌ No user found for thread: {thread_id}")

    return user_id

async def save_to_redis(key: str, data: dict, expire_seconds: int = 86400):
    """Save data to Redis with expiration"""
    try:
        redis = get_redis_client()
        json_data = json.dumps(data)
        await redis.set(key, json_data, expire_seconds=expire_seconds)
        logger.info(f"Successfully saved data to Redis with key: {key}")
    except Exception as e:
        logger.error(f"Failed to save data to Redis: {str(e)}")

async def get_from_redis(key: str) -> Optional[dict]:
    """Retrieve data from Redis"""
    try:
        redis = get_redis_client()
        json_data = await redis.get(key)
        if json_data:
            logger.info(f"Successfully retrieved data from Redis with key: {key}")
            return json.loads(json_data)
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve data from Redis: {str(e)}")
        return None

# Define which tools need user_id - LIST FORMAT
TOOLS_REQUIRING_USER_ID = ["handle_ret_update", "handle_classc_update"]  # These 2 tools need user_id

class SelectiveUserContextToolNode(ToolNode):
    """Custom ToolNode that injects user_id ONLY for specific tools"""

    def __init__(self, tools, tools_needing_user_id=None):
        super().__init__(tools)
        self.tools_needing_user_id = tools_needing_user_id or []

    async def __call__(self, state: MessagesState, config: RunnableConfig = None):
        """Override to inject user context only for specific tools (ASYNC VERSION)"""

        # Get thread_id from config
        thread_id = None
        if config and hasattr(config, 'configurable'):
            thread_id = config.configurable.get('thread_id')

        # Get user_id from thread_id (NOW PROPERLY ASYNC)
        user_id = await get_user_from_thread(thread_id) if thread_id else None

        if user_id and state.get('messages'):
            last_message = state['messages'][-1]

            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                modified_tool_calls = []
                needs_modification = False

                for tool_call in last_message.tool_calls:
                    tool_name = tool_call['name']

                    # Only inject user_id for specific tools
                    if tool_name in self.tools_needing_user_id:
                        logger.info(f"🔧 Injecting user_id '{user_id}' into tool: {tool_name}")
                        modified_call = tool_call.copy()
                        modified_call['args'] = {**tool_call['args'], 'user_id': user_id}
                        modified_tool_calls.append(modified_call)
                        needs_modification = True
                    else:
                        logger.info(f"⏭️  Skipping user_id injection for tool: {tool_name}")
                        modified_tool_calls.append(tool_call)

                if needs_modification:
                    # Create new AI message with modified tool calls
                    modified_message = AIMessage(
                        content=last_message.content,
                        tool_calls=modified_tool_calls
                    )

                    # Update state with modified message
                    modified_state = {
                        **state,
                        'messages': state['messages'][:-1] + [modified_message]
                    }

                    return await super().__call__(modified_state, config)

        # No modification needed - call parent async method
        return await super().__call__(state, config)

    # Keep sync version for backward compatibility if needed
    def __call_sync__(self, state: MessagesState, config: RunnableConfig = None):
        """Synchronous version using asyncio.run for compatibility"""
        return asyncio.run(self.__call__(state, config))

# ================================
# HELPER FUNCTIONS FOR AGENT INTEGRATION
# ================================

async def inject_user_context_into_state(state: MessagesState, config: RunnableConfig = None, tools_needing_user_id: list = None):
    """
    Standalone function to inject user context into state - used by the agent's take_action method
    This is what your Telco_Agent uses in its _inject_user_context method
    """
    if not tools_needing_user_id:
        tools_needing_user_id = TOOLS_REQUIRING_USER_ID

    # Get thread_id from config
    thread_id = None
    if config and hasattr(config, 'configurable'):
        thread_id = config.configurable.get('thread_id')

    # Get user_id from thread_id
    user_id = await get_user_from_thread(thread_id) if thread_id else None

    if user_id and state.get('messages'):
        last_message = state['messages'][-1]

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            modified_tool_calls = []
            needs_modification = False

            for tool_call in last_message.tool_calls:
                tool_name = tool_call['name']

                # Only inject user_id for specific tools
                if tool_name in tools_needing_user_id:
                    logger.info(f"🔧 Injecting user_id '{user_id}' into tool: {tool_name}")
                    modified_call = tool_call.copy()
                    modified_call['args'] = {**tool_call['args'], 'user_id': user_id}
                    modified_tool_calls.append(modified_call)
                    needs_modification = True
                else:
                    logger.info(f"⏭️  Skipping user_id injection for tool: {tool_name}")
                    modified_tool_calls.append(tool_call)

            if needs_modification:
                # Create new AI message with modified tool calls
                modified_message = AIMessage(
                    content=last_message.content,
                    tool_calls=modified_tool_calls
                )

                # Update state with modified message
                state['messages'][-1] = modified_message
                logger.info(f"✅ Successfully updated {len([tc for tc in modified_tool_calls if tc['name'] in tools_needing_user_id])} tool calls with user_id")

from pathlib import Path

async def find_repo_image(name: str, images_dir_name: str = "Images") -> Path | None:
    """Look upward from this file to find <images_dir_name>/<name>.
    """
    logger.info(f"Looking for Image :: {name}")
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        candidate = parent / images_dir_name / name
        if candidate.exists():
            return candidate
    # final attempt: check cwd / images dir
    candidate = Path.cwd() / images_dir_name / name
    if candidate.exists():
        return candidate
    return None


