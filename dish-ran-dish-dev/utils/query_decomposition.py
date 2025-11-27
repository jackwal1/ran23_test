import logging
from typing import List, Optional
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from llms.llms import llama_chatmodel_react

# ──────────────────────────────── logging ────────────────────────────────
from utils import constants as CONST

log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RAN")

# ───────────────────────────── schema ─────────────────────────────

class Search(BaseModel):
    query: str
    sub_queries: List[str]
# ───────────────────────────── prompt ─────────────────────────────

# Define few-shot examples
examples = [
    {
        "question": "What is the a5-threshold2-rsrp for n70 for Samsung and Mavenir",
        "answer": Search(
            query="What is the a5-threshold2-rsrp for n70 for Samsung and Mavenir",
            sub_queries=["What is the a5-threshold2-rsrp for n70 for Samsung", "What is the a5-threshold2-rsrp for n70 for Mavenir"]
        )
    },
    {
        "question": "What is the value of the timer t310 in Mavenir",
        "answer": Search(
            query="What is the value of the timer t310 in Mavenir",
            sub_queries=["What is the value of the timer t310 in Mavenir"]
        )
    },
    {
        "question": "What is the a5-threshold2-rsrp for n70",
        "answer": Search(
            query="What is the a5-threshold2-rsrp for n70",
            sub_queries=["What is the a5-threshold2-rsrp for n70 for Samsung", "What is the a5-threshold2-rsrp for n70 for Mavenir"]
        )
    },
    {
        "question": "What is the DISH GPL value for the parameter zeroCorrelationZoneCfg?",
        "answer": Search(
            query="What is the DISH GPL value for the parameter zeroCorrelationZoneCfg?",
            sub_queries=["What is the DISH GPL value for the parameter zeroCorrelationZoneCfg for Samsung", "What is the DISH GPL value for the parameter zeroCorrelationZoneCfg for Mavenir"]
        )
    }
]

# Convert examples to messages
few_shot_messages = []
for example in examples:
    few_shot_messages.append(HumanMessage(content=example["question"]))
    few_shot_messages.append(AIMessage(content=example["answer"].json()))

# Define the system message and prompt template
system = """You are an expert at converting user questions into sub queries based on vendor.
Given a question, return a list of sub queries optimized to retrieve the most relevant results.

Decomposition rules:
1. If the query mentions neither Samsung nor Mavenir, generate two sub-queries:
   - one targeting Samsung
   - one targeting Mavenir
2. If the query mentions exactly one of these vendors, return the original query unchanged.
3. If the query mentions both Samsung and Mavenir, split into two versions, each mentioning only one vendor.
"""
# ───────────────────────── core function ─────────────────────────
async def decompose_query(query: str) -> Search:
    """
    Decompose the user query into vendor-specific sub-queries
    using LlamaIndex structured output.
    """
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system),
            MessagesPlaceholder("examples", optional=True),
            ("human", "{question}"),
        ])

        structured_llm = llama_chatmodel_react.with_structured_output(Search)

        # Create the query analyzer chain with few-shot examples
        query_analyzer_with_examples = (
                {"question": RunnablePassthrough()} | prompt.partial(examples=few_shot_messages) | structured_llm
        )

        result = await query_analyzer_with_examples.ainvoke(query)
        logger.info(f"Decomposed '{query}' → {result.sub_queries}")
        return result

    except Exception as e:
        logger.error(f"Decomposition failed for query='{query}': {e}", exc_info=True)
        # Fallback: return the original query as a single sub-query
        return Search(query=query, sub_queries=[query])

# ──────────────────────── wrapper for FastAPI ───────────────────────
async def process_user_query(query: str) -> List[str]:
    # Decompose the query
    result = await decompose_query(query)

    # Prepare bullet-point list
    bullets = "\n".join(f"- {sub}" for sub in result.sub_queries)
    log_message = f"Original query: {query}\nSub-queries:\n{bullets}"

    # Log the message
    logger.info(log_message)

    return result.sub_queries

