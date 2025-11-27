import utils.memory_checkpoint as memory
from utils import constants as CONST
from tools.ran_pm_tools import get_mcp_tools
from utils.log_init import logger
from llms.models import ran_pm_chatmodel
from .base_agent_asset import Telco_Agent
from prompts.ran_pm_prompt import PM_AGENT_INSTRUCTION_PROMPT_V1

# initialize agent
async def initialize_ran_pm_agent():
    """Initialize the enhanced agent with retry capabilities"""
    try:
        checkpointer = await memory.get_checkpointer()
         # Ensure tools are loaded
        langgraph_agent = Telco_Agent(
            ran_pm_chatmodel,
            tools=await get_mcp_tools(),
            checkpointer=checkpointer,
            token_memory_limit=50000,
            # max_retries=max_retries,
            system=PM_AGENT_INSTRUCTION_PROMPT_V1,
            tool_calls_to_remember=2, # 1 is necessary for continuous conversation            
        )
        return langgraph_agent.graph
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise