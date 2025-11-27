import logging
from typing import Annotated, Sequence, TypedDict, List, AsyncIterator, Dict
from langgraph.graph import StateGraph, END, add_messages
from uuid import UUID
import traceback
from llms.llms import query_classifier, analyzer
# from utils.wd_utils import wd_query_extract_format_response
from utils.ran_part_one.wd_utils_with_filters import main_wd_query_and_process
from utils import constants as CONST


# Setup the logging configuration
log_level = getattr(logging,CONST.LOG_LEVEL )
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(filename)s - Line: %(lineno)d - %(message)s"
)
logger = logging.getLogger()
## Graph State
class RANState(TypedDict):
    messages: Annotated[Sequence[str], add_messages]
    context: str
    user_query: str
    classifier: str
    retriever: str
    retriever_output: str
    query_type: str
    final_output: dict
    conversation_id: str
    user_id: str
    message_id: str
    title: str
    temp_session: UUID
    file_sources: str

#################### Graph Flow Node Functions ###########

async def ran_query_classifier(state: RANState):
    """
    """
    try:
        logger.info(f'user_question:{state.get("user_query","NA")} :: Node 1 - ran_query_classifier - START')
        ####
        response = await query_classifier(state)
        category = response.get('query_type', ['NA'])
        # retrieval flow
        if len(category) == 1 and "ran_docs" in category:
            classifier = "ran_docs"
        elif len(category) == 2 and "public" in category and "ran_docs" in category:
            classifier = "ran_docs"
        elif len(category) == 1 and "public" in category:
            classifier = "ran_public"
        elif len(category) == 1 and "fallback" in category:
            classifier = "ran_fallback"
        else:
            classifier = None
        logger.info(f'user_question:{state.get("user_query","NA")}, classifier - {classifier}:: ll_response:{response} :: Node 1 - ran_query_classifier - END')
        return {
            "retriever": classifier,
            "final_output": response,
            "classifier":response.get('query_type', 'NA')
        }
    except Exception as e:
        logger.error(f'user_question:{state.get("user_query","NA")} :: Node 1 - ran_query_classifier - ERROR')
        traceback.print_exc()

async def ran_docs(state: RANState):
    """
    """
    try:
        logger.info(f'user_question:{state.get("user_query","NA")} :: Node 2 - ran_docs - START')
        ####
        # ran_docs_data = await wd_query_extract_format_response(state['final_output'], state['user_query'])
        ran_docs_data = await main_wd_query_and_process(state['user_query'])
        # Preprocess the data
        if ran_docs_data is not None:
            if len(ran_docs_data.get('passages', '')) > 0:
                response = ran_docs_data.get("passages", "Not Available")
                s3_files = ran_docs_data.get("s3_url", [])
                file_sources = {"s3_urls":s3_files}
                confidence_score = ran_docs_data.get("confidence_score", [])
            else:
                response = "Not Available"
                file_sources = {}
                confidence_score=[]

            logger.info(f'user_question:{state.get("user_query","NA")}, s3_files:{s3_files}, confidence_scores : {confidence_score} :: Node 2 - ran_docs - END')

            return {
                "retriever": "ran_docs",
                "final_output": response,
                "file_sources": file_sources
            }
        # elif ran_docs_data=="WD_CONNECTION_DATA_ERROR":
        #     return {
        #         "retriever": "ran_docs",
        #         "final_output": "WD_O"
        #     }
        elif ran_docs_data is None:
            return {
                "retriever": "ran_docs",
                "final_output": "WD_0",
            }
    except Exception as e:
        logger.error(f'user_question:{state.get("user_query","NA")} :: Node 2 - ran_docs - ERROR')
        traceback.print_exc()

async def ran_analyzer(state: RANState):
    """
    """
    try:
        logger.linfog(f'user_question:{state.get("user_query","NA")} :: Node 3 - ran_analyzer - START')
        ##
        final_output = state['final_output']
        # logger.log(f'DATA :: Node 3 - ran_analyzer --- {len(final_output)}')
        if final_output == "WD_O":
            response = [{"type": "summary_text", "content": "Something went wrong while connecting Watson Discovery."}]
            return {
                "retriever": "ran_analyzer",
                "final_output": response
            }
        elif final_output == "WD_1":
            response = [{"type": "summary_text", "content": "Something went wrong while preprocessing the Watson Discovery results."}]
            return {
                "retriever": "ran_analyzer",
                "final_output": response
            }
        else:
            res = await analyzer(state)
            response = [{"type": "summary_text", "content": res}]
            logger.info(f'user_question:{state.get("user_query","NA")} :: Node 3 - ran_analyzer - END')
            return {
                "retriever": "ran_analyzer",
                "final_output": response,
            }
    except Exception as e:
        logger.error(f'user_question:{state.get("user_query","NA")} :: Node 3 - ran_analyzer - ERROR')
        traceback.print_exc()
        return None

async def ran_fallback(state: RANState):
    """
    """
    try:
        logger.info(f'user_question:{state.get("user_query","NA")} :: Node 2 - ran_fallback - START')
        ####
        starter_line = "The question is not related to the RAN documents that I have been trained on. Please provide a relevant query and I will be happy to help!"
        resp = [{"type": "text", "content": starter_line}]
        logger.info(f'user_question:{state.get("user_query","NA")} :: Node 2 - ran_fallback - END')
        return {
            "retriever": "ran_fallback",
            "final_output": resp
        }
    except Exception as e:
        logger.error(f'user_question:{state.get("user_query","NA")} :: Node 2 - ran_fallback - ERROR')
        traceback.print_exc()


### Define Nodes
workflow = StateGraph(RANState)
workflow.add_node("ran_query_classifier", ran_query_classifier)
workflow.add_node("ran_docs", ran_docs)
workflow.add_node("ran_analyzer", ran_analyzer)
workflow.add_node("ran_fallback", ran_fallback)

query_classifier_nodes = {
    "ran_docs": "ran_docs",
    "ran_public": "ran_docs",
    "ran_fallback":"ran_fallback"
}

def ran_issue_classifier_route_retrievers(state: RANState) -> Sequence[str]:
    return state.get("retriever", [])

workflow.add_conditional_edges(
    "ran_query_classifier", ran_issue_classifier_route_retrievers, query_classifier_nodes
)

workflow.set_entry_point("ran_query_classifier")
workflow.add_edge("ran_docs", "ran_analyzer")
workflow.add_edge("ran_analyzer", END)
workflow.add_edge("ran_fallback", END)

graph = workflow.compile()
# print(graph.show())