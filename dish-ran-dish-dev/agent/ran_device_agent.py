import utils.memory_checkpoint as memory
from utils import constants as CONST
from tools.ran_device_tools import fetch_device_data
from tools.ran_nca_device_tools import fetch_customer_order_data, fetch_nca_call_summary_data, fetch_nca_device_data
from utils.log_init import logger
from llms.models import ran_device_chatmodel
from .base_agent_asset import Telco_Agent
# from .base_agent import Agent

from prompts.ran_device_prompt import DEVICE_AGENT_INSTRUCTION_PROMPT_v3

ran_device_toolset = [fetch_device_data,fetch_nca_call_summary_data, fetch_nca_device_data, fetch_customer_order_data]

async def initialize_ran_device_agent():
    """Initialize the enhanced agent with retry capabilities"""
    try:
        checkpointer = await memory.get_checkpointer()
         # Ensure tools are loaded
        langgraph_agent = Telco_Agent(
            ran_device_chatmodel,
            tools=ran_device_toolset,
            checkpointer=checkpointer,
            token_memory_limit=100000,
            # max_retries=1,
            #system=DEVICE_AGENT_INSTRUCTION_PROMPT_v2,
            system=DEVICE_AGENT_INSTRUCTION_PROMPT_v3,
            tool_calls_to_remember=1,  # 1 is necessary for continuous conversation
        )
        return langgraph_agent.graph
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise