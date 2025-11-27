from llama_index.core import PromptTemplate
from llms.llms import llamaindex_llama_3
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import json
from sqlalchemy import text
from pydantic import ConfigDict
from utils import constants as CONST
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import the database connection utility
from utils.postgres_util.dbutil import get_session

# Define the categories for classification
class QueryCategory(str, Enum):
    RAN_DOCUMENTS_QA = "RAN_DOCUMENTS_QA"
    RAN_CONFIGURATION = "RAN_CONFIGURATION"
    RAN_CONFIGURATION_UPDATE = "RAN_CONFIGURATION_UPDATE"

# Query classification model
class QueryClassificationModel(BaseModel):
    category: QueryCategory = Field(..., description="The category of the query")

# Function to fetch recent conversation history
async def fetch_conversation_history(session_id: str, limit: int = 5) -> List[Dict[str, str]]:
    """
    Fetch the last `limit` user queries and their categories (response_type)
    from conversation history for a given session_id.

    Args:
        session_id: The conversation session ID.
        limit:       Maximum number of entries to retrieve.

    Returns:
        A list of dicts, each with keys 'user_query' and 'category'.
    """
    try:
        async with get_session() as db_session:
            query = text("""
                SELECT 
                    user_query, 
                    response_type AS category
                FROM 
                    conversation_logs.messages
                WHERE 
                    conversation_id = :session_id
                ORDER BY 
                    created_timestamp DESC
                LIMIT :limit
            """ )
            result = await db_session.execute(query, {"session_id": session_id, "limit": limit})
            rows = result.fetchall()

            if not rows:
                logger.warning(f"No messages found for session_id={session_id}")
                return []

            rows.reverse()
            final_resp = [
                {
                    "user_query": row.user_query,
                    "category": CONST.CATEGORY_MAPPING.get(row.category, row.category)
                }
                for row in rows
            ]

            logger.info(f"Session history: \n{final_resp}")
            return final_resp
    except Exception as e:
        logger.error(f"Error fetching conversation history for session_id={session_id}: {e}")
        return []

# Function to load few-shot examples as a string
def _load_few_shot_examples() -> str:
    return """
        EXAMPLES OF * RAN_DOCUMENTS_QA * QUERIES:
        1. "I am seeing my DL CA throughput is degraded after upgrading to Mavenir SW 5231.2 P3. Is there any known defect? Is this fixed in 5232?"
        2. "What are the issues fixed in Mavenir 5232 Sw release?"
        3. "How does ANR Whitelist and blacklist work in Mavenir and Samsung?"
        4. "How many cells per DU are currently supported in Mavenir?"
        5. "How many users per cell are currently supported by Mavenir?"
        6. "How many cells are supported in Mavenir CUs?"
        7. "What new features or configurations have been added to Mavenir ANR in 5232?"
        8. "Tell me about the latency requirements for 5G networks."
        9. "What is the maximum supported power output for Mavenir RRUs?"
        10. "Can you explain how MIMO beam forming works in Mavenir products?"
        11. "How can I configure CA to trigger it faster for samsung?"
        
        EXAMPLES OF * RAN_CONFIGURATION * QUERIES:
        1. "What is the frequency band supported by the antenna model MX0866521402AR1?"
        2. "What is the operational state of CUCP with name JKRLA627035000?"
        3. "What is the operational state of CUUP with id 121014100?"
        4. "What is the operational & admin state of DU with name ATABY511000002?"
        5. "What is the administrative state of CUCP with user label NYNYC351030000?"
        6. "Show me the current tilt configuration for sector BOBOS01075F."
        7. "What is the current power setting for cell NYNYC351030001?"
        8. "Display the signal strength for node ATABY511000002."
        9. "List all active alarms for the Dallas region RAN equipment."
        10. "What's the temperature reading for CUUP with id 121014100?"
        11. "What is the value of the timer t311 in Samsung and Mavenir?"
        12. "Can you tell me which 551030000 NRCells deviate from GPL?"
        13. "What misalignment's do we have for gapOffset parameter in MCA (AOI) in Mavenir?"
        14. "What are the values of threshXHighP in Samsung and Mavenir for all Bands?"
        15. "What is the GPL-defined cellReselectionPriority baseline value for an NRCell on band n70 for Mavenir?"
        16. "Can you generate a summary report for all CUs in the DAL AOI where we observe GPL inconsistencies?"
        17. "What is the defined baseline for qRxLevMin (minimum required RSRP level) for all bands?"
        
        EXAMPLES OF * RAN_CONFIGURATION_UPDATE * QUERIES:
        1. "Please change tilt value to 30 for cell name BOBOS01075F."
        2. "I want to update a5 threshold2-rsrp for cell name BOBOS01075F to value 52."
        3. "Increase the transmission power for sector NYNYC351030001 to 43 dBm."
        4. "Modify the ANR settings for DU ATABY511000002 to include neighboring cell BOBOS01075F."
        5. "Enable carrier aggregation for CUUP 121014100."
        6. "Disable the sector BOBOS01075F for maintenance."
        7. "Update the frequency band for antenna MX0866521402AR1 to n77."
        8. "Change the admin state to ENABLED for CUCP JKRLA627035000."
        9. "Set the beam forming parameters for cell NYNYC351030001 according to template B."
        10. "Update the handover threshold for cell BOBOS01075F to -110 dBm."
        """

# Function to classify the query
async def classify_query(session_id: str, query: str) -> QueryClassificationModel:
    """
    Classify the query into one of three categories: RAN Documents QA, RAN Configuration, or RAN Configuration Update.
    """
    try:
        # 1) Fetch history
        history = await fetch_conversation_history(session_id)

        # 2) Build context string
        context_str = ""
        if history:
            context_lines = ["CONVERSATION HISTORY:"]
            for idx, entry in enumerate(history, start=1):
                context_lines.append(f"{idx}. User: {entry['user_query']} | Category: {entry['category'] or 'N/A'}")
            context_str = "\n".join(context_lines)

        # 3) Few-shot examples
        few_shot_examples = _load_few_shot_examples()

        # 4) Prompt template
        prompt_tmpl = """
        You are a specialized Radio Access Network (RAN) query classifier. Your task is to categorize each user query into EXACTLY ONE of these three categories by analyzing its intent, content, and structure:
        
        CATEGORY 1: RAN_DOCUMENTS_QA
        This category includes:
        - Questions about general RAN knowledge, capabilities, or specifications
        - Questions about software versions, releases, or fixed issues
        - Questions about feature limitations (e.g., "How many cells per DU are supported?")
        - Questions asking for explanations of how things work (e.g., "How does ANR Whitelist work?")
        - Questions about technical concepts, system behaviors, or protocols
        - Troubleshooting questions starting with phrases like "I am seeing..."
        - Questions about maximum supported values or theoretical limits
        - Questions about latency requirements or other network specifications
        - Questions about how to configure values or How to find any process for activation etc?
        
        CATEGORY 2: RAN_CONFIGURATION
        This category includes:
        - Queries about CURRENT settings, states, or parameters of SPECIFIC components
        - Questions about operational/administrative states of named equipment
        - Queries that aim to CHECK or RETRIEVE existing configuration values
        - Questions about compliance with standards (GPL) or misalignments
        - Requests to display, show, or list current status information
        - Questions about parameter values across different vendors or equipment
        - Requests for reports or summaries about current configurations
        - Temperature, signal strength, or alarm status for specific equipment
        - Questions about defined baselines or thresholds for parameters (e.g., "What is the defined baseline for qRxLevMin for all bands?")
        
        CATEGORY 3: RAN_CONFIGURATION_UPDATE
        This category includes:
        - Requests containing action verbs: change, update, set, modify, enable, disable
        - Requests to increase, decrease, or adjust specific parameter values
        - Instructions to apply new settings or alter configurations
        - Any query that explicitly requests a change to current network state
        - Commands that include both a target component and a desired new value/state
        - Requests starting with phrases like "Please change..." or "I want to update..."
        
        IMPORTANT CLASSIFICATION RULES:
        
        1. To distinguish between RAN_DOCUMENTS_QA and RAN_CONFIGURATION:
           - If the query references SPECIFIC EQUIPMENT (with IDs, names, or labels), it's likely RAN_CONFIGURATION
           - If the query asks about theoretical knowledge, capabilities, or how things work, it's RAN_DOCUMENTS_QA
           - "What is" can belong to either category depending on what follows:
             * "What is the maximum supported..." → RAN_DOCUMENTS_QA (theoretical limit)
             * "What is the current setting for..." → RAN_CONFIGURATION (specific actual value)
             * "What is the operational state of [specific component]" → RAN_CONFIGURATION
        
        2. Questions about misalignments, GPL compliance, or deviations belong to RAN_CONFIGURATION.
        
        3. If a query asks for a REPORT or SUMMARY of current states without changing anything, classify as RAN_CONFIGURATION.
        
        USER QUERY: {query}
        
        {context}

        {few_shot_examples}
        
        DISAMBIGUATION GUIDELINES:
        1. For comparative queries (e.g., "What is the value of X in vendor A and vendor B?"):
           - If comparing actual configured values → RAN_CONFIGURATION
           - If comparing theoretical capabilities → RAN_DOCUMENTS_QA
        
        2. For questions about specific parameters:
           - If asking for current value of a parameter for a specific component → RAN_CONFIGURATION
           - If asking about the general purpose, functioning, or capabilities → RAN_DOCUMENTS_QA
        
        3. For troubleshooting queries:
           - If asking about known issues or defects → RAN_DOCUMENTS_QA
           - If asking to check current states to diagnose → RAN_CONFIGURATION
           - If asking to make changes to fix an issue → RAN_CONFIGURATION_UPDATE
        
        4. For report generation:
           - If only requesting to display/summarize current data or misalignments → RAN_CONFIGURATION
           - If requesting to create a new configuration → RAN_CONFIGURATION_UPDATE
        
        5. For ambiguous "What is" queries:
           - Look for equipment identifiers (IDs, names) → RAN_CONFIGURATION
           - Look for theoretical concepts → RAN_DOCUMENTS_QA
        
        When still uncertain after applying these guidelines, default to RAN_DOCUMENTS_QA.
        """
        prompt = PromptTemplate(template=prompt_tmpl)

        # 5) Call the LLM
        response: QueryClassificationModel = llamaindex_llama_3.structured_predict(
            output_cls=QueryClassificationModel,
            prompt=prompt,
            query=query,
            context=context_str,
            few_shot_examples=few_shot_examples
        )
        category = response.category
        logger.info(f"Query classified: '{query}' → Category={category}")
        return response

    except Exception as e:
        logger.error(f"Query classification failed for session_id={session_id}: {e}")
        return QueryClassificationModel(
            category=QueryCategory.RAN_DOCUMENTS_QA
        )

# Main query processing function
async def process_user_query(session_id: str, query: str) -> Dict[str, Any]:
    """
    Main query processing function that handles query classification

    Args:
        session_id: The conversation session ID
        query: The user's query

    Returns:
        Dictionary with classification results
    """
    classification = await classify_query(session_id, query)
    logger.info(f"Query processed:\n {json.dumps(classification.model_dump(), indent=2)}")
    return classification.category  # or classification.model_dump() if you prefer a plain dict