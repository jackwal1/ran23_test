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
from utils.tokenization import get_tokens
from utils.network_agent_utils import display_messages
from utils.network_agent_utils import generate_summary
from dataclasses import dataclass
from utils.log_init import logger
from utils import constants as CONST
from datetime import datetime
import weakref

class AgentState(MessagesState):
    """A state class that extends MessagesState to include summary and reasoning information."""
    thread_id: Optional[str]
    summary: str
    thought: str
    reasoning: str  # Added for Chain of Thought reasoning
    plan: str

class MemoryManager:
    """Background memory management system."""
    def __init__(self, token_limit: int):
        self.token_limit = token_limit
        self.soft_limit = int(token_limit * 0.8)  # 80% threshold
        self.cache = {}
        self.background_tasks = set()
        self.last_cleanup = 0

    async def check_and_manage(self, state: AgentState, agent_instance) -> None:
        """Non-blocking memory check and management."""
        current_time = asyncio.get_event_loop().time()
        # Skip if we recently checked (within last 30 seconds)
        if current_time - self.last_cleanup < 30:
            return

        # Quick heuristic check
        if self._should_cleanup(state):
            # Schedule background cleanup
            task = asyncio.create_task(
                self._perform_background_cleanup(state, agent_instance)
            )
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)
            self.last_cleanup = current_time

    def _should_cleanup(self, state: AgentState) -> bool:
        """Fast heuristic to determine if cleanup is needed."""
        if not state.get("messages"):
            return False

        message_count = len(state["messages"])
        char_count = sum(len(str(msg.content)) for msg in state["messages"])
        # Rough estimates: 4 chars per token
        estimated_tokens = char_count // 4

        # Trigger cleanup if we're approaching limits
        return (estimated_tokens > self.soft_limit or message_count > 50)

    async def _perform_background_cleanup(self, state: AgentState, agent_instance) -> None:
        """Actual cleanup operations in background."""
        try:
            logger.info("Starting background memory cleanup")
            # Get accurate token count
            num_tokens = await agent_instance.get_full_context_token_count(state)
            if num_tokens > self.soft_limit:
                await self._cleanup_messages(state, agent_instance)
                logger.info(f"Background cleanup completed. Cleaned up excess tokens.")
            else:
                logger.info("Background cleanup: No action needed after token count")
        except Exception as e:
            logger.error(f"Background memory cleanup failed: {e}")

    async def _cleanup_messages(self, state: AgentState, agent_instance):
        """Clean up old messages and create summary."""
        messages = state.get("messages", [])
        if len(messages) <= 10:  # Keep minimum conversation context
            return

        # Find a good cut-off point (keep last 10 messages)
        trim_idx = max(0, len(messages) - 10)

        # Find the last HumanMessage before our cutoff to maintain context
        for i in range(trim_idx - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                trim_idx = i
                break

        if trim_idx > 0:
            msgs_to_summarize = messages[:trim_idx]
            # Create summary in background
            summary_content = " ".join([str(msg.content) for msg in msgs_to_summarize])
            current_summary = state.get("summary", "")
            try:
                new_summary = await asyncio.get_event_loop().run_in_executor(
                    None,
                    generate_summary,
                    summary_content,
                    current_summary
                )
                # Update state summary (this would need checkpointer integration)
                logger.info(f"Generated summary for {len(msgs_to_summarize)} messages")
            except Exception as e:
                logger.error(f"Summary generation failed: {e}")

class Telco_Agent:
    """IBM's telecommunications agent with Chain of Thought reasoning and background memory management."""
    def __init__(
            self, model, tools, checkpointer=None, token_memory_limit=100000, system="",
            tool_calls_to_remember=None, cot_system_prompt=None
    ):
        """Initialize the Telco Agent with Chain of Thought reasoning.
        Args:
            model: The language model to use for generating responses
            tools: List of tools available to the agent (can be empty)
            checkpointer: Optional checkpoint manager for saving/loading agent state
            token_memory_limit (int, optional): Maximum tokens in conversation history. Defaults to 100000.
            system (str, optional): System instructions for the agent. Defaults to "".
            tool_calls_to_remember (int, optional): Number of tool messages to keep in LLM context.
            cot_system_prompt (str, optional): Chain of Thought reasoning system prompt. Defaults to None.
        """
        self.system = system
        self.tool_calls_to_remember = tool_calls_to_remember
        self.token_memory_limit = token_memory_limit
        self.memory_manager = MemoryManager(token_memory_limit)
        self.has_tools = len(tools) > 0
        self.tools = {t.name: t for t in tools} if self.has_tools else {}
        self.checkpointer = checkpointer
        self.cot_system_prompt = cot_system_prompt  # Store CoT prompt

        # Bind tools to model only if tools exist
        self.model = model.bind_tools(tools) if self.has_tools else model

        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("reasoning_node", self.reasoning_node)  # Combined think, reason, and plan
        graph.add_node("classifier_llm", self.call_llm)
        graph.add_node("final_response", self.final_response_node)

        # Add action node only if tools exist
        if self.has_tools:
            graph.add_node("action", self.take_action)

        # Set entry point
        graph.set_entry_point("reasoning_node")

        # Add edges
        graph.add_edge("reasoning_node", "classifier_llm")

        # After LLM, check if action is needed (only if tools exist)
        if self.has_tools:
            graph.add_conditional_edges(
                "classifier_llm", self.should_take_action, {True: "action", False: "final_response"}
            )
            # After action, check if we need final response
            graph.add_conditional_edges(
                "action", self.needs_final_response, {True: "final_response", False: END}
            )
        else:
            # No tools, go directly to final response
            graph.add_edge("classifier_llm", END)  # Skip final_response if no tools used

        # Final response leads to end
        graph.add_edge("final_response", END)

        # Compile the graph with optional checkpointer
        self.graph = graph.compile(checkpointer=checkpointer) if checkpointer else graph.compile()

    def should_take_action(self, state: AgentState) -> bool:
        """Check if we should take action (only called when tools exist)."""
        if not state["messages"]:
            return False

        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage):
            # Check if there are tool calls
            return bool(getattr(last_message, 'tool_calls', []))
        return False

    def needs_final_response(self, state: AgentState) -> bool:
        """Check if we need a separate final response or if LLM response is sufficient."""
        if not state["messages"]:
            return True

        # If we executed tools, we need a final response
        tool_messages = [msg for msg in state["messages"][-5:] if isinstance(msg, ToolMessage)]
        if tool_messages:
            return True

        # Check if the last AI message is complete
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and not getattr(last_message, 'tool_calls', []):
            content = last_message.content.strip()
            if len(content) > 50 and not content.startswith("I need to"):
                return False  # Response is sufficient
        return True

    async def reasoning_node(self, state: AgentState) -> Dict:
        """Combined node for thought, reasoning, and planning."""
        # Trigger background memory check (non-blocking)
        asyncio.create_task(self.memory_manager.check_and_manage(state, self))

        # Build a combined prompt for thought, reasoning, and planning
        reasoning_prompt = self.system + "\n\n" + state.get("summary", "") + "\n\n"

        if self.cot_system_prompt:
            reasoning_prompt += self.cot_system_prompt + "\n\n"

        reasoning_prompt += """You are a thinking assistant. Analyze the current conversation and provide:
1. A brief thought about what to do next.
2. Detailed reasoning following the Chain of Thought process.
3. A plan to address the user's request.

Format your response as:
Thought: [your thought]
Reasoning: [your reasoning]
Plan: [your plan]

"""

        if self.has_tools:
            reasoning_prompt += "If any step requires using a tool, specify the tool and the arguments in the plan.\n"

        reasoning_prompt += "Conversation:\n"

        # Use filtered messages for context
        filtered_messages = self._filter_messages_for_llm(state["messages"])
        for msg in filtered_messages[-10:]:  # Last 10 messages for reasoning
            if isinstance(msg, HumanMessage):
                reasoning_prompt += f"Human: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                reasoning_prompt += f"AI: {msg.content}\n"
            elif isinstance(msg, ToolMessage):
                reasoning_prompt += f"Tool ({msg.name}): {msg.content}\n"

        reasoning_prompt += "\nResponse:"

        # Generate combined thought, reasoning, and plan
        try:
            response_message = await self.model.ainvoke([HumanMessage(content=reasoning_prompt)])
            content = response_message.content

            # Parse the response to extract thought, reasoning, and plan
            thought = ""
            reasoning = ""
            plan = ""

            # Simple parsing based on expected format
            if "Thought:" in content:
                thought_part = content.split("Thought:")[1].split("Reasoning:")[0].strip()
                thought = thought_part

            if "Reasoning:" in content:
                reasoning_part = content.split("Reasoning:")[1].split("Plan:")[0].strip()
                reasoning = reasoning_part

            if "Plan:" in content:
                plan_part = content.split("Plan:")[1].strip()
                plan = plan_part

            # Fallback if parsing fails
            if not thought and not reasoning and not plan:
                logger.warning("Could not parse reasoning response, using entire content as thought")
                thought = content

            logger.info(f"Generated thought: {thought[:100]}...")
            logger.info(f"Generated reasoning: {reasoning[:100]}...")
            logger.info(f"Generated plan: {plan[:100]}...")

            return {"thought": thought, "reasoning": reasoning, "plan": plan}

        except Exception as e:
            logger.error(f"Error generating reasoning: {e}")
            return {
                "thought": f"Error: {str(e)}",
                "reasoning": "",
                "plan": ""
            }

    async def final_response_node(self, state: AgentState) -> Dict:
        """Generate a final response based on all the thinking, reasoning, planning, and tool execution."""
        # Build context for final response
        response_prompt = self.system + "\n\n" + state.get("summary", "") + "\n\n"

        if state.get("thought", ""):
            response_prompt += f"Your thought process: {state['thought']}\n\n"

        if state.get("reasoning", ""):
            response_prompt += f"Your detailed reasoning: {state['reasoning']}\n\n"

        if state.get("plan", ""):
            response_prompt += f"Your plan: {state['plan']}\n\n"

        response_prompt += """Based on your thinking, reasoning, planning, and any tool executions, provide a final, comprehensive response to the user.
        
Make your response:
- Clear and direct
- Don't Hallucinate, Always verify and self reflect on your response.
- Based on the information gathered from tools (if any were used)
- Professional and helpful
- Complete (don't leave the user hanging)
- Include key reasoning points that led to your conclusion
Conversation history:
"""

        # Use filtered messages for context
        filtered_messages = self._filter_messages_for_llm(state["messages"])
        for msg in filtered_messages[-10:]:  # Last 10 messages for final response
            if isinstance(msg, HumanMessage):
                response_prompt += f"User: {msg.content}\n"
            elif isinstance(msg, AIMessage) and not msg.tool_calls:
                response_prompt += f"Assistant: {msg.content}\n"
            elif isinstance(msg, ToolMessage):
                response_prompt += f"Tool Result ({msg.name}): {msg.content}\n"

        response_prompt += "\nFinal Response:"

        # Generate final response
        try:
            final_message = await self.model.ainvoke([HumanMessage(content=response_prompt)])
            logger.info(f"Generated final response: {final_message.content[:100]}...")
            return {"messages": [final_message]}
        except Exception as e:
            logger.error(f"Error generating final response: {e}")
            error_message = AIMessage(content="I apologize, but I encountered an error generating my response.")
            return {"messages": [error_message]}

    async def get_full_context_token_count(self, state: AgentState) -> int:
        """Get the total token count including tool descriptions."""
        # Build tool descriptions only if tools exist
        tool_desc_str = ""
        if self.has_tools:
            tool_descriptions = []
            for tool in self.tools.values():
                tool_schema = None
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    try:
                        tool_schema = tool.args_schema.model_json_schema()
                    except Exception as e:
                        logger.debug(f"Could not get tool schema: {e}")
                        tool_schema = None

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

        # Build the full prompt
        full_prompt = f"System: {system_with_tools}\n"

        if state.get("thought", ""):
            full_prompt += f"Thought: {state['thought']}\n"

        if state.get("reasoning", ""):
            full_prompt += f"Reasoning: {state['reasoning']}\n"

        if state.get("plan", ""):
            full_prompt += f"Plan: {state['plan']}\n"

        # Add conversation history
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

    async def take_action(self, state: AgentState) -> Dict:
        """Execute tool calls from the last AI message concurrently."""
        if not self.has_tools:
            return {"messages": []}  # Should never happen if graph is built correctly

        tool_calls = state["messages"][-1].tool_calls
        results = []

        async def execute_tool_call(tool_call):
            logger.info(
                f"Agent is making a Tool Call at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==> {tool_call}[/]"
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
                traceback.print_exc()
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
                logger.info(f"Tool call {i} failed with exception: {result}")
                results.append(
                    ToolMessage(
                        tool_call_id=tool_calls[i]["id"],
                        name=tool_calls[i]["name"],
                        content=f"Error: {str(result)}"
                    )
                )
            else:
                results.append(result)

        return {"messages": results}

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

    async def call_llm(self, state: AgentState) -> Dict:
        """Generate a response from the language model based on the current state."""
        messages = state["messages"]
        filtered_messages = self._filter_messages_for_llm(messages)

        # Create system message with thought, reasoning, and plan

        system_content = self.system + state.get("summary", "")

        if state.get("thought", ""):
            system_content += f"\n\nThought: {state['thought']}"

        if state.get("reasoning", ""):
            system_content += f"\n\nReasoning: {state['reasoning']}"

        if state.get("plan", ""):
            system_content += f"\n\nPlan: {state['plan']}"

        filtered_messages = [SystemMessage(content=system_content)] + filtered_messages

        logger.info("-------------------------------- filtered messages ------------------------------")
        await display_messages(filtered_messages)

        try:
            message = await self.model.ainvoke(filtered_messages)

            # Process tool calls if they exist
            if self.has_tools and hasattr(message, 'additional_kwargs') and message.additional_kwargs.get("tool_calls"):
                tool_calls_from_kwargs = message.additional_kwargs.get("tool_calls", [])
                corrected_tool_calls = []

                for call in tool_calls_from_kwargs:
                    try:
                        name = call["function"]["name"]
                        try:
                            args = json.loads(call["function"]["arguments"])
                        except json.JSONDecodeError:
                            logger.error(
                                f"Error decoding tool call arguments, using arguments as string: {call['function']['arguments']}"
                            )
                            args = call["function"]["arguments"]

                        id = call["id"]
                        type = "tool_call"
                        corrected_tool_calls.append(
                            {"name": name, "args": args, "id": id, "type": type}
                        )
                    except (KeyError, json.JSONDecodeError) as e:
                        logger.error(f"Error processing tool call: {call}, Error: {e}")

                # Create a new message with corrected tool calls
                message = AIMessage(
                    content=message.content,
                    additional_kwargs=message.additional_kwargs,
                    tool_calls=corrected_tool_calls
                )

            logger.info(f"\nToken Usage: {message.usage_metadata}")
            return {"messages": [message]}
        except Exception as e:
            logger.error(f"Error in LLM call: {e}")
            error_message = AIMessage(content=f"I encountered an error: {str(e)}")
            return {"messages": [error_message]}

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

async def initialize_reasoning_agent(
        checkpointer=None,
        model=None,
        tools=None,
        tokenlimit=100000,
        system_instruction="",
        cot_system_prompt=None
):
    """Initialize the reasoning agent with optional Chain of Thought support.
    Args:
        checkpointer: Optional checkpoint manager for saving/loading agent state
        model: The language model to use for generating responses
        tools: List of tools available to the agent (can be empty)
        tokenlimit: Maximum tokens in conversation history
        system_instruction: System instructions for the agent
        cot_system_prompt: Optional Chain of Thought reasoning system prompt
    Returns:
        Telco_Agent: Initialized agent instance
    """
    logger.info("==== Initializing Reasoning Agent with Chain of Thought support")

    # Initialize the agent with the provided parameters
    agent = Telco_Agent(
        model=model,
        tools=tools or [],  # Ensure tools is at least an empty list
        checkpointer=checkpointer,
        token_memory_limit=tokenlimit,
        system=system_instruction,
        cot_system_prompt=cot_system_prompt  # Pass CoT prompt
    )

    return agent.graph