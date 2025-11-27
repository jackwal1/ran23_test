import utils.memory_checkpoint as memory
from utils import constants as CONST
from tools.ran_qa_tools import fetch_passages
from utils.log_init import logger
from llms.models import ran_qa_chatmodel
# from .base_agent import Agent
from .base_agent_asset import Telco_Agent
from prompts.ran_qa_prompt import AGENT_INSTRUCTION_PROMPT_v7

ran_qa_toolset = [fetch_passages]

async def initialize_ran_qa_agent():
    """Initialize the enhanced agent with retry capabilities"""
    try:
        checkpointer = await memory.get_checkpointer()
         # Ensure tools are loaded
        langgraph_agent = Telco_Agent(
            ran_qa_chatmodel,
            tools=ran_qa_toolset,
            checkpointer=checkpointer,
            token_memory_limit=90000,
            # max_retries=max_retries,
            system=AGENT_INSTRUCTION_PROMPT_v7,
            tool_calls_to_remember=1,  # 1 is necessary for continuous conversation
        )
        # print("ran_qa_agent initialized")
        return langgraph_agent.graph
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise