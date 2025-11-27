# from langgraph.prebuilt import create_react_agent
# from langgraph.graph import MessagesState
# from utils.ran2_qa.ran_sql_tools import tools
# from utils.ran2_qa.ran_sql_agent_utils import manage_memory
# from llms.llms import llama_chatmodel_react_ran_sql
# import utils.ran2_qa.ran_sql_memory_checkpoint as memory


# async def initialize_agent():
#     checkpointer = await memory.get_checkpointer()

#     # Create the agent with the initialized checkpointer
#     langgraph_agent = create_react_agent(
#         model=llama_chatmodel_react_ran_sql,
#         tools=tools,
#         checkpointer=checkpointer,  # Pass the actual checkpointer instance
#         state_modifier=manage_memory
#     )
#     return langgraph_agent

###

# import logging
# #from langgraph.prebuilt import create_react_agent
# from langgraph.graph import MessagesState
# from utils.tools_utils import tools
# from utils.network_agent_utils import manage_memory
# from llms.llms import llama_chatmodel_react
# import utils.memory_checkpoint as memory

import logging
from langgraph.graph import MessagesState
from utils.ran2_qa.ran_sql_tools import tools
from utils.ran2_qa.ran_sql_agent_utils import manage_memory
from llms.llms import llama_chatmodel_react_ran_sql
import utils.ran2_qa.ran_sql_memory_checkpoint as memory
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, filter_messages, AIMessage
import json

from utils import constants as CONST


# Setup the logging configuration
log_level = getattr(logging,CONST.LOG_LEVEL )
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(filename)s - Line: %(lineno)d - %(message)s"
)
logger = logging.getLogger()


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

class Agent:
    def __init__(self, model, tools, checkpointer, system=""):
        self.system = system
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_conditional_edges("llm", self.exists_action, {True: "action", False: END})
        graph.add_edge("action", "llm")
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

    async def call_llm(self, state: AgentState):
        messages = state['messages']
        messages = await manage_memory(state)
        message = await self.model.ainvoke(messages)
        return {'messages': [message]}

async def initialize_agent():
    checkpointer = await memory.get_checkpointer()
    langgraph_agent = Agent(llama_chatmodel_react_ran_sql, tools, checkpointer=checkpointer)

    return langgraph_agent

def is_valid_json(json_string):
    try:
        json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False