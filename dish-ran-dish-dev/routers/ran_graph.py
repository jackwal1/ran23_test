
import logging
from fastapi import APIRouter, status, Response
from routers.pydantic_model import queryRequest
from fastapi import HTTPException
from typing import AsyncIterator
import asyncio
import json
import os
from starlette.responses import StreamingResponse
from graph.nodes import graph
from dotenv import load_dotenv
from utils import constants as CONST


# Setup the logging configuration
log_level = getattr(logging,CONST.LOG_LEVEL )
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(filename)s - Line: %(lineno)d - %(message)s"
)
logger = logging.getLogger()
try:
    # Fetch environment variables
    url_for_pdf_links = os.environ["URL_FOR_PDF_LINKS"]
except Exception as e:
    print(e)
    print("Loading Environmment Variables from local .env file")
    load_dotenv()
    url_for_pdf_links = os.environ["URL_FOR_PDF_LINKS"]

ranQuerygraph = APIRouter(prefix='/watsonx/ran', tags=['RAN Part - 1 - LangGraph based'])
## Functions to expose Streaming Graph
async def streamGraph(initial_state) -> AsyncIterator[bytes]:
    buffer = ""
    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event["event"]
        if kind == "on_chain_end" and event.get('name', {}) == "LangGraph":
            yield f"data: {json.dumps({'type': 'start', 'element_type': 'text'})}"
            yield "\n\n"
            relevance_node_response = event["data"]["output"]
            summary_present = any(item.get('type') == 'summary_text' for item in (relevance_node_response.get("final_output") or []))

            if summary_present:
                # print(relevance_node_response)
                chunk_ = relevance_node_response.get('final_output',{})
                content = [item['content'] for item in chunk_ if item['type'] == 'summary_text'][0]
                # content = await replace_incident_with_link(content)
                # item_copy = {'type': 'text', 'content': content}
                # print(content)
                # yield f"data: {json.dumps(item_copy)}"
                # yield "\n\n"

                ###
                chunk_size = 5
                streamed_text = ""

                # Stream content in chunks
                for i in range(0, len(content), chunk_size):
                    chunk = content[i:i + chunk_size]
                    streamed_text += chunk
                    item_copy = {'type': 'text', 'content': streamed_text}

                    # print(f"Streaming dynamic text part: {json.dumps(item_copy)}")
                    # yield json.dumps({'data':item_copy})
                    yield f"data: {json.dumps(item_copy)}"
                    yield "\n\n"
                    await asyncio.sleep(0.1)  # Simulate processing time
                    streamed_text = ""
                ###
                
            else:
                # print("summary_text is not present in final_output.")
                click_here_table_check_cnt = 0
                for item in (relevance_node_response.get("final_output") or []):

                    # Add start marker
                    # yield json.dumps({'data':{'type': 'start', 'element_type': item['type']}})
                    # if item['type'] == "text":
                    #     yield f"data: {json.dumps({'type': 'start', 'element_type': item['type']})}"
                    #     yield "\n\n"
                        
                    # Stream static data (tables) in full
                    
                    if item['type'] == 'table':
                        click_here_table_check_cnt +=1
                        # print("item from streaming---\n")
                        # print(item)
                        # print(f"Streaming table part: {json.dumps(item)}")
                        if click_here_table_check_cnt == 1:
                            item_table_start = {'type': 'text', 'content': '\n'}
                            # print("#######################################")
                            # print(item["content"])
                            # item_table_with_liks  = await convert_to_markdown(item["content"])
                            item_table_with_liks  = item["content"]
                            # item_table = {'type': 'text', 'content': await replace_incident_with_link(item_table_with_liks)}
                            item_table = {'type': 'text', 'content': item_table_with_liks}
                            # yield json.dumps(item_table)
                            yield f"data: {json.dumps(item_table_start)}"
                            yield "\n\n"
                            yield f"data: {json.dumps(item_table)}"
                            # print("#######################################")
                            # print(item_table)
                            yield "\n\n"
                        elif click_here_table_check_cnt == 2:
                            item_table_start = {'type': 'text', 'content': '\n'}
                            # content_markdown = await convert_to_markdown_with_html(item["content"])
                            content_markdown = item["content"]
                            # item_table = {'type': 'text', 'content': await replace_incident_with_link(content_markdown)} # add html tag for click here for more
                            item_table = {'type': 'text', 'content': content_markdown} # add html tag for click here for more
                            yield f"data: {json.dumps(item_table_start)}"
                            yield "\n\n"
                            yield f"data: {json.dumps(item_table)}"
                            yield "\n\n"

                    # Stream dynamic text data incrementally - # this is for "here is the requested info" only
                    elif item['type'] == 'text':
                        content = item['content']
                        # content = await replace_incident_with_link(item['content'])
                        # print(content)
                        chunk_size = 5
                        streamed_text = ""

                        # Stream content in chunks
                        for i in range(0, len(content), chunk_size):
                            chunk = content[i:i + chunk_size]
                            streamed_text += chunk
                            item_copy = {'type': 'text', 'content': streamed_text}

                            # print(f"Streaming dynamic text part: {json.dumps(item_copy)}")
                            # yield json.dumps({'data':item_copy})
                            yield f"data: {json.dumps(item_copy)}"
                            yield "\n\n"
                            await asyncio.sleep(0.1)  # Simulate processing time
                            streamed_text = ""
            # conversation_id = relevance_node_response.get("conversation_id", "NA")
            # user_id = relevance_node_response.get("user_id", "NA")
            # message_id = relevance_node_response.get("message_id", "NA")
            # title = relevance_node_response.get("title", "NA")        
            # Add end marker
            ## add the files here
            try:
                file_source_response = event["data"]["output"]
                files = file_source_response.get("file_sources", "NA")
                classifier = file_source_response.get("classifier", "NA")
                if len(classifier) > 1 or "ran_docs" in classifier:
                    s3_urls = files.get("s3_urls", [])
                    # s3_urls.append("s3://dl-dish-wrls-whlsl-network-documents-cpni-p/mops/samsung/817 cUSM Scale-In and NE Realignment MOP for SVR23B P2_v1.0 - PRELIMINARY.docx")
                    # s3_urls.append("s3://dl-dish-wrls-whlsl-network-documents-cpni-p/mops/samsung/817 cUSM Scale-In and NE Realignment MOP for SVR23B P2_v1.0 - PRELIMINARY.doc")
                    # print(s3_urls)
                    if len(s3_urls) > 0:
                        data = json.dumps({'type': 'text', 'content': '<br><br><span style="color: blue;">Source:</span>'})
                        yield f"data: {data}"
                        yield "\n\n"
                        # print("----", s3_urls)
                        for s3_path in s3_urls:
                            if s3_path!= "NA":
                                file_name = s3_path.replace("s3://", "", 1).split("/")[-1]
                                html_render = f'<br><a href="{url_for_pdf_links}?s3_file_url={s3_path}" target="_blank">{file_name}</a>'
                                yield f"data: {json.dumps({'type': 'text', 'content': html_render})}"
                                yield "\n\n"
            except Exception as e:
                print("Exp --> ", e)
                logger.error(f'Error in while creating link for s3_url')
                # yield "\n\n"
                # data = json.dumps({'type': 'text', 'content': 'Not found any sources'})
                # yield f"data: {data}"
                # yield "\n\n"

            yield f"data: {json.dumps({'type': 'end', 'element_type': 'text'})}"
            # yield "\n\n"
            # # yield f"data: {json.dumps({'type': 'text', 'conversation_id':conversation_id, 'user_id':user_id, 'message_id':message_id, 'title':title})}"
            # yield "\n\n"

        # Handle end event
        elif event['name'] == "end_event":
            if buffer:  # Send any remaining buffered content
                yield buffer
            yield "end\n"  # Indicate the end of the stream
            break
    
@ranQuerygraph.post(
    "/ran_graph",
    summary="RAN AI Assistant - Answer for the user question",
    status_code=status.HTTP_200_OK,
    response_description="Answer for the user question from watson discovery",
)
async def query_user_question(request: queryRequest, response: Response):
    """
    ### RAN AI Assistant
    Query the database for the user question:
    **Input:**
    - user_question: questions from the user

    **Output:**
    - A response for the user question
    """
    logger.info(f'user_question:{request.user_question} - API : classify : START')
    try:
        initial_state = {
            "user_query": request.user_question,
            # "conversation_id": conv_id,
            # "user_id": user_id,
        }
        return StreamingResponse(streamGraph(initial_state), media_type="text/event-stream")
    except Exception as e:
        logger.error(f'user_question:{request.user_question}, error: {e} - query : ERROR')
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")