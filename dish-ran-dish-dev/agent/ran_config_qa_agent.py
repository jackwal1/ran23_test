from tools.ran_config_qa_tools import get_ran_qa_tools
from prompts.ran_config_qa_prompts import RAN_CONFIG_QA_AGENT_INSTRUCTION_PROMPT_CONSOLIDATED_v4
from llms.llms import chatmodel_mistral_large_ran_2, chatmodel_mistral_medium_ran_2
#from llms.models import ran_config_qa_model
import time
# from rich.console import Console
from .base_agent_asset import Telco_Agent
from utils.memory_checkpoint import get_checkpointer
from utils.log_init import logger

# Initialize console for rich text output
# console = Console()

async def initialize_ran_config_qa_agent():
    start_time = time.perf_counter()
    logger.info("==== Initializing RAN Config QA Agent")

    # Get checkpoint manager for state persistence
    checkpointer = await get_checkpointer()

    # Initialize the agent with IBM-specific configuration
    ran_config_qa_agent = Telco_Agent(
        chatmodel_mistral_medium_ran_2,
        await get_ran_qa_tools(),
        token_memory_limit=100000,  # Maximum tokens in conversation history
        system=RAN_CONFIG_QA_AGENT_INSTRUCTION_PROMPT_CONSOLIDATED_v4,    # IBM-specific system instructions
        checkpointer=checkpointer,  # Checkpoint manager for state persistence
    )

    # Calculate and log initialization time
    end_time = time.perf_counter()
    elapsed_time = (end_time - start_time) * 1000
    logger.info(f"Agent initialization time: {elapsed_time:.2f} ms")

    return ran_config_qa_agent.graph

async def initialize_ran_config_qa_agent_medium():
    start_time = time.perf_counter()
    logger.info("==== Initializing RAN Config QA Agent")

    # Get checkpoint manager for state persistence
    checkpointer = await get_checkpointer()

    # Initialize the agent with IBM-specific configuration
    ran_config_qa_agent = Telco_Agent(
        chatmodel_mistral_medium_ran_2,
        await get_ran_qa_tools(),
        token_memory_limit=100000,  # Maximum tokens in conversation history
        tool_calls_to_remember=25,  # Maximum tool calls to remember
        system=RAN_CONFIG_QA_AGENT_INSTRUCTION_PROMPT_CONSOLIDATED_v4,    # IBM-specific system instructions
        checkpointer=checkpointer,  # Checkpoint manager for state persistence
    )

    # Calculate and log initialization time
    end_time = time.perf_counter()
    elapsed_time = (end_time - start_time) * 1000
    logger.info(f"Agent initialization time: {elapsed_time:.2f} ms")

    return ran_config_qa_agent.graph





