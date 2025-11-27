import utils.memory_checkpoint as memory
from langchain_core.messages import HumanMessage, AIMessage
from typing import List, Dict, Union, Optional, Any
import re
import asyncio



async def trim_ai_message(message: str, max_length: int = 500) -> str:
    """
    Trim AI messages for cleaner context while preserving meaning.

    Args:
        message: The AI message to trim
        max_length: Maximum length for trimmed message

    Returns:
        Trimmed message with ellipsis if truncated
    """
    if len(message) <= max_length:
        return message

    # Try to cut at sentence boundaries
    sentences = re.split(r'[.!?]+', message)
    trimmed = ""

    for sentence in sentences:
        if len(trimmed + sentence) <= max_length - 10:  # Leave room for ellipsis
            trimmed += sentence + ". "
        else:
            break

    if trimmed:
        return trimmed.strip() + "..."
    else:
        # If no complete sentence fits, just truncate
        return message[:max_length-3] + "..."


async def get_formatted_conversation_history(
        state,
        n: int = 10,
        trim_ai_messages: bool = True,
        max_ai_length: int = 500
) -> List[Dict[str, str]]:
    """
    Format conversation history from PostgreSQL checkpoint.

    Args:
        state: LangGraph state object
        checkpointer: PostgresSaver instance for checkpoint operations
        n: Number of message pairs to retrieve
        trim_ai_messages: Whether to trim AI messages for cleaner context
        max_ai_length: Maximum length for AI messages when trimming

    Returns:
        List of dictionaries formatted for format_conversation_for_llm function
    """
    thread_id = state.get("thread_id_sql_agent")

    if not thread_id:
        # Fallback to state messages if no thread_id
        if "messages" not in state:
            return []
        all_messages = state["messages"]
    else:
        # Fetch from PostgreSQL checkpoint
        thread_config = {"configurable": {"thread_id": thread_id}}

        checkpointer = await memory.get_checkpointer()

        try:
            # Get latest checkpoint
            latest_checkpoint = await checkpointer.aget_tuple(thread_config)
            if latest_checkpoint and latest_checkpoint.checkpoint:
                all_messages = latest_checkpoint.checkpoint.get('channel_values', {}).get('messages', [])
            else:
                all_messages = []
        except Exception as e:
            print(f"Error fetching from checkpoint: {e}")
            all_messages = []

    # Filter to only human and AI messages (exclude tool calls)
    human_ai_messages = [
        msg for msg in all_messages
        if isinstance(msg, (HumanMessage, AIMessage)) and
           not (isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls)
    ]

    # Group messages into conversation pairs
    conversation_history = []
    i = 0

    while i < len(human_ai_messages) - 1 and len(conversation_history) < n:
        current = human_ai_messages[i]
        next_msg = human_ai_messages[i + 1]

        if isinstance(current, HumanMessage) and isinstance(next_msg, AIMessage):
            ai_content = next_msg.content

            # Trim AI message if requested
            if trim_ai_messages:
                ai_content = await trim_ai_message(ai_content, max_ai_length)

            # Create formatted dictionary
            interaction = {
                "user_query": current.content,
                "ai_message": ai_content
            }

            conversation_history.append(interaction)
            i += 2
        else:
            i += 1

    # Return in reverse order (most recent first) and limit to n
    return list((conversation_history))[-n:]


async def get_conversation_context_for_llm(
        state,
        n: int = 10,
        trim_ai_messages: bool = True,
        max_ai_length: int = 500
) -> str:
    """
    Get formatted conversation context ready for LLM consumption from PostgreSQL checkpoint.

    Args:
        state: LangGraph state object
        checkpointer: PostgresSaver instance for checkpoint operations
        n: Number of message pairs to retrieve
        trim_ai_messages: Whether to trim AI messages for cleaner context
        max_ai_length: Maximum length for AI messages when trimming

    Returns:
        Formatted string ready for LLM context
    """
    conversation_history = await get_formatted_conversation_history(
        state, n, trim_ai_messages, max_ai_length
    )

    return await format_conversation_for_llm(conversation_history)


async def format_conversation_for_llm(conversation_history: List[Dict[str, str]]) -> str:
    """
    Convert conversation history JSON to a clear format for LLM context understanding.

    Args:
        conversation_history: List of dictionaries with user_query and ai_message

    Returns:
        Formatted string that provides clear context for LLM
    """
    if not conversation_history:
        return "No previous conversation history available."

    context_parts = [
        "=== CONVERSATION HISTORY ===",
        f"Previous interactions: {len(conversation_history)} messages",
        ""
    ]

    for i, interaction in enumerate(conversation_history, 1):
        user_query = interaction.get('user_query', 'No query recorded')
        ai_message = interaction.get('ai_message', 'No response available')

        context_parts.extend([
            f"--- Interaction {i} ---",
            f"User Query: {user_query}",
            f"AI Message: {ai_message}",
            ""
        ])

    context_parts.extend([
        "=== END CONVERSATION HISTORY ===",
        "",
        "Instructions for LLM:",
        "- Use this conversation history to understand the user's previous questions and context",
        "- Maintain conversation continuity and refer to previous topics when relevant",
        "- If the user asks follow-up questions, consider the previous responses",
        "- Make sure to enrich the follow up queries with proper context before doing tool calls"
    ])

    return "\n".join(context_parts)


# Example usage:
async def main():
    # Example of how to use the async functions with PostgreSQL checkpoint
    # checkpointer = PostgresSaver.from_conn_string("postgresql://user:password@localhost:5432/langgraph_db")
    # state = {"thread_id_sql_agent": "some_thread_id"}
    # context = await get_conversation_context_for_llm(state, checkpointer, n=5)
    # print(context)
    pass

if __name__ == "__main__":
    asyncio.run(main())