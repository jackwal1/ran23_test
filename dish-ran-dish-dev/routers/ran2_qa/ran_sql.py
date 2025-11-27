from fastapi import APIRouter, status, Response
from routers.pydantic_model import ChatRequest
from fastapi import HTTPException
from utils.logger import logger
import os
from starlette.responses import StreamingResponse
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

from graph.ran2_qa.ran_sql_graph import initialize_agent
from utils.ran2_qa.ran_sql_agent_utils import process_chunks
import asyncio
try:
    # Fetch environment variables
    url_for_pdf_links = os.environ["URL_FOR_PDF_LINKS"]
except Exception as e:
    print(e)
    print("Loading Environmment Variables from local .env file")
    load_dotenv()
    url_for_pdf_links = os.environ["URL_FOR_PDF_LINKS"]

agentic_ran_sql = APIRouter(prefix='/watsonx/ran', tags=['RAN Part - 2 : QA'])


'''async def process_chat_stream1(message: str, thread_id: str):
    langgraph_agent = await initialize_agent()
    async  for step in langgraph_agent.astream(
            {"messages": [HumanMessage(content=message)]},
            {"configurable": {"thread_id": thread_id}},
    ):
        for node, values in step.items():
            print(f"stream_response -> {node}")
            print(f"stream_response -> {values}")
            node_output = {"node": node}
            yield json.dumps(node_output).encode("utf-8") + b"\n\n"'''

async def process_chat_stream(message: str, thread_id: str):
    langgraph_agent = await initialize_agent()
    buffer = ""
    async for event in langgraph_agent.graph.astream_events({"messages": [HumanMessage(content=message)]},
                                            {"configurable": {"thread_id": thread_id}}, version="v2"):
        await process_chunks(event)
        kind = event["event"]
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            content = chunk.content if hasattr(chunk, "content") else str(chunk)

            if content:  # Ensure content is not empty
                buffer += content

            yield content
            await asyncio.sleep(0.1) 

            
@agentic_ran_sql.post(
    "/ran_sql",
    summary="RAN AI Assistant - Agentic RAG implementation",
    status_code=status.HTTP_200_OK,
    response_description="Answer for the user question from watson discovery using ReAct model",
)
async def query_user_question(request: ChatRequest):
    """
     ### RAN AI Assistant - Agentic RAG implementation
    Query the watson discovery for the user question:
    **Input:**
    - user_question: questions from the user

    **Output:**
    - A response for the user question
    """
    logger.log(f'user_question:{request.message}')
    try:
        return StreamingResponse(process_chat_stream(request.message,request.thread_id),
                                 media_type="text/event-stream")
    except Exception as e:
        logger.log(f'user_question:{request.user_question}, error: {e} - query : ERROR')
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")