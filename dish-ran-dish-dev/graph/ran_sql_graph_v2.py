import logging
import asyncio
import json
import re
import traceback

from langgraph.graph import MessagesState, StateGraph, END
from utils.ran2_qa.ran_sql_tools_v2 import tools
from utils.ran2_qa.ran_sql_agent_utils import manage_memory
from llms.llms import chatmodel_mistral_large_ran_2, llama_405_chatmodel_react
import utils.memory_checkpoint as memory
from typing import TypedDict, Annotated, Dict, List, Union
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from utils import constants as CONST
from prompts.ran2_qa.ran_sql_prompts_v2 import RAN_SQL_AGENT_INSTRUCTION_PROMPT_V2

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    retry_count: int
    max_retries: int
    thread_id: str
    validation_errors: list[str]

class Agent:
    def __init__(self, model, tools, checkpointer, system="", max_retries=3):
        self.system = system
        self.max_retries = max_retries
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("retry", self.handle_retry)
        graph.add_conditional_edges(
            "llm",
            self.route_after_llm,
            {
                "action": "action",
                "retry": "retry",
                "end": END
            }
        )
        graph.add_edge("action", "llm")
        graph.add_edge("retry", "llm")
        graph.set_entry_point("llm")
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)

    def fix_json_format(self, json_str: str) -> str:
        """Attempt to fix common JSON formatting issues"""
        if not json_str:
            return json_str
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
        json_str = json_str.strip()
        if json_str.startswith('{') and not json_str.endswith('}'):
            json_str += '}'
        elif json_str.startswith('[') and not json_str.endswith(']'):
            json_str += ']'
        return json_str

    def extract_and_validate_tool_calls(self, ai_message: AIMessage) -> tuple[List[Dict], List[str]]:
        """Extract and validate tool calls from AI message"""
        tool_calls_from_kwargs = ai_message.additional_kwargs.get('tool_calls', [])
        validation_errors = []
        corrected_tool_calls = []
        if not tool_calls_from_kwargs:
            return [], []
        for i, call in enumerate(tool_calls_from_kwargs):
            try:
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
                if name not in self.tools:
                    validation_errors.append(f"Tool '{name}' does not exist. Available tools: {list(self.tools.keys())}")
                    continue
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError as e:
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

    def route_after_llm(self, state: AgentState) -> str:
        """Route based on LLM output and validation"""
        messages = state.get('messages', [])
        if not messages or not isinstance(messages[-1], AIMessage):
            return "end"
        ai_message = messages[-1]
        tool_calls_from_kwargs = ai_message.additional_kwargs.get('tool_calls', [])
        if not tool_calls_from_kwargs:
            return "end"
        corrected_tool_calls, validation_errors = self.extract_and_validate_tool_calls(ai_message)
        if validation_errors:
            retry_count = state.get('retry_count', 0)
            max_retries = state.get('max_retries', self.max_retries)
            if retry_count < max_retries:
                logger.warning(f"Tool call validation failed, retry {retry_count + 1}/{max_retries}")
                return "retry"
            else:
                logger.error(f"Max retries ({max_retries}) reached. Final validation errors: {tuple(validation_errors)}")
                return "end"
        ai_message.tool_calls = corrected_tool_calls
        return "action"

    async def handle_retry(self, state: AgentState) -> Dict:
        """Handle retry logic with specific error feedback"""
        retry_count = state.get('retry_count', 0)
        validation_errors = state.get('validation_errors', [])
        max_retries = state.get('max_retries', self.max_retries)
        if not validation_errors and state.get('messages'):
            ai_message = state['messages'][-1]
            if isinstance(ai_message, AIMessage):
                corrected_tool_calls, validation_errors = self.extract_and_validate_tool_calls(ai_message)
        logger.warning(f"Retry attempt {retry_count + 1}/{max_retries} due to validation errors")
        error_details = "\n".join(f"- {error}" for error in validation_errors) if validation_errors else "Unknown validation errors"
        error_message = (
            f"❌ Tool call validation failed: (Attempt {retry_count + 1}/{max_retries})\n\n"
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
        return {
            'messages': [retry_message],
            'retry_count': retry_count + 1,
            'max_retries': max_retries,
            'validation_errors': validation_errors
        }

    async def take_action(self, state: AgentState) -> Dict:
        """Execute validated tool calls asynchronously"""
        messages = state.get('messages', [])
        if not messages or not isinstance(messages[-1], AIMessage):
            return {'messages': []}
        ai_message = messages[-1]
        tool_calls = getattr(ai_message, 'tool_calls', [])
        if not tool_calls:
            logger.warning("No tool calls found in take_action")
            return {'messages': []}
        results = []
        for t in tool_calls:
            try:
                logger.info(f"Executing tool: {t['name']} with args: {t['args']}")
                tool = self.tools[t['name']]
                result = await tool.ainvoke(t['args'])
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
        return {
            'messages': results,
            'retry_count': 0,
            'validation_errors': []
        }

    async def call_llm(self, state: AgentState) -> Dict:
        """Call the LLM with memory management"""
        messages = state.get('messages', [])
        try:
            messages = await manage_memory(state)
        except Exception as e:
            traceback.print_exc()
            logger.warning(f"Memory management failed: {e}")
            messages = state.get('messages', [])
        retry_count = state.get('retry_count', 0)
        if retry_count > 0:
            tool_format_reminder = SystemMessage(content=(
                "🚨 CRITICAL: Your previous tool call had formatting errors. "
                "Ensure all tool calls use proper JSON formatting:\n"
                "- Use double quotes for all strings\n"
                "- No trailing commas\n"
                "- Proper bracket/brace matching\n"
                f"- Only use these available tools: {list(self.tools.keys())}\n"
                "Double-check your JSON before responding!"
            ))
            messages = [tool_format_reminder] + messages
        try:
            message = await self.model.ainvoke(messages)
            return {
                'messages': [message],
                'max_retries': state.get('max_retries', self.max_retries)
            }
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            error_message = AIMessage(content=f"Error: LLM invocation failed - {str(e)}")
            return {'messages': [error_message]}

async def initialize_agent(max_retries: int = 3) -> Agent:
    """Initialize the enhanced agent with retry capabilities"""
    try:
        checkpointer = await memory.get_checkpointer()
        langgraph_agent = Agent(
            chatmodel_mistral_large_ran_2,
            tools,
            checkpointer=checkpointer,
            max_retries=max_retries,
            system= RAN_SQL_AGENT_INSTRUCTION_PROMPT_V2
        )
        return langgraph_agent
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

async def is_valid_json(json_string: str) -> bool:
    """Utility function to validate JSON"""
    try:
        json.loads(json_string)
        return True
    except (json.JSONDecodeError, TypeError):
        return False

async def debug_tool_call_format(ai_message: AIMessage) -> None:
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
            try:
                args = json.loads(args_str)
                print(f"  ✅ Args parsed: {args}")
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON Error: {e}")
                print(f"  📍 Error position: {getattr(e, 'pos', 'unknown')}")
                if hasattr(e, 'pos') and e.pos < len(args_str):
                    start = max(0, e.pos - 10)
                    end = min(len(args_str), e.pos + 10)
                    problematic_area = args_str[start:end]
                    print(f"  🎯 Problematic area: '{problematic_area}'")
        except Exception as e:
            print(f"  💥 Unexpected error: {e}")
    print("=== End Debug Info ===\n")

async def test_agent_with_malformed_json() -> None:
    """Test function to simulate malformed JSON scenarios"""
    print("🧪 Testing agent with various JSON formatting issues...")
    malformed_examples = [
        '{"param": "value",}',  # Trailing comma
        "{'param': 'value'}",   # Single quotes
        '{"param": "value"',    # Missing closing brace
        '{"param": value}',     # Unquoted value
    ]
    for example in malformed_examples:
        print(f"\n🔍 Testing: {example}")
        agent = Agent(None, [], None)
        fixed = agent.fix_json_format(example)
        print(f"🔧 Fixed to: {fixed}")
        valid = await is_valid_json(fixed)
        print(f"✅ Valid: {valid}")