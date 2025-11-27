from dotenv import load_dotenv
from rich.console import Console
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, filter_messages, SystemMessage
from graph.agent_graph_nodes import initialize_agent
from utils.network_agent_utils import process_chunks, process_checkpoints, process_chunks_non_streaming
import utils.memory_checkpoint as memory
import platform

load_dotenv()

rich = Console()

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
async def main():
    langgraph_agent = await initialize_agent()
    checkpointer = await memory.get_checkpointer()
    # Loop until the user chooses to quit the chat
    while True:
        # Get the user's question and display it in the terminal
        user_question = input("\nUser:\n")

        # Check if the user wants to quit the chat
        if user_question.lower() == "quit":
            rich.print(
                "\nAgent:\nHave a nice day! :wave:\n", style="black on white"
            )
            break

        # Use the async stream method of the LangGraph agent to get the agent's answer
        thread_id = "1008"
        async for chunk in langgraph_agent.astream(
                {"messages": [HumanMessage(content=user_question)]},
                {"configurable": {"thread_id": thread_id}},
        ):
            # Process the chunks from the agent
            await process_chunks_non_streaming(chunk)

            # Use the async list method of the memory to list all checkpoints that match a given configuration
            checkpoints = checkpointer.alist({"configurable": {"thread_id": thread_id}})
            #Process the checkpoints from the memory in an async way
            await process_checkpoints(checkpoints)


if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())