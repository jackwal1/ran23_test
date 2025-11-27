import logging
from typing import Optional, Any

from langgraph.graph import MessagesState
from llms.llms import llama_405_chatmodel_react
from langgraph.graph import StateGraph, END
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
import json
import re
from rich.console import Console
from prompts.gpl_classifier_prompt import gpl_agent_instruction_v1

console = Console()

from utils import constants as CONST

log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

class AgentState(MessagesState):
    retry_count: int
    max_retries: int
    validation_errors: list[str]

class Agent:
    def __init__(self, model, tools, system=gpl_agent_instruction_v1, max_retries=3):
        self.system = system
        self.max_retries = max_retries
        self.tools = {t.name: t for t in tools}
        self.model = model

        # Build the graph
        graph = StateGraph(AgentState)
        graph.add_node("classifier_llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("retry", self.handle_retry)

        # Enhanced conditional edges with retry logic
        graph.add_conditional_edges(
            "classifier_llm",
            self.route_after_llm,
            {
                "action": "action",
                "retry": "retry",
                "end": END
            }
        )
        graph.add_edge("action", "classifier_llm")
        graph.add_edge("retry", "classifier_llm")
        graph.set_entry_point("classifier_llm")

        self.graph = graph.compile()

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
            return "end"

        ai_message = messages[-1]
        tool_calls_from_kwargs = ai_message.additional_kwargs.get('tool_calls', [])

        if not tool_calls_from_kwargs:
            return "end"  # No tool calls, end conversation

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
                return "end"  # Give up and end

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

    async def take_action(self, state: AgentState):
        """Execute validated tool calls"""
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

    async def call_llm(self, state: AgentState):
        """Call LLM with system prompt"""
        messages = state.get('messages', [])

        # Add system prompt at the beginning if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            if self.system:
                messages = [SystemMessage(content=self.system)] + messages

        try:
            message = await self.model.ainvoke(messages)

            logger.info("<================= Reply from LLM  ==================> ")
            print(f"AI: {message.content}")

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

    async def run(self, user_input: str):
        """Simple run method to process user input"""
        initial_state = {
            'messages': [HumanMessage(content=user_input)],
            'retry_count': 0,
            'max_retries': self.max_retries,
            'validation_errors': []
        }

        result = await self.graph.ainvoke(initial_state)
        return result

async def initialize_agent(tools=None, system_prompt=None, max_retries=3):
    """Initialize the simplified agent"""
    if tools is None:
        tools = []

    if system_prompt is None:
        system_prompt = gpl_agent_instruction_v1

    try:
        agent = Agent(
            llama_405_chatmodel_react,
            tools,
            system=system_prompt,
            max_retries=max_retries
        )
        return agent
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

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

# Example usage
async def main():
    """Example usage of the simplified agent"""
    agent = await initialize_agent(
        tools=[],  # Add your tools here
        system_prompt="You are a helpful assistant.",
        max_retries=3
    )

    # Run a conversation
    result = await agent.run("Hello, how can you help me?")
    print("Final result:", result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())