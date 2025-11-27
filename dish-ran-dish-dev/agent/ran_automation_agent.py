from tools.ran_automation_tools import ran_automation_tools
from prompts.ran_automation_prompt import RAN_AUTOMATION_PROMPT_TEMPLATE_V2
#from llms.llms import chatmodel_mistral_large_ran_2, chatmodel_mistral_medium_ran_2
from llms.models import ran_automation_model
import time
# from rich.console import Console
from .base_agent_with_tool_correction import Telco_Agent
from utils.memory_checkpoint import get_checkpointer
from utils.log_init import logger

# Initialize console for rich text output
# console = Console()

async def initialize_ran_automation_agent():
    start_time = time.perf_counter()
    logger.info("==== Initializing RAN Automation Agent")

    # Get checkpoint manager for state persistence
    checkpointer = await get_checkpointer()

    # Initialize the agent with IBM-specific configuration
    ran_automation_agent = Telco_Agent(
        ran_automation_model,
        ran_automation_tools,
        token_memory_limit=100000,  # Maximum tokens in conversation history
        system=RAN_AUTOMATION_PROMPT_TEMPLATE_V2,    # IBM-specific system instructions
        checkpointer=checkpointer,  # Checkpoint manager for state persistence
    )

    # Calculate and log initialization time
    end_time = time.perf_counter()
    elapsed_time = (end_time - start_time) * 1000
    logger.info(f"Agent initialization time: {elapsed_time:.2f} ms")

    return ran_automation_agent.graph


