from fastapi import APIRouter, status, Response
from routers.pydantic_model import queryRequest
from fastapi import HTTPException
from utils.logger import logger
import datetime
from typing import Annotated, Sequence, TypedDict, List, AsyncIterator
import asyncio
import json
from starlette.responses import StreamingResponse
from graph.nodes import graph

ranQuerygraphv2 = APIRouter(prefix='/watsonx/ran', tags=['RAN Part - 1 - LangGraph based'])

## Functions to expose Streaming Graph
# async def streamGraph(initial_state) -> AsyncIterator[bytes]:
#     print("Started Graph---------------")
#     response = graph.astream(initial_state, {"recursion_limit": 20})
#     print(":response: ", response)
#     async for obj in response:
#         print('trying to yield ==> ', obj)
#         # nodes_list = ['check_relevance']
#         # for node in nodes_list:
#         #     if node in obj.keys():
#         #         obj['generate_response'] = obj.pop(node)
#         ##
#         if "final_output" in obj.keys():
#             if type(obj) is datetime.date or type(obj) is datetime.datetime:
#                 yield json.dumps(obj.isoformat()).encode('utf-8') + b'\n'
#             else:
#                 yield json.dumps(obj).encode('utf-8') + b'\n'
#             await asyncio.sleep(1)


async def streamGraph(initial_state) -> AsyncIterator[bytes]:
    buffer = ""
    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event["event"]
        print("EVENT-----\n",event)
        # Send start event
        if (
            kind == "on_chat_model_start"
            and event["metadata"]["langgraph_node"] == "ran_analyzer"
        ):
            yield json.dumps({"type": "start", "element_type": "text"})

        # Handle streamed content
        if (
            event.get("metadata", {}).get("langgraph_node")
            == "ran_analyzer"
        ):
            if kind == "on_chat_model_stream":

                chunk = event["data"]["chunk"]
                content = chunk.content if hasattr(chunk, "content") else str(chunk)

                if content:  # Ensure content is not empty
                    buffer += content

                    # Send buffered content if conditions met
                    # if len(buffer) >= 5 or content.endswith((".", "!", "?", "\n")):
                    # yield buffer  # Sending the buffer as a plain string
                    item_copy = {"type": "text", "content": buffer}
                    yield json.dumps(item_copy)
                    await asyncio.sleep(0.1)  # Simulate processing time
                    buffer = ""
            if kind == "on_chat_model_end":
                # yield json.dumps({"type": "text", "content": "sources:links will come here"})
                # yield json.dumps({"type": "end", "element_type": "text"})
                pass

        elif kind == "on_chain_end" and event.get("name", {}) == "LangGraph":
             ### add for the sources here
            file_source_response = event["data"]["output"]
            files = file_source_response.get("file_sources", 'NA')
            yield json.dumps({"type": "text", "content": files})
            yield json.dumps({"type": "end", "element_type": "text"})

            # yield "starting check relevance node \n"  # Sending a plain string
            relevance_node_response = event["data"]["output"]
            # logger.log(f"relevance_node_response : {relevance_node_response}")
            # Check if "summary_text" is present in "final_output"
            summary_present = any(
                item.get("type") == "summary_text"
                for item in (relevance_node_response.get("final_output") or [])
            )
            
            # print(summary_present)
            if summary_present:
                pass
            else:
                # print("summary_text is not present in final_output.")
                # print(relevance_node_response.get("final_output", []))
                # print("######")
                for item in (relevance_node_response.get("final_output") or []):
                    # print(item)

                    # Add start marker
                    yield json.dumps({"type": "start", "element_type": item["type"]})
                    await asyncio.sleep(0.1)
                    # Stream static data (tables) in full
                    if item["type"] == "table":
                        # print(f"Streaming table part: {json.dumps(item)}")
                        yield json.dumps(item)

                    # Stream dynamic text data incrementally
                    elif item["type"] == "text":
                        content = item["content"]
                        chunk_size = 5
                        streamed_text = ""

                        # Stream content in chunks
                        for i in range(0, len(content), chunk_size):
                            chunk = content[i : i + chunk_size]
                            streamed_text += chunk
                            item_copy = {"type": "text", "content": streamed_text}

                            # print(f"Streaming dynamic text part: {json.dumps(item_copy)}")
                            yield json.dumps(item_copy)
                            await asyncio.sleep(0.1)  # Simulate processing time
                            streamed_text = ""

                    # Add end marker
                    yield json.dumps({"type": "end", "element_type": item["type"]})
        
        # Handle end event
        elif event["name"] == "end_event":
            if buffer:  # Send any remaining buffered content
                yield buffer
            yield json.dumps({"type": "end", "element_type": "text"})
            yield "end\n"  # Indicate the end of the stream
            break



@ranQuerygraphv2.post(
    "/ran_graphv2",
    summary="RAN AI Assistant - Answer for the user question",
    status_code=status.HTTP_200_OK,
    response_description="Answer for the user question from watson discovery",
)
async def query_user_question(request: queryRequest, response: Response):
    """
    ### RAN AI Assistant
    Query the database for the user question:
    - gpl: Questions related to the General Public License, including its usage, restrictions, and implications.

    **Input:**
    - user_question : The user question

    **Output:**
    - A response for the user question
    """
    logger.log(f'user_question:{request.user_question} - API : classify : START')
    try:
        initial_state = {
            "user_query": request.user_question,
            # "conversation_id": conv_id,
            # "user_id": user_id,
        }
        return StreamingResponse(streamGraph(initial_state), media_type="text/event-stream")
    except Exception as e:
        logger.log(f'user_question:{request.user_question}, error: {e} - query : ERROR')
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")