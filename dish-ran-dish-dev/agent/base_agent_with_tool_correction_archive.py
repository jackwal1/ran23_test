import traceback
from langgraph.graph import StateGraph, END, MessagesState
from typing import TypedDict, Dict, Any, Optional, List
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
from utils.tokenization import get_tokens
from utils.network_agent_utils import display_messages
from utils.network_agent_utils import generate_summary
from dataclasses import dataclass
from utils.log_init import logger
from utils import constants as CONST
import re
from pydantic import BaseModel, Field
from langchain.output_parsers import PydanticOutputParser

class ToolCallCorrection(BaseModel):
    """Structured output for tool call correction"""
    corrected_arguments: str = Field(description="The corrected JSON arguments for the tool call")
    explanation: str = Field(description="Detailed explanation of what was wrong and how it was fixed")
    is_valid: bool = Field(description="Whether the corrected tool call is now valid")
    common_issues: List[str] = Field(description="List of common JSON issues that were fixed")

class AgentState(MessagesState):
    """Enhanced state class that includes retry tracking information."""
    summary: str
    retry_count: int
    max_retries: int
    validation_errors: List[str]
    tool_call_examples: Dict[str, str]
    last_tool_call: Dict[str, Any]  # Store the last failed tool call for analysis
    correction_history: List[Dict[str, Any]]  # Track previous correction attempts
    corrected_tool_call: Optional[Dict[str, Any]] = None  # Store the corrected tool call

class Telco_Agent:
    """Enhanced telecommunications agent with structured tool call correction."""

    def __init__(
            self, model, tools, checkpointer, token_memory_limit=100000, system="",
            tool_calls_to_remember=None, max_retries=3, correction_model=None
    ):
        """Initialize the Telco Agent with structured correction capabilities."""
        self.system = system
        self.tool_calls_to_remember = tool_calls_to_remember
        self.max_retries = max_retries
        self.correction_model = correction_model or model  # Use separate model if provided

        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("memory", self.filter_memory)
        graph.add_node("retry", self.handle_retry)
        graph.add_node("correct_tool_call", self.correct_tool_call)

        # Add conditional edges
        graph.add_conditional_edges(
            "llm",
            self.route_after_llm,
            {
                "action": "action",
                "retry": "retry",
                "memory": "memory"
            }
        )
        graph.add_conditional_edges(
            "retry",
            self.should_attempt_correction,
            {
                "correct": "correct_tool_call",
                "llm": "llm"
            }
        )
        graph.add_conditional_edges(
            "correct_tool_call",
            self.route_after_correction,
            {
                "action": "action",
                "llm": "llm"
            }
        )
        graph.add_edge("action", "llm")
        graph.add_edge("memory", END)
        graph.set_entry_point("llm")

        # Compile the graph with checkpointer
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)
        self.token_memory_limit = token_memory_limit

        # Set up output parser for structured corrections
        self.correction_parser = PydanticOutputParser(pydantic_object=ToolCallCorrection)

    async def get_full_context_token_count(self, state: AgentState) -> int:
        """Get the total token count including tool descriptions that LangChain injects."""
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

        # Fix 1: Handle concatenated JSON objects (common issue in our logs)
        # Find the first complete JSON object
        brace_count = 0
        split_pos = -1
        for i, char in enumerate(json_str):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    split_pos = i + 1
                    break
        if split_pos > 0 and split_pos < len(json_str):
            json_str = json_str[:split_pos]

        # Fix 2: Remove trailing commas before closing brackets/braces
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Fix 3: Fix single quotes to double quotes (but be careful with content)
        json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)  # Keys
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)  # Values

        # Fix 4: Handle missing values (like "band":,)
        json_str = re.sub(r'"([^"]+)":\s*,', r'"\1": null,', json_str)

        # Fix 5: Remove any trailing/leading whitespace
        json_str = json_str.strip()

        # Fix 6: Ensure proper bracket matching (basic check)
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
        tool_calls_from_kwargs = ai_message.additional_kwargs.get('tool_calls', [])

        if not tool_calls_from_kwargs:
            return "memory"  # No tool calls, proceed to memory management

        # Validate tool calls
        corrected_tool_calls, validation_errors = self.extract_and_validate_tool_calls(ai_message)

        # Store the last tool call for analysis in retry
        last_tool_call = None
        if tool_calls_from_kwargs:
            last_tool_call = tool_calls_from_kwargs[0]

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

    def should_attempt_correction(self, state: AgentState):
        """Decide whether to attempt structured correction or return to LLM"""
        retry_count = state.get('retry_count', 0)
        # Use structured correction on the second retry attempt
        if retry_count >= 1:
            return "correct"
        return "llm"

    def route_after_correction(self, state: AgentState):
        """Decide whether to execute the corrected tool call or return to LLM"""
        # If we have a corrected tool call, execute it directly
        if state.get('corrected_tool_call'):
            return "action"
        return "llm"

    async def correct_tool_call(self, state: AgentState):
        """Use a separate LLM call with structured output to correct tool calls"""
        last_tool_call = state.get('last_tool_call', {})
        validation_errors = state.get('validation_errors', [])
        correction_history = state.get('correction_history', [])

        if not last_tool_call or 'function' not in last_tool_call:
            logger.warning("No tool call to correct")
            return {'messages': [], 'corrected_tool_call': None}

        tool_name = last_tool_call['function'].get('name', '')
        args_str = last_tool_call['function'].get('arguments', '{}')

        # Get tool schema if available
        tool_schema = None
        if tool_name in self.tools and hasattr(self.tools[tool_name], 'args_schema'):
            try:
                tool_schema = self.tools[tool_name].args_schema.model_json_schema()
            except Exception as e:
                logger.error(f"Error getting tool schema: {e}")

        # Create correction prompt
        correction_prompt = f"""
You are a JSON correction expert. Your task is to fix malformed JSON arguments for tool calls.

Tool Name: {tool_name}
Tool Schema: {json.dumps(tool_schema, indent=2) if tool_schema else 'Not available'}

Original Arguments (malformed):
{args_str}

Validation Errors:
{chr(10).join(f'- {error}' for error in validation_errors)}

Previous Correction Attempts:
{json.dumps(correction_history, indent=2) if correction_history else 'None'}

Please fix the JSON arguments to match the tool schema and resolve all validation errors.
Pay special attention to:
1. Proper JSON syntax (quotes, commas, brackets)
2. All required fields must be present
3. Field types must match the schema
4. No concatenated JSON objects
5. No missing values (use null if needed)

{self.correction_parser.get_format_instructions()}
"""

        try:
            # Make the correction call
            correction_response = await self.correction_model.ainvoke([
                SystemMessage(content="You are a JSON correction expert. Fix malformed tool call arguments."),
                HumanMessage(content=correction_prompt)
            ])

            # Parse the structured response
            correction = self.correction_parser.parse(correction_response.content)

            logger.info(f"Structured correction result: {correction}")

            # Add to correction history
            correction_history.append({
                'original': args_str,
                'corrected': correction.corrected_arguments,
                'explanation': correction.explanation,
                'is_valid': correction.is_valid,
                'common_issues': correction.common_issues
            })

            # Create a message with the correction explanation
            correction_message = AIMessage(
                content=f"I've corrected the tool call JSON. Here's what was fixed:\n\n{correction.explanation}\n\nCommon issues addressed: {', '.join(correction.common_issues)}"
            )

            # If the correction is valid, prepare the corrected tool call for execution
            corrected_tool_call = None
            if correction.is_valid:
                try:
                    corrected_args = json.loads(correction.corrected_arguments)
                    corrected_tool_call = {
                        'name': tool_name,
                        'args': corrected_args,
                        'id': last_tool_call.get('id', 'corrected_call'),
                        'type': 'tool_call'
                    }
                    logger.info(f"Prepared corrected tool call for execution: {corrected_tool_call}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse corrected arguments: {correction.corrected_arguments}")

            return {
                'messages': [correction_message],
                'correction_history': correction_history,
                'retry_count': state.get('retry_count', 0) + 1,
                'corrected_tool_call': corrected_tool_call
            }

        except Exception as e:
            logger.error(f"Error in structured correction: {e}")
            # Fallback to regular retry message
            return {
                'messages': [HumanMessage(content=f"Structured correction failed: {str(e)}. Please try again with the previous guidance.")],
                'retry_count': state.get('retry_count', 0) + 1,
                'corrected_tool_call': None
            }

    def handle_retry(self, state: AgentState):
        """Handle retry logic with specific error feedback"""
        retry_count = state.get('retry_count', 0)
        validation_errors = state.get('validation_errors', [])
        max_retries = state.get('max_retries', self.max_retries)
        last_tool_call = state.get('last_tool_call', {})

        # Get validation errors from the current message validation
        if not validation_errors and state.get('messages'):
            ai_message = state['messages'][-1]
            if isinstance(ai_message, AIMessage):
                _, validation_errors = self.extract_and_validate_tool_calls(ai_message)
                # Get the last tool call
                tool_calls_from_kwargs = ai_message.additional_kwargs.get('tool_calls', [])
                if tool_calls_from_kwargs:
                    last_tool_call = tool_calls_from_kwargs[0]

        logger.warning(f"Retry attempt {retry_count + 1}/{max_retries} due to validation errors")

        # Create detailed error message for the model
        error_details = "\n".join(f"- {error}" for error in validation_errors) if validation_errors else "Unknown validation errors"

        # Generate tool examples if available
        tool_examples = ""
        if state.get('tool_call_examples'):
            tool_examples = "\n\nExamples of correct tool usage:\n"
            for tool_name, example in state.get('tool_call_examples', {}).items():
                tool_examples += f"- {tool_name}:\n{example}\n"

        # Analyze the specific error and provide targeted guidance
        specific_guidance = ""
        if last_tool_call and 'function' in last_tool_call:
            args_str = last_tool_call['function'].get('arguments', '{}')
            tool_name = last_tool_call['function'].get('name', '')

            # Check for common issues
            if '":,' in args_str:
                specific_guidance += "\n\nSpecific issue detected: Missing value for a key (e.g., \"key\":,).\n"
                specific_guidance += "Fix: Provide a value for all keys, even if it's null (e.g., \"key\": null).\n"

            if '{"' in args_str and args_str.count('{') > 1:
                specific_guidance += "\n\nSpecific issue detected: Multiple JSON objects concatenated.\n"
                specific_guidance += "Fix: Ensure you provide only one complete JSON object, not multiple.\n"

            if '""' in args_str:
                specific_guidance += "\n\nSpecific issue detected: Double quotes in values.\n"
                specific_guidance += "Fix: Use single set of double quotes for string values (e.g., \"value\" not \"\"value\"\").\n"

            # Generate a corrected example based on the tool schema
            if tool_name in self.tools and hasattr(self.tools[tool_name], 'args_schema'):
                try:
                    schema = self.tools[tool_name].args_schema.model_json_schema()
                    example = {}

                    # Extract values from the original attempt if possible
                    original_args = {}
                    try:
                        fixed_args_str = self.fix_json_format(args_str)
                        original_args = json.loads(fixed_args_str)
                    except:
                        pass

                    # Generate example based on schema
                    for prop, details in schema.get('properties', {}).items():
                        if prop in original_args:
                            example[prop] = original_args[prop]
                        else:
                            # Generate a reasonable example based on the type
                            if details.get('type') == 'string':
                                example[prop] = "example_value"
                            elif details.get('type') == 'integer':
                                example[prop] = 123
                            elif details.get('type') == 'number':
                                example[prop] = 123.45
                            elif details.get('type') == 'boolean':
                                example[prop] = True
                            elif details.get('type') == 'null':
                                example[prop] = None
                            elif details.get('type') == 'array':
                                example[prop] = []
                            elif details.get('type') == 'object':
                                example[prop] = {}

                    specific_guidance += f"\n\nCorrected example for {tool_name}:\n"
                    specific_guidance += f"{json.dumps(example, indent=2)}\n"
                except Exception as e:
                    logger.error(f"Error generating corrected example: {e}")

        error_message = (
            f"🚨 Tool call validation failed (Attempt {retry_count + 1}/{max_retries}):\n\n"
            f"{error_details}\n"
            f"{specific_guidance}\n"
            "Please fix these issues:\n"
            "1. Ensure all tool arguments are valid JSON\n"
            "2. Use double quotes for strings, not single quotes\n"
            "3. Remove trailing commas\n"
            "4. Check bracket/brace matching\n"
            "5. Provide values for all keys (use null if needed)\n"
            f"6. Only use available tools: {list(self.tools.keys())}\n"
            f"{tool_examples}\n"
            "Please provide your response again with correct tool call formatting."
        )

        retry_message = HumanMessage(content=error_message)

        # Return proper state update for LangGraph
        return {
            'messages': [retry_message],
            'retry_count': retry_count + 1,
            'max_retries': max_retries,
            'validation_errors': validation_errors,
            'last_tool_call': last_tool_call,
            'corrected_tool_call': None
        }

    async def take_action(self, state: AgentState):
        """Execute validated tool calls"""
        messages = state.get('messages', [])
        corrected_tool_call = state.get('corrected_tool_call')

        # If we have a corrected tool call from the correction node, use it
        if corrected_tool_call:
            logger.info(f"Executing corrected tool call: {corrected_tool_call}")
            tool_calls = [corrected_tool_call]
        else:
            # Otherwise, check the last message for tool calls
            if not messages or not isinstance(messages[-1], AIMessage):
                return {'messages': []}

            ai_message = messages[-1]
            tool_calls = getattr(ai_message, 'tool_calls', [])

            if not tool_calls:
                logger.warning("No tool calls found in take_action")
                return {'messages': []}

        results = []
        tool_call_examples = state.get('tool_call_examples', {}).copy()

        # Execute all tool calls concurrently
        async def execute_tool_call(tool_call):
            logger.info(
                f"Agent is making a Tool Call at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==> {tool_call}"
            )
            try:
                result = await self.tools[tool_call["name"]].ainvoke(tool_call["args"])
                return ToolMessage(
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                    content=str(result)
                )
            except Exception as e:
                logger.error(f"Error invoking tool {tool_call['name']}: {e}")

                # Generate an example of correct tool usage if we have the schema
                tool_name = tool_call["name"]
                if tool_name not in tool_call_examples and hasattr(self.tools[tool_name], 'args_schema'):
                    try:
                        schema = self.tools[tool_name].args_schema.model_json_schema()
                        example = {}
                        for prop, details in schema.get('properties', {}).items():
                            # Generate a reasonable example based on the type
                            if details.get('type') == 'string':
                                example[prop] = "example_value"
                            elif details.get('type') == 'integer':
                                example[prop] = 123
                            elif details.get('type') == 'number':
                                example[prop] = 123.45
                            elif details.get('type') == 'boolean':
                                example[prop] = True
                            elif details.get('type') == 'null':
                                example[prop] = None
                            elif details.get('type') == 'array':
                                example[prop] = []
                            elif details.get('type') == 'object':
                                example[prop] = {}

                        tool_call_examples[tool_name] = json.dumps(example, indent=2)
                    except Exception as ex:
                        logger.error(f"Error generating tool example: {ex}")

                # Create a detailed error message
                error_msg = f"Error: {str(e)}\n\n"

                # Add tool schema information if available
                if hasattr(self.tools[tool_name], 'args_schema'):
                    try:
                        schema = self.tools[tool_name].args_schema.model_json_schema()
                        error_msg += f"Tool schema:\n{json.dumps(schema, indent=2)}\n\n"
                    except Exception as ex:
                        logger.error(f"Error getting tool schema: {ex}")

                # Add example of correct usage if available
                if tool_name in tool_call_examples:
                    error_msg += f"Example of correct usage:\n{tool_call_examples[tool_name]}\n\n"

                return ToolMessage(
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                    content=error_msg
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
            'validation_errors': [],
            'tool_call_examples': tool_call_examples,
            'last_tool_call': {},
            'correction_history': [],
            'corrected_tool_call': None
        }

    async def filter_memory(self, state: AgentState) -> Dict:
        """Manage conversation history by summarizing and trimming when token limit is exceeded."""
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

                # Clean up retry tracking for old tool calls
                tool_call_examples = state.get('tool_call_examples', {})

                # Get tool call IDs from messages being trimmed
                trimmed_tool_call_ids = set()
                for msg in msgs_to_sum:
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            trimmed_tool_call_ids.add(tool_call["id"])

                # Remove error tracking for tools that are no longer being retried
                active_tool_names = set()
                for msg in filtered_msgs:
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            active_tool_names.add(tool_call["name"])

                updated_tool_call_examples = {
                    k: v for k, v in tool_call_examples.items()
                    if k in active_tool_names
                }

                delete_messages = [RemoveMessage(id=m.id) for m in msgs_to_sum if m.id]
                return {
                    "summary": summarized_text,
                    "messages": delete_messages,
                    "retry_count": 0,
                    "validation_errors": [],
                    "tool_call_examples": updated_tool_call_examples,
                    "last_tool_call": {},
                    "correction_history": [],
                    "corrected_tool_call": None
                }
            else:
                logger.info(f"\nHistory not long enough to summarize and trim")

        return {}

    def _filter_messages_for_llm(self, messages: List) -> List:
        """Filter messages to keep only the specified number of tool messages for LLM context."""
        logger.info(f"Filtering messages for LLM context with tool_calls_to_remember={self.tool_calls_to_remember}")

        if self.tool_calls_to_remember is None or self.tool_calls_to_remember < 0:
            return messages

        filtered_messages = []
        tool_message_indices = [i for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)]

        n = min(self.tool_calls_to_remember, len(tool_message_indices))
        last_n_tool_indices = tool_message_indices[-n:] if n > 0 else []

        start_index = 0
        if last_n_tool_indices:
            earliest_tool_index = min(last_n_tool_indices)
            for i in range(earliest_tool_index - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    start_index = i
                    break
        else:
            for i in range(len(messages) - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    start_index = i
                    break

        filtered_messages = messages[start_index:]
        return filtered_messages

    async def call_llm(self, state: AgentState):
        """Enhanced LLM calling with retry support"""
        messages = state['messages']

        # Filter messages for LLM context while preserving all messages for audit
        filtered_messages = self._filter_messages_for_llm(messages)

        # Add System Prompt And Summary if they exist
        if self.system or state.get("summary", ""):
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
                    "- Provide values for all keys (use null if needed)\n"
                    "- Only include one complete JSON object\n"
                    f"- Only use these available tools: {list(self.tools.keys())}\n"
                    "Double-check your JSON before responding!"
                )

            filtered_messages = [SystemMessage(content=system_content)] + filtered_messages

        logger.info("<================= messages to LLM  ==================> ")
        await display_messages(filtered_messages)

        try:
            message = await self.model.ainvoke(filtered_messages)
            logger.info("<================= Reply from LLM  ==================> ")
            await display_messages([message])

            # Get the full token count including tool descriptions
            full_token_count = await self.get_full_context_token_count(state)
            logger.info(f"Token Usage: {message.usage_metadata}")
            logger.info(f"Total Context Tokens (including tool descriptions): {full_token_count}")

            return {
                'messages': [message],
                'max_retries': state.get('max_retries', self.max_retries),
                'tool_call_examples': state.get('tool_call_examples', {}),
                'last_tool_call': state.get('last_tool_call', {}),
                'correction_history': state.get('correction_history', []),
                'corrected_tool_call': state.get('corrected_tool_call', None)
            }
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            error_message = AIMessage(content=f"Error: LLM invocation failed - {str(e)}")
            return {'messages': [error_message]}

    async def run_agent(self, initial_state: AgentState, config: Optional[Dict] = None) -> Dict:
        """Run the agent with proper async handling."""
        try:
            if hasattr(self.graph, 'ainvoke'):
                result = await self.graph.ainvoke(initial_state, config=config)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.graph.invoke, initial_state, config
                )
            return result
        except Exception as e:
            logger.error(f"Error running agent: {e}")
            raise

    async def stream_agent(self, initial_state: AgentState, config: Optional[Dict] = None):
        """Stream agent execution with proper async handling."""
        try:
            if hasattr(self.graph, 'astream'):
                async for chunk in self.graph.astream(initial_state, config=config):
                    yield chunk
            else:
                for chunk in self.graph.stream(initial_state, config=config):
                    yield chunk
        except Exception as e:
            logger.error(f"Error streaming agent: {e}")
            raise