from langchain_core.messages import HumanMessage
import json
from agent import gpl_classifier_agent, base_agent_reasoning
from utils.log_init import logger
from typing import List, Dict, Any, Optional, Union
from utils.query_classifier_v2 import  extract_json_from_string


async def gpl_classifier_chat(
        user_message: str,
        thread_id: Optional[str] = None,
        validator_thread_id: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Sends the user_message to the LangGraph agent, streams through the steps,
    captures the final LLM output, extracts embedded JSON, ensures `missing_info`
    is present, and returns a flat dict of strings.
    """
    langgraph_agent = await gpl_classifier_agent.initialize_agent()
    inputs = {"messages": [("user", user_message)]}

    raw_output = await langgraph_agent.graph.ainvoke(inputs)
    raw_output = get_ai_message_content_prioritized(raw_output)

    logger.info(f"Return from LLm :: {raw_output}")

    if raw_output is None:
        logger.error("No LLM output received in streaming.")
        return {}
    logger.info("Extracting Json")
    parsed = extract_json_from_string(raw_output)
    if parsed is None:
        logger.error(f"Failed to extract JSON from LLM output: {raw_output}")
        return {}

    # Flatten to Dict[str, Optional[str]]
    if isinstance(parsed, dict):
        result: Dict[str, Optional[str]] = {k: (str(v) if v is not None else None)
                                            for k, v in parsed.items()}
    else:
        result = {"result": json.dumps(parsed)}

    return result

async def live_table_classifier(
        model: Any,
        system: str,
        user_message: str,
        cot_prompt: str) -> Dict[str, Optional[str]]:
    """
    Sends the user_message to the LangGraph agent, streams through the steps,
    captures the final LLM output, extracts embedded JSON, ensures `missing_info`
    is present, and returns a flat dict of strings.
    """
    langgraph_agent = await base_agent_reasoning.initialize_reasoning_agent(
        checkpointer=None,
        model=model,
        system_instruction=system,
        cot_system_prompt=cot_prompt

    )
    inputs = {"messages": [("user", user_message)]}

    raw_output = await langgraph_agent.ainvoke(inputs)
    logger.info(f"Return from LLm 1:: {raw_output}")
    raw_output = get_ai_message_content_prioritized(raw_output)


    logger.info(f"Return from LLm 2:: {raw_output}")

    if raw_output is None:
        logger.error("No LLM output received in streaming.")
        return {}

    return raw_output

def get_ai_message_content_prioritized(step):
    """
    Prioritize classifier_llm messages, fallback to direct messages.
    Appends 'plan' to the response if it exists in the step.
    """
    # Priority 1: classifier_llm messages (nested structure)
    llm_msgs = step.get("classifier_llm", {}).get("messages", [])
    if llm_msgs:
        last_msg = llm_msgs[-1]
        if hasattr(last_msg, 'content') and last_msg.content:
            content = last_msg.content
            plan = step.get('plan')
            return f"{content}\n\nPlan: {plan}" if plan else content

    # Priority 2: direct messages
    direct_msgs = step.get("messages", [])
    if direct_msgs:
        # Find the last AI message (skip human messages)
        for msg in reversed(direct_msgs):
            if hasattr(msg, 'content') and msg.content:
                if not isinstance(msg, HumanMessage):
                    content = msg.content
                    plan = step.get('plan')
                    return f"{content}\n\nPlan: {plan}" if plan else content

    # Fallback: Return plan if no messages but plan exists
    plan = step.get('plan')
    return f"Plan: {plan}" if plan else None