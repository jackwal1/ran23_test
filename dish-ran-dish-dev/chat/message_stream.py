from utils.log_init import logger
from langchain_core.messages import HumanMessage, AIMessage
from agent.supervisor_agent import initialize_supervisor_agent
from agent.ran_device_agent import initialize_ran_device_agent
import json
from utils import constants as CONST
# Available agents mapping (easy to extend)
# AGENTS = {
#         "supervisor": initialize_supervisor_agent,    
#         "ran_device": initialize_ran_device_agent,              
# }

supervisor_agent= None

# async def _initialise_supervisor_agent():
#     supervisor_agent = await initialize_supervisor_agent()
#     return supervisor_agent

# process message streams
async def process_message_stream(message: str, thread_id: str, agent: str):
    try:
        # initialize agent
        # agent_runner = AGENTS[agent]
        # langgraph_agent = await agent_runner()  # Initialize selected agent
        global supervisor_agent
        if supervisor_agent is None:
            supervisor_agent = await initialize_supervisor_agent()
        # Initialize our source collection to gather sources during streaming
        sources = []
        is_streaming_complete = False
        logger.info(f'Process message stream for agent --> {agent}')
        # logger.info(f'self.thread_id type --> {self.thread_id}')
        # logger.info(f'message --> {message}')
        async for event in supervisor_agent.astream_events(
            {"messages": [HumanMessage(content=message)]},
            {"configurable": {"thread_id": thread_id}},
            version="v2",
        ):  
            try:
                event_type = event["event"]
                logger.info(f'event_type -> {event_type}')
                if event_type.endswith("_stream") and "chunk" in event.get("data", {}):
                    logger.info(f'event -> {event}')
                    chunk = event["data"].get("chunk")
                    if isinstance(chunk, AIMessage):
                        content = getattr(chunk, "content", "")
                        if content:
                            item = {'type': 'text', 'content': content}
                            yield f"data: {json.dumps(item)}"
                            yield "\n\n"
                            #yield content
                elif event_type == "on_tool_start":
                    logger.info(f'event -> {event}')
                    tool_data = event.get("data", {})
                    tool_name = tool_data.get("name") or tool_data.get("tool_call") or tool_data.get("tool") or None
                    if not tool_name and "function" in tool_data:
                        tool_name = tool_data["function"].get("name")
                    if not tool_name:
                        tool_name = str(tool_data) if tool_data else "Unknown tool"
                    logger.info(f"Calling tool: {tool_name}")
                elif event_type == "on_tool_end":
                    logger.info(f"Tool execution completed")
                    logger.info(event)
                    # Extract source information from ToolMessage
                    tool_output = event["data"]["output"]

                    if isinstance(tool_output, str):
                        # Split content into lines, handling potential line breaks
                        lines = tool_output.split('\n')
                        current_file = None

                        for line in lines:
                            # Extract file name using string operations
                            if line.startswith('file_name ::'):
                                current_file = line.replace('file_name ::', '').strip()

                            # When we have file name, store them
                            if current_file:
                                source_tuple = (current_file)
                                if source_tuple not in sources:
                                    sources.append(source_tuple)
                                    # Reset for next pair
                                    current_file = None

                elif event_type == "on_chain_end":
                    # Mark streaming as complete when the chain ends
                    is_streaming_complete = True                

                        # After all streaming is complete, append sources if we have any
                if is_streaming_complete and sources:
                    # Add formatting for the sources section
                    source_item = {'type': 'text', 'content': "\n\n**Sources:**\n"}
                    yield f"data: {json.dumps(source_item)}"
                    yield "\n\n"

                    # Generate and yield source links individually
                    for file_name in sources:
                        # Format each source as a markdown bullet point with HTML anchor tag
                        source_link = f'• <a href="{CONST.FILE_ENDPOINT}{file_name}" target="_blank">{file_name}</a>\n'
                        source_file_item = {'type': 'text', 'content': source_link}
                        yield f"data: {json.dumps(source_file_item)}"
                        yield "\n\n"

            except Exception as e:
                logger.error(f'Error during streaming: {str(e)}')
                break
    except Exception as e:
        logger.error(f'Error in process_message_stream: {str(e)}')
        # logger.error(traceback.format_exc())
        error_message = {'type': 'error', 'content': "I encountered an issue while processing your request. Please try again."}
        yield f"data: {json.dumps(error_message)}"
        yield "\n\n"
        

