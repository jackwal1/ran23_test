import logging
#from langgraph.prebuilt import create_react_agent
from langgraph.graph import MessagesState
from utils.tools_utils import tools
from utils.network_agent_utils import manage_memory, display_messages
from llms.llms import llama_chatmodel_react, generate_summary
import utils.memory_checkpoint as memory

from utils.tokenization import get_tokens
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, filter_messages, AIMessage, RemoveMessage
import json
from rich.console import Console

console = Console()

from utils import constants as CONST
'''async def initialize_agent():
    checkpointer = await memory.get_checkpointer()

    # Create the agent with the initialized checkpointer
    langgraph_agent = create_react_agent(
        model=llama_chatmodel_react,
        tools=tools,
        checkpointer=checkpointer,  # Pass the actual checkpointer instance
        state_modifier=manage_memory
    )

    return langgraph_agent'''

# Setup the logging configuration
log_level = getattr(logging,CONST.LOG_LEVEL )
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(filename)s - Line: %(lineno)d - %(message)s"
)
logger = logging.getLogger()


class AgentState(MessagesState):
    summary: str

class Agent:
    def __init__(self, model, tools, checkpointer, token_memory_limit=100000, system=""):
        self.system = system
        self.token_memory_limit = token_memory_limit
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("memory", self.filter_memory)
        graph.add_conditional_edges("llm", self.exists_action, {True: "action", False: "memory"})
        graph.add_edge("action", "llm")
        graph.add_edge("memory", END)
        graph.set_entry_point("llm")
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)

    async def exists_action(self, state: AgentState):
        if state['messages'] and isinstance(state['messages'][-1], AIMessage):
            result = state['messages'][-1]
            tool_calls_from_kwargs = result.additional_kwargs.get('tool_calls', [])
            if tool_calls_from_kwargs:
                corrected_tool_calls = []
                for call in tool_calls_from_kwargs:
                    try:
                        # Extract name and arguments
                        name = call['function']['name']
                        args = json.loads(call['function']['arguments'])
                        # Extract or set id and type
                        id = call['id']
                        type = 'tool_call'  # Default type
                        corrected_tool_calls.append({
                            'name': name,
                            'args': args,
                            'id': id,
                            'type': type
                        })
                    except (KeyError, json.JSONDecodeError):
                        print(f"Error processing tool call: {call}")
                result.tool_calls = corrected_tool_calls
                state['messages'][-1] = result  # Update the state with the corrected AIMessage
            return len(result.tool_calls) > 0
        return False

    async def take_action(self, state: AgentState):
        tool_calls = state['messages'][-1].tool_calls
        results = []
        for t in tool_calls:
            print(f"Calling: {t}")
            # Use an async call to the tool. This assumes that each tool now has an 'ainvoke' method.
            result = await self.tools[t['name']].ainvoke(t['args'])
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
        print("Back to the model!")
        return {'messages': results}

    async def filter_memory(self, state: AgentState):

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
            history_str += msg.content + "\n"

        num_tokens = get_tokens(history_str)
        print(f"Tokens in Chat History: {num_tokens}")

        # Trim and summarize history if over token limit
        if num_tokens > self.token_memory_limit:
            print(f"We are going to trim and summarize the history")
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
                summarized_text = await generate_summary(
                    " ".join([msg.content for msg in msgs_to_sum]), summary
                )
                summarized_text = "Summary:\n" + summarized_text
                print(f"Successfully summarized history")
                print(f"Trimmed {trim_idx+1} messages")
                print(f"{summarized_text}")
                print(f"Deleting trimmed messages::::::")
                print(msgs_to_sum)
                delete_messages = [RemoveMessage(id=m.id) for m in msgs_to_sum]
                return {"summary": summarized_text, "messages": delete_messages}
            else:
                print(f"History not long enough to summarize and trim")

    async def call_llm(self, state: AgentState):
        messages = state['messages']

        # Add System Prompt And Summary if they exist
        if self.system or state.get("summary", ""):
            print("Adding system prompt and/or summary...")
            messages = [
                           SystemMessage(content=self.system + state.get("summary", ""))
                       ] + messages

            print("<================= messages to LLM  ==================> ")
            await display_messages(messages)
        else:
            messages = await manage_memory(state)

        message = await self.model.ainvoke(messages)

        print("<================= Reply from LLM  ==================> ")
        await display_messages([message])
        console.print(f"[bold magenta]Token Usage: {message.usage_metadata}")

        return {'messages': [message]}

async def initialize_agent():
    checkpointer = await memory.get_checkpointer()
    langgraph_agent = Agent(llama_chatmodel_react, tools, checkpointer=checkpointer, token_memory_limit=CONST.MAX_TOKEN_THRESHOLD)

    return langgraph_agent

def is_valid_json(json_string):
    try:
        json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False
