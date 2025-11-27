from langgraph.graph import MessagesState, StateGraph, END
# from chat.chunks import manage_memory, display_messages
from utils.network_agent_utils import display_messages, generate_summary
from llms.utils import generate_summary
from utils.tokenization import get_tokens
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    ToolMessage,
    AIMessage,
    RemoveMessage,
)
import json
import asyncio
from datetime import datetime
import re
# from rich.console import Console
from utils.log_init import logger
from typing import TypedDict, Dict, Any, Optional, List

class AgentState(MessagesState):
    """A state class that extends MessagesState to include other relevant information.
    
    This class maintains the state of the agent's conversation, including messages
    and a summary of the conversation history.
    
    Attributes:
        summary (str): A summary of the conversation history
        retry_count (int): retry
        max_retries (int): maximum number of retries
        validation_errors list[str]: validation errors
    """    
    summary: str
    retry_count: int
    max_retries: int
    validation_errors: list[str]

class Agent:
    """DISH telecommunications agent that implements a state-based conversation flow.
    
    This agent uses a graph-based architecture to manage conversation flow, tool usage,
    and memory management. It can handle tool calls, maintain conversation history,
    and manage token limits through summarization.
    
    Attributes:
        system (str): System instructions for the agent
        graph (StateGraph): The conversation flow graph
        tools (Dict): Dictionary of available tools
        checkpointer: Checkpoint manager for saving/loading agent state
        model: The language model used for generating responses
        token_memory_limit (int): Maximum number of tokens allowed in conversation history
    """    
    def __init__(self, model, tools, checkpointer, token_memory_limit=100000, system="", tool_calls_to_remember=None, max_retries=3):
        self.system = system
        self.token_memory_limit = token_memory_limit
        self.max_retries = max_retries
        self.tool_calls_to_remember = tool_calls_to_remember

        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("memory", self.filter_memory)
        graph.add_node("retry", self.handle_retry)

        # Enhanced conditional edges with retry logic
        graph.add_conditional_edges(
            "llm",
            self.route_after_llm,
            {
                "action": "action",
                "retry": "retry",
                "memory": "memory"
            }
        )
        graph.add_edge("action", "llm")
        graph.add_edge("memory", END)
        graph.add_edge("retry", "llm")
        graph.set_entry_point("llm")

        logger.info("About to compile graph...")
        self.graph = graph.compile(checkpointer=checkpointer)
        logger.info("Graph compiled...")        
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)

    async def get_full_context_token_count(self, state: AgentState) -> int:
        """Get the total token count including tool descriptions that LangChain injects.

        This method reconstructs the full prompt as it would be sent to the model,
        including the tool descriptions that LangChain automatically injects.

        Args:
            state (AgentState): Current state of the agent

        Returns:
            int: Total token count including tool descriptions
        """
        # Build tool descriptions as LangChain would inject them
        tool_descriptions = []
        for tool in self.tools.values():
            # Get tool schema if available
            tool_schema = None
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    tool_schema = tool.args_schema.model_json_schema()
                except Exception as e:
                    logger.error(f"Error getting tool schema: {e}")
                    tool_schema = None

            # Build tool description in LangChain format
            tool_desc = f"{tool.name}: {tool.description}"
            if tool_schema:
                tool_desc += f"\nParameters: {json.dumps(tool_schema, indent=2)}"
            tool_descriptions.append(tool_desc)

        tool_desc_str = "\n".join(tool_descriptions)

        # Build the system prompt with tool descriptions
        system_with_tools = self.system
        if state.get("summary", ""):
            system_with_tools += state.get("summary", "")

        if tool_desc_str:
            system_with_tools += f"\n\nYou have access to the following tools:\n\n{tool_desc_str}\n\nUse the tools when needed to answer the user's question."

        # Build the full prompt as it would be sent to the model
        full_prompt = f"System: {system_with_tools}\n"

        # Add conversation history (using filtered messages for token counting too)
        filtered_messages = self._filter_messages_for_llm(state["messages"])
        for msg in filtered_messages:
            if isinstance(msg, ToolMessage):
                full_prompt += "Tool: "
            elif isinstance(msg, AIMessage):
                full_prompt += "AI: "
            elif isinstance(msg, HumanMessage):
                full_prompt += "Human: "
            full_prompt += str(msg.content) + "\n"

        # Make token counting async-safe
        return await asyncio.get_event_loop().run_in_executor(None, get_tokens, full_prompt)
    
    def fix_json_format(self, json_str):
        """Attempt to fix common JSON formatting issues"""
        if not json_str:
            return json_str

        # Remove trailing commas before closing brackets/braces
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Fix single quotes to double quotes (but be careful with content)
        json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)  # Keys
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)  # Values

        # Remove any trailing/leading whitespace
        json_str = json_str.strip()

        # Ensure proper bracket matching (basic check)
        if json_str.startswith('{') and not json_str.endswith('}'):
            json_str += '}'
        elif json_str.startswith('[') and not json_str.endswith(']'):
            json_str += ']'

        return json_str

    def extract_and_validate_tool_calls(self, ai_message):
        """Extract and validate tool calls from AI message"""
        tool_calls_from_kwargs = ai_message.additional_kwargs.get('tool_calls', [])
        validation_errors = []
        corrected_tool_calls = []

        if not tool_calls_from_kwargs:
            return [], []

        for i, call in enumerate(tool_calls_from_kwargs):
            try:
                # Extract basic info with proper error handling
                if 'function' not in call:
                    validation_errors.append(f"Tool call {i} missing 'function' key")
                    continue

                function_data = call['function']
                name = function_data.get('name')
                args_str = function_data.get('arguments', '{}')
                call_id = call.get('id', f"call_{i}")

                if not name:
                    validation_errors.append(f"Tool call {i} missing function name")
                    continue

                # Validate tool name exists
                if name not in self.tools:
                    validation_errors.append(f"Tool '{name}' does not exist. Available tools: {list(self.tools.keys())}")
                    continue

                # Try to parse arguments JSON
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError as e:
                    # Try to fix common JSON issues
                    fixed_args_str = self.fix_json_format(args_str)
                    try:
                        args = json.loads(fixed_args_str)
                        logger.info(f"Fixed JSON for tool call {i}: {args_str} -> {fixed_args_str}")
                    except json.JSONDecodeError:
                        validation_errors.append(
                            f"Invalid JSON in tool call {i} for '{name}': {str(e)}\n"
                            f"Original: {args_str}\n"
                            f"Position: {e.pos if hasattr(e, 'pos') else 'unknown'}"
                        )
                        continue

                corrected_tool_calls.append({
                    'name': name,
                    'args': args,
                    'id': call_id,
                    'type': 'tool_call'
                })

            except Exception as e:
                validation_errors.append(f"Unexpected error in tool call {i}: {str(e)}")

        return corrected_tool_calls, validation_errors

    def route_after_llm(self, state: AgentState):
        """Enhanced routing logic with validation and retry support"""
        messages = state.get('messages', [])
        if not messages or not isinstance(messages[-1], AIMessage):
            return "memory"

        ai_message = messages[-1]
        # logger.info(f'ai_message -> {ai_message}')
        tool_calls_from_kwargs = ai_message.additional_kwargs.get('tool_calls', [])

        if not tool_calls_from_kwargs:
            return "memory"  # No tool calls, proceed to memory management

        # Validate tool calls
        corrected_tool_calls, validation_errors = self.extract_and_validate_tool_calls(ai_message)

        if validation_errors:
            retry_count = state.get('retry_count', 0)
            max_retries = state.get('max_retries', self.max_retries)

            if retry_count < max_retries:
                logger.warning(f"Tool call validation failed, retry {retry_count + 1}/{max_retries}")
                return "retry"
            else:
                logger.error(f"Max retries ({max_retries}) reached. Final validation errors: {validation_errors}")
                return "memory"  # Give up and proceed to memory management

        # Update the AI message with corrected tool calls
        ai_message.tool_calls = corrected_tool_calls
        return "action"

    def handle_retry(self, state: AgentState):
        """Handle retry logic with specific error feedback"""
        retry_count = state.get('retry_count', 0)
        validation_errors = state.get('validation_errors', [])
        max_retries = state.get('max_retries', self.max_retries)

        # Get validation errors from the current message validation
        if not validation_errors and state.get('messages'):
            ai_message = state['messages'][-1]
            if isinstance(ai_message, AIMessage):
                _, validation_errors = self.extract_and_validate_tool_calls(ai_message)

        logger.warning(f"Retry attempt {retry_count + 1}/{max_retries} due to validation errors")

        # Create detailed error message for the model
        error_details = "\n".join(f"- {error}" for error in validation_errors) if validation_errors else "Unknown validation errors"

        error_message = (
            f" Tool call validation failed (Attempt {retry_count + 1}/{max_retries}):\n\n"
            f"{error_details}\n\n"
            " Please fix these issues:\n"
            "1. Ensure all tool arguments are valid JSON\n"
            "2. Use double quotes for strings, not single quotes\n"
            "3. Remove trailing commas\n"
            "4. Check bracket/brace matching\n"
            f"5. Only use available tools: {list(self.tools.keys())}\n\n"
            "Please provide your response again with correct tool call formatting."
        )

        retry_message = HumanMessage(content=error_message)

        # Return proper state update for LangGraph
        return {
            'messages': [retry_message],
            'retry_count': retry_count + 1,
            'max_retries': max_retries,
            'validation_errors': validation_errors
        }

    async def take_action(self, state: AgentState):
        """Execute validated tool calls"""

        messages = state.get('messages', [])
        # logger.info(messages)

        if not messages or not isinstance(messages[-1], AIMessage):
            return {'messages': []}

        ai_message = messages[-1]
        # Get the value of the tool_calls attribute from ai_message, or return [] if it doesn't exist.
        tool_calls = getattr(ai_message, 'tool_calls', [])

        if not tool_calls:
            logger.warning("No tool calls found in take_action")
            return {'messages': []}

        results = []

        # Execute all tool calls concurrently
        async def execute_tool_call(tool_call):
            logger.info(
                f"Agent is making a Tool Call at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==> {tool_call}[/]"
            )
            try:
                result = await self.tools[tool_call["name"]].ainvoke(tool_call["args"])
                # logger.info(f"Tool {tool_call['name']} result: {result}")
                return ToolMessage(
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                    content=str(result)
                )
            except Exception as e:
                logger.error(f"Error invoking tool {tool_call['name']}: {e}")
                return ToolMessage(
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                    content=f"Error: {str(e)}"
                )
            finally:
                logger.info(
                    f"Tool call {tool_call['name']} completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

        # Execute all tool calls concurrently
        tool_results = await asyncio.gather(
            *[execute_tool_call(tool_call) for tool_call in tool_calls],
            return_exceptions=True
        )

        # Handle any exceptions that occurred during tool execution
        for i, result in enumerate(tool_results):
            if isinstance(result, Exception):
                logger.error(f"Tool call {i} failed with exception: {result}")
                results.append(
                    ToolMessage(
                        tool_call_id=tool_calls[i]["id"],
                        name=tool_calls[i]["name"],
                        content=f"Error: {str(result)}"
                    )
                )
            else:
                results.append(result)

        logger.info("Tool execution completed, returning to model")
        # Reset retry count after successful tool execution
        return {
            'messages': results,
            'retry_count': 0,
            'validation_errors': []
        }

    async def filter_memory(self, state: AgentState) -> Dict:
        """Manage conversation history by summarizing and trimming when token limit is exceeded.

        Args:
            state (AgentState): Current state of the agent

        Returns:
            Dict: Updated state with summarized history if needed
        """
        # Get the full token count including tool descriptions
        num_tokens = await self.get_full_context_token_count(state)
        logger.info(f"\nTokens in Chat History: {num_tokens}")

        if num_tokens > self.token_memory_limit:
            logger.info(f"We are going to trim and summarize the history")
            trim_idx = None
            for i in reversed(range(len(state["messages"]) - 4)):
                if isinstance(state["messages"][i], HumanMessage):
                    trim_idx = i
                    break

            if trim_idx is not None and trim_idx > 0:
                msgs_to_sum = state["messages"][:trim_idx]
                filtered_msgs = state["messages"][trim_idx:]

                summary = state.get("summary", "")

                # Make summarization async
                summarized_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    generate_summary,
                    " ".join([str(msg.content) for msg in msgs_to_sum]),
                    summary
                )

                summarized_text = "Summary:\n" + summarized_text
                logger.info(f"Successfully summarized history")
                logger.info(f"Trimmed {trim_idx+1} messages")
                logger.info(f"{summarized_text}")

                delete_messages = [RemoveMessage(id=m.id) for m in msgs_to_sum if m.id]
                return {"summary": summarized_text, "messages": delete_messages}
            else:
                logger.info(
                    f"\nHistory not long enough to summarize and trim"
                )

        return {}

    def _filter_messages_for_llm(self, messages: List) -> List:
        """Filter messages to keep only the specified number of tool messages for LLM context.
        
        This method preserves all messages for audit purposes but filters the context
        sent to the LLM to include only the last N tool messages and their corresponding
        AI tool call messages.
        
        Args:
            messages (List): List of all messages in the conversation
            
        Returns:
            List: Filtered messages for LLM context
        """
        logger.info(f"Filtering messages for LLM context with tool_calls_to_remember={self.tool_calls_to_remember}")
        # if self.tool_calls_to_remember is None or self.tool_calls_to_remember <= 0:
        #     # If tool_calls_to_remember is 0 or negative, don't filter tool messages
        #     return messages

        # logger.info(f"Original messages: {messages}")

        if self.tool_calls_to_remember is None or self.tool_calls_to_remember < 0:
            # If tool_calls_to_remember is None or negative, don't filter tool messages
            return messages

        filtered_messages = []
        
        # Find indices of all ToolMessage objects
        tool_message_indices = [i for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)]
        
        # Determine indices of the last n ToolMessage objects (or all if n is larger than available)
        n = min(self.tool_calls_to_remember, len(tool_message_indices))
        last_n_tool_indices = tool_message_indices[-n:] if n > 0 else []
        # logger.info(f"Last n ToolMessage indices: {last_n_tool_indices}")
        
        # Find the index of the first HumanMessage before the earliest of the last n ToolMessage
        start_index = 0
        if last_n_tool_indices:
            earliest_tool_index = min(last_n_tool_indices)
            # Search backward from the earliest ToolMessage to find the first HumanMessage
            for i in range(earliest_tool_index - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    start_index = i
                    break
        else:
            # Find the last HumanMessage if last_n_tool_indices is 0
            for i in range(len(messages) - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    start_index = i
                    break
        
        # logger.info(f"Start index for filtering: {start_index}")

        # Start from the first HumanMessage before the last n ToolMessage
        filtered_messages = messages[start_index:]  
      
        return filtered_messages

    async def call_llm(self, state: AgentState):
        """Enhanced LLM calling with retry support"""
        messages = state['messages']
        # logger.info(f'1. ##### --> messages --> {messages}')

        # Filter messages for LLM context while preserving all messages for audit
        filtered_messages = self._filter_messages_for_llm(messages)

        # Add System Prompt And Summary if they exist
        if self.system or state.get("summary", ""):

            logger.info("Adding system prompt and/or summary...")
            system_content = self.system + state.get("summary", "")
        

            # Add retry-specific system message if this is a retry
            retry_count = state.get('retry_count', 0)
            if retry_count > 0:
                system_content += (
                    f"\n\n🚨 CRITICAL: Your previous tool call had formatting errors (Retry {retry_count}/{self.max_retries}). "
                    "Ensure all tool calls use proper JSON formatting:\n"
                    "- Use double quotes for all strings\n"
                    "- No trailing commas\n"
                    "- Proper bracket/brace matching\n"
                    f"- Only use these available tools: {list(self.tools.keys())}\n"
                    "Double-check your JSON before responding!"
                )

            filtered_messages = [SystemMessage(content=system_content)] + filtered_messages
            # logger.info(f'2. ##### --> messages --> {messages}')

        logger.info("<================= messages to LLM  ==================> ")
        await display_messages(filtered_messages)

        try:
            message = await self.model.ainvoke(messages)

            logger.info("<================= Reply from LLM  ==================> ")
            await display_messages([message])

            # Get the full token count including tool descriptions
            full_token_count = await self.get_full_context_token_count(state)
            logger.info(f" Token Usage: {message.usage_metadata}")
            logger.info(f" Total Context Tokens (including tool descriptions): {full_token_count}")

            return {
                'messages': [message],
                'max_retries': state.get('max_retries', self.max_retries)
            }
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            error_message = AIMessage(content=f"Error: LLM invocation failed - {str(e)}")
            return {'messages': [error_message]}

# def is_valid_json(json_string):
#     """Utility function to validate JSON"""
#     try:
#         json.loads(json_string)
#         return True
#     except (json.JSONDecodeError, TypeError):
#         return False

# def debug_tool_call_format(ai_message):
#     """Debug utility to analyze tool call formatting issues"""
#     if not isinstance(ai_message, AIMessage):
#         logger.error("❌ Not an AIMessage")
#         return

#     tool_calls = ai_message.additional_kwargs.get('tool_calls', [])

#     logger.info("=== 🔍 Tool Call Debug Info ===")
#     logger.info(f"Found {len(tool_calls)} tool calls")

#     for i, call in enumerate(tool_calls):
#         logger.info(f"\n📞 Tool Call {i}:")
#         logger.info(f"  Raw call: {call}")

#         try:
#             if 'function' not in call:
#                 logger.error("  ❌ Missing 'function' key")
#                 continue

#             name = call['function'].get('name', 'MISSING_NAME')
#             args_str = call['function'].get('arguments', '{}')
#             call_id = call.get('id', 'MISSING_ID')

#             print(f"  🏷️ Name: {name}")
#             print(f"  🆔 ID: {call_id}")
#             print(f"  📝 Args string: {repr(args_str)}")

#             # Try parsing
#             try:
#                 args = json.loads(args_str)
#                 print(f"  ✅ Args parsed: {args}")
#             except json.JSONDecodeError as e:
#                 print(f"  ❌ JSON Error: {e}")
#                 print(f"  📍 Error position: {getattr(e, 'pos', 'unknown')}")

#                 # Show problematic area
#                 if hasattr(e, 'pos') and e.pos < len(args_str):
#                     start = max(0, e.pos - 10)
#                     end = min(len(args_str), e.pos + 10)
#                     problematic_area = args_str[start:end]
#                     print(f"  🎯 Problematic area: '{problematic_area}'")

#         except Exception as e:
#             print(f"  💥 Unexpected error: {e}")

#     print("=== End Debug Info ===\n")

# Example usage for testing malformed JSON scenarios
# async def test_json_fixing():
#     """Test function to validate JSON fixing capabilities"""
#     print("🧪 Testing JSON fixing capabilities...")

#     agent = Agent(None, [], None)  # Mock for testing
#     malformed_examples = [
#         '{"param": "value",}',          # Trailing comma
#         "{'param': 'value'}",           # Single quotes
#         '{"param": "value"',            # Missing closing brace
#         '{"param": value}',             # Unquoted value
#         '{"param1": "value1", "param2": "value2",}',  # Complex trailing comma
#     ]

#     for example in malformed_examples:
#         print(f"\n🔍 Testing: {example}")
#         fixed = agent.fix_json_format(example)
#         print(f"🔧 Fixed to: {fixed}")
#         print(f"✅ Valid: {is_valid_json(fixed)}")

#         if is_valid_json(fixed):
#             parsed = json.loads(fixed)
#             print(f"📊 Parsed result: {parsed}")