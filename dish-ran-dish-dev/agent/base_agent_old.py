from langgraph.graph import MessagesState
from chat.chunks import manage_memory, display_messages
from llms.utils import generate_summary
from utils.tokenization import get_tokens
from langgraph.graph import StateGraph, END
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, filter_messages, AIMessage, RemoveMessage
import json
import re
from rich.console import Console
from utils.log_init import logger

console = Console()

# log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)

# logging.basicConfig(
#     level=log_level,
#     format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S"
# )

# logger = logging.getLogger("RAN")

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
    def __init__(self, model, tools, checkpointer, token_memory_limit=100000, system="", max_retries=3):
        self.system = system
        self.token_memory_limit = token_memory_limit
        self.max_retries = max_retries

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

        print("About to compile graph...")
        self.graph = graph.compile(checkpointer=checkpointer)
        print("Graph compiled...")        
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)

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
            f"❌ Tool call validation failed (Attempt {retry_count + 1}/{max_retries}):\n\n"
            f"{error_details}\n\n"
            "🔧 Please fix these issues:\n"
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

    # async def exists_action(self, state: AgentState):
    #     """Legacy method - now handled by route_after_llm"""
    #     if state['messages'] and isinstance(state['messages'][-1], AIMessage):
    #         result = state['messages'][-1]
    #         return hasattr(result, 'tool_calls') and len(result.tool_calls) > 0
    #     return False

    async def take_action(self, state: AgentState):
        """Execute validated tool calls"""

        messages = state.get('messages', [])
        logger.info(messages)

        if not messages or not isinstance(messages[-1], AIMessage):
            return {'messages': []}

        ai_message = messages[-1]
        # Get the value of the tool_calls attribute from ai_message, or return [] if it doesn't exist.
        tool_calls = getattr(ai_message, 'tool_calls', [])

        if not tool_calls:
            logger.warning("No tool calls found in take_action")
            return {'messages': []}

        results = []
        for t in tool_calls:
            try:
                logger.info(f"Executing tool: {t['name']} with args: {t['args']}")
                result = await self.tools[t['name']].ainvoke(t['args'])
                results.append(ToolMessage(
                    tool_call_id=t['id'],
                    name=t['name'],
                    content=str(result)
                ))
            except Exception as e:
                logger.error(f"Error executing tool {t['name']}: {str(e)}")
                results.append(ToolMessage(
                    tool_call_id=t['id'],
                    name=t['name'],
                    content=f"Error executing tool: {str(e)}"
                ))

        logger.info("Tool execution completed, returning to model")
        # Reset retry count after successful tool execution
        return {
            'messages': results,
            'retry_count': 0,
            'validation_errors': []
        }

    async def filter_memory(self, state: AgentState):
        """Enhanced memory filtering with proper state management"""
        # Default is no filtering
        messages = state["messages"]

        # Create string of history to check tokens
        history_str = ""
        if self.system or state.get("summary", ""):
            history_str = "System: " + self.system + state.get("summary", "") + "\n"
        for msg in messages:
            if isinstance(msg, ToolMessage):
                history_str += "Tool: "
            elif isinstance(msg, AIMessage):
                history_str += "AI: "
            elif isinstance(msg, HumanMessage):
                history_str += "Human: "
            history_str += str(getattr(msg, 'content', '')) + "\n"

        num_tokens = get_tokens(history_str)
        logger.info(f"Tokens in Chat History: {num_tokens}")

        # Trim and summarize history if over token limit
        if num_tokens > self.token_memory_limit:
            logger.info(f"We are going to trim and summarize the history")
            trim_idx = None
            # Find last human message over 4 messages ago to split
            for i in reversed(range(len(messages) - 4)):
                if isinstance(messages[i], HumanMessage):
                    trim_idx = i
                    break

            if trim_idx is not None and trim_idx > 0:
                msgs_to_sum = messages[:trim_idx]
                filtered_msgs = messages[trim_idx:]

                summary = state.get("summary", "")
                try:
                    summarized_text = await generate_summary(
                        " ".join([str(getattr(msg, 'content', '')) for msg in msgs_to_sum]), summary
                    )
                    summarized_text = "Summary:\n" + summarized_text
                    logger.info(f"Successfully summarized history")
                    logger.info(f"Trimmed {trim_idx+1} messages")
                    logger.info(f"{summarized_text}")
                    logger.info(f"Deleting trimmed messages::::::")
                    logger.info(msgs_to_sum)

                    delete_messages = []
                    for m in msgs_to_sum:
                        if hasattr(m, 'id') and m.id:
                            delete_messages.append(RemoveMessage(id=m.id))

                    return {
                        "summary": summarized_text,
                        "messages": delete_messages,
                        'retry_count': 0,  # Reset retry count
                        'validation_errors': []
                    }
                except Exception as e:
                    logger.error(f"Error during summarization: {e}")
            else:
                logger.info(f"History not long enough to summarize and trim")

        else:
            # Irrespective of tokens, remove messages - 1) ToolMessage 2) AIMessage with content=''
            delete_messages = []
            for msg in messages:
                if isinstance(msg, ToolMessage) or (isinstance(msg, AIMessage) and msg.content.strip() == ''):
                    if hasattr(msg, 'id') and msg.id:
                        delete_messages.append(RemoveMessage(id=msg.id))
            return {
                "messages": delete_messages,
                'retry_count': 0,  # Reset retry count
                'validation_errors': []
            }            
            
        # Return empty dict to indicate no changes needed
        return {}

    async def call_llm(self, state: AgentState):
        """Enhanced LLM calling with retry support"""
        messages = state['messages']
        # print(f'1. ##### --> messages --> {messages}')

        # Add System Prompt And Summary if they exist
        if self.system or state.get("summary", ""):
            # print(f'Adding system prompt and/or summary...')
            logger.info("Adding system prompt and/or summary...")
            system_content = self.system + state.get("summary", "")
            # print(f'1.1 ##### --> system_content --> {system_content}')            

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

            messages = [SystemMessage(content=system_content)] + messages
            # print(f'2. ##### --> messages --> {messages}')

            logger.info("<================= messages to LLM  ==================> ")
            await display_messages(messages)
        else:
            try:
                messages = await manage_memory(state, self.system)
                logger.info(f'3. ##### --> messages --> {messages}')
            except Exception as e:
                logger.warning(f"Memory management failed: {e}")
                messages = state.get('messages', [])

        try:
            message = await self.model.ainvoke(messages)

            logger.info("<================= Reply from LLM  ==================> ")
            await display_messages([message])

            # Safely access usage metadata
            usage_metadata = getattr(message, 'usage_metadata', None)
            if usage_metadata:
                console.print(f"[bold magenta]Token Usage: {usage_metadata}")

            return {
                'messages': [message],
                'max_retries': state.get('max_retries', self.max_retries)
            }
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            error_message = AIMessage(content=f"Error: LLM invocation failed - {str(e)}")
            return {'messages': [error_message]}

def is_valid_json(json_string):
    """Utility function to validate JSON"""
    try:
        json.loads(json_string)
        return True
    except (json.JSONDecodeError, TypeError):
        return False

def debug_tool_call_format(ai_message):
    """Debug utility to analyze tool call formatting issues"""
    if not isinstance(ai_message, AIMessage):
        print("❌ Not an AIMessage")
        return

    tool_calls = ai_message.additional_kwargs.get('tool_calls', [])

    print("=== 🔍 Tool Call Debug Info ===")
    print(f"Found {len(tool_calls)} tool calls")

    for i, call in enumerate(tool_calls):
        print(f"\n📞 Tool Call {i}:")
        print(f"  Raw call: {call}")

        try:
            if 'function' not in call:
                print("  ❌ Missing 'function' key")
                continue

            name = call['function'].get('name', 'MISSING_NAME')
            args_str = call['function'].get('arguments', '{}')
            call_id = call.get('id', 'MISSING_ID')

            print(f"  🏷️ Name: {name}")
            print(f"  🆔 ID: {call_id}")
            print(f"  📝 Args string: {repr(args_str)}")

            # Try parsing
            try:
                args = json.loads(args_str)
                print(f"  ✅ Args parsed: {args}")
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON Error: {e}")
                print(f"  📍 Error position: {getattr(e, 'pos', 'unknown')}")

                # Show problematic area
                if hasattr(e, 'pos') and e.pos < len(args_str):
                    start = max(0, e.pos - 10)
                    end = min(len(args_str), e.pos + 10)
                    problematic_area = args_str[start:end]
                    print(f"  🎯 Problematic area: '{problematic_area}'")

        except Exception as e:
            print(f"  💥 Unexpected error: {e}")

    print("=== End Debug Info ===\n")

# Example usage for testing malformed JSON scenarios
async def test_json_fixing():
    """Test function to validate JSON fixing capabilities"""
    print("🧪 Testing JSON fixing capabilities...")

    agent = Agent(None, [], None)  # Mock for testing
    malformed_examples = [
        '{"param": "value",}',          # Trailing comma
        "{'param': 'value'}",           # Single quotes
        '{"param": "value"',            # Missing closing brace
        '{"param": value}',             # Unquoted value
        '{"param1": "value1", "param2": "value2",}',  # Complex trailing comma
    ]

    for example in malformed_examples:
        print(f"\n🔍 Testing: {example}")
        fixed = agent.fix_json_format(example)
        print(f"🔧 Fixed to: {fixed}")
        print(f"✅ Valid: {is_valid_json(fixed)}")

        if is_valid_json(fixed):
            parsed = json.loads(fixed)
            print(f"📊 Parsed result: {parsed}")