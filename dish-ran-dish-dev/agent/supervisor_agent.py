# from __future__ import annotations

import time

from utils.memory_checkpoint import get_checkpointer
# from utils.summary_utils import generate_summary
from llms.models import supervisor_model
from utils.log_init import logger
from .base_supervisor_agent import BaseSupervisorAgent, BaseSupervisorState
from .ran_pm_agent import initialize_ran_pm_agent
from .ran_qa_agent import initialize_ran_qa_agent
from .ran_config_qa_agent import initialize_ran_config_qa_agent_medium
from .ran_automation_agent import initialize_ran_automation_agent
from prompts.ran_supervisor_prompt import SUPERVISOR_PROMPT

# console = Console()

# initialise the worker agents for the supervisor agent
async def _initialise_worker_agents():
    ran_pm = await initialize_ran_pm_agent()
    ran_qa = await initialize_ran_qa_agent()
    ran_config = await initialize_ran_config_qa_agent_medium()
    ran_automation = await initialize_ran_automation_agent()
    return {
        "ran_pm_agent": ran_pm,
        "ran_qa_agent": ran_qa,
        "ran_config_agent": ran_config,
        "ran_automation_agent": ran_automation,
    }

# initialize the supervisor agent with the worker agents
async def initialize_supervisor_agent():
    start_ts = time.perf_counter()
    logger.info("Initializing Multi-Agent Supervisor...")
    supervisor_checkpointer = await get_checkpointer()
    worker_agents = await _initialise_worker_agents()
    supervisor_agent = BaseSupervisorAgent(
        model=supervisor_model,
        workers=worker_agents,
        checkpointer=supervisor_checkpointer,
        token_memory_limit=50000,
        system=SUPERVISOR_PROMPT,
    )
    elapsed_ms = (time.perf_counter() - start_ts) * 1000
    logger.info(
        f"Supervisor initialized in {elapsed_ms:.2f} ms with workers: {list(worker_agents.keys())}"
    )
    return supervisor_agent.graph
