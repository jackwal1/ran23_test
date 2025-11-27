from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import logging
import json
import re
from langchain_core.messages import AnyMessage
from sqlalchemy import text
from llms.llms import chatmodel_ran_automation
from enum import Enum
from langgraph.graph import MessagesState, StateGraph, END

from typing import TypedDict, Annotated, Optional, Dict, List, Any
import operator

# Setup logging configuration
from utils import constants as CONST

log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN_CLASSIFIER_AGENT")

# Import database connection utility
from utils.postgres_util.dbutil import get_session

# Define the categories for classification
class QueryCategory(str, Enum):
    RAN_DOCUMENTS_QA = "RAN_DOCUMENTS_QA"
    RAN_CONFIGURATION = "RAN_CONFIGURATION"
    RAN_CONFIGURATION_UPDATE = "RAN_CONFIGURATION_UPDATE"
    RAN_PERFORMANCE_METRICS = "RAN_PERFORMANCE_METRICS"

# Query classification model
class QueryClassificationModel(BaseModel):
    category: QueryCategory = Field(..., description="The category of the query")
    confidence: float = Field(default=0.8, description="Confidence score for the classification")
    reasoning: str = Field(default="", description="Brief reasoning for the classification")

class QueryClassificationModelWithFollwUpIndicator(BaseModel):
    category: QueryCategory = Field(..., description="The category of the query")
    confidence: float = Field(default=0.8, description="Confidence score for the classification")
    reasoning: str = Field(default="", description="Brief reasoning for the classification")
    is_followup: bool = Field(default=False, description="Is the question a follow-up")

# Agent state for classification
class ClassifierAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    query: str
    is_followup: bool
    conversation_history: List[Dict[str, str]]
    current_classification: Optional[QueryClassificationModel]
    analysis_steps: List[str]
    final_decision: bool
    retry_count: int


def extract_json_from_string(input_str: str) -> Optional[Union[dict, list]]:
    """
    Extract and normalize JSON from a string.

    This function handles multiple scenarios:
    1. Pure JSON strings (original functionality)
    2. JSON within markdown code blocks
    3. JSON mixed with other text
    4. Nested JSON structures
    5. JSON with common formatting issues

    Args:
        input_str: The string that may contain JSON

    Returns:
        The parsed JSON object (dict or list) or None if no valid JSON is found
    """
    if not input_str or not isinstance(input_str, str):
        return None

    input_str = input_str.strip()

    # Strategy 1: Try to parse the entire string as JSON directly (original functionality)
    try:
        return recursively_clean_json(json.loads(input_str))
    except json.JSONDecodeError:
        pass

    # Strategy 2: Try to find JSON using the original regex approach
    try:
        match = re.search(r'({.*}|\[.*\])', input_str, re.DOTALL)
        if match:
            try:
                return recursively_clean_json(json.loads(match.group(1)))
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logger.error(f"Failed to parse JSON with original regex: {e}")

    # Strategy 3: Look for JSON in markdown code blocks
    json_in_block = _extract_json_from_markdown(input_str)
    if json_in_block is not None:
        return json_in_block

    # Strategy 4: Look for JSON objects or arrays in the text with more precise patterns
    json_candidates = _find_json_candidates(input_str)

    # Try each candidate until we find a valid one
    for candidate in json_candidates:
        try:
            # Try to parse as-is first
            return recursively_clean_json(json.loads(candidate))
        except json.JSONDecodeError:
            # If that fails, try to clean and parse
            cleaned = _clean_json_string(candidate)
            if cleaned:
                try:
                    return recursively_clean_json(json.loads(cleaned))
                except json.JSONDecodeError:
                    continue

    # If all strategies fail, return None
    return None

def _extract_json_from_markdown(text: str) -> Optional[Union[dict, list]]:
    """Extract JSON from markdown code blocks."""
    # Pattern for ```json...``` or ```...``` blocks
    pattern = r'```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```'
    matches = re.findall(pattern, text, re.IGNORECASE)

    for match in matches:
        try:
            return recursively_clean_json(json.loads(match))
        except json.JSONDecodeError:
            continue

    return None

def _find_json_candidates(text: str) -> List[str]:
    """Find potential JSON strings in the text."""
    candidates = []

    # First, try the original simple pattern (for backward compatibility)
    simple_match = re.search(r'({.*}|\[.*\])', text, re.DOTALL)
    if simple_match:
        candidates.append(simple_match.group(1))

    # Then try more precise patterns for nested structures
    # Pattern for JSON objects with balanced braces
    object_pattern = r'(\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\})'
    # Pattern for JSON arrays with balanced brackets
    array_pattern = r'(\[(?:[^\[\]]|(?:\[(?:[^\[\]]|(?:\[[^\[\]]*\]))*\]))*\])'

    # Find all object candidates
    for match in re.finditer(object_pattern, text):
        candidates.append(match.group(1))

    # Find all array candidates
    for match in re.finditer(array_pattern, text):
        candidates.append(match.group(1))

    # Remove duplicates and sort by length (descending) to try the most substantial ones first
    candidates = list(dict.fromkeys(candidates))  # Preserve order while removing duplicates
    candidates.sort(key=len, reverse=True)

    return candidates

def _clean_json_string(json_str: str) -> Optional[str]:
    """Clean a JSON string to handle common issues."""
    if not json_str:
        return None

    # Remove trailing commas before closing brackets or braces
    cleaned = re.sub(r',(\s*[}\]])', r'\1', json_str)

    # Remove JavaScript-style comments (// and /* */)
    # Single-line comments
    cleaned = re.sub(r'\/\/.*?(\n|$)', '', cleaned)
    # Multi-line comments
    cleaned = re.sub(r'\/\*.*?\*\/', '', cleaned, flags=re.DOTALL)

    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()

    # Ensure the string starts with { or [ and ends with } or ]
    if (cleaned.startswith('{') and cleaned.endswith('}')) or \
            (cleaned.startswith('[') and cleaned.endswith(']')):
        return cleaned

    return None

def recursively_clean_json(data: Any) -> Any:
    """
    Recursively processes a JSON object or list,
    decoding nested JSON strings and normalizing primitives.
    (Original functionality preserved)
    """
    if isinstance(data, dict):
        return {k: recursively_clean_json(_try_parse_json(v)) for k, v in data.items()}
    elif isinstance(data, list):
        return [recursively_clean_json(_try_parse_json(item)) for item in data]
    return _normalize_primitive(data)

def _try_parse_json(value: Any) -> Any:
    """
    Tries to parse a value as JSON if it's a string.
    (Original functionality preserved)
    """
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed
        except (json.JSONDecodeError, TypeError):
            return _normalize_primitive(value)
    return value

def _normalize_primitive(value: Any) -> Any:
    """
    Converts strings like "true", "false", "null" to native Python types.
    Keeps numeric strings as-is.
    (Original functionality preserved)
    """
    if isinstance(value, str):
        val = value.strip().lower()
        if val == "true":
            return True
        elif val == "false":
            return False
        elif val == "null":
            return None
    return value

# Function to load few-shot examples
def _load_few_shot_examples() -> str:
    return """
    EXAMPLES OF *RAN_DOCUMENTS_QA* QUERIES:
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

    EXAMPLES OF *RAN_CONFIGURATION* QUERIES:
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
    18. "What is the range for the parameter preambleTransMax?"
    19. "What is the DISH GPL value for the parameter preambleTransMax?"
    20. "What is the recommended gpl dish value of parameter 'totalNumOfRachPreamble'?"
    21. "What is hierarchy for the parameter name 'zeroCorrelationZoneCfg'?"
    22. "What is the range for the parameter 'preambleTransMax'?"
    23. "Explain the hierarchy for the parameter name 'zeroCorrelationZoneCfg'?"
    24. "Can you show the trend for misalignment observed in west region"
    25. "National GPL Inconsistency Dashboard from PI Works can you give me region wise inconsistency percentage?" # Missallignment percentage related queries
    26. "For the Mavenir GPL Audit, what should the baseline value be for MO Type: XYZ" # Audit related queries
    25. "Please list all relevant Mavenir MO Types for Parameter: prachCfgIndex" # MO related queries
    26. "Can you show the trend for misalignment observed in west region"
    27. "Which CUCP has the most GPL inconsistencies for Mavenir AOI, "DAL"?"

    EXAMPLES OF *RAN_CONFIGURATION_UPDATE* QUERIES:
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
    
    EXAMPLES OF *RAN_PERFORMANCE_METRICS* QUERIES:
    1. "What is the trend of call drops in Denver Airport?"
    2. "What is the total traffic per Band in my AOI?"
    3. "Do you see a correlation between KPI X degradation last week with KPI Y?"
    4. "What are top offending cells in AOI XXX?"
    5. "Show daily site level KPI_1 for XXXX000001 in last month on a new chart widget"
    6. "Show daily site level KPI_1 for all sites in AOI_1 on a new chart widget"
    7. "Show daily site level KPI_1 and KPI_2 for all sites in AOI_1 on a new chart widget"
    8. "Show object aggregated site level KPI_1 and KPI_2 for all sites in AOI_1 on a new chart widget"
    9. "Show time aggregated site level KPI_1 and KPI_2 for all sites in AOI_1 on a new chart widget"
    10. "Show time and object aggregated site level KPI_1 and KPI_2 for all sites in AOI_1 on a new chart widget"
    11. "Show object aggregated site level KPI_1 and KPI_2 for all sites in AOI_1 on a new table widget sorted ascending"
    12. "What is the aggregated value of KPI_1 for site_1 in last month?"
    13. "At what timestamp did the highest value of KPI_1 occur?"
    14. "Show the 10 top contributor cell with KPI_1 in cluster_1 on widget _1"
    15. "Add/Remove a new widget/tab"
    16. "Resize widget_1 to (x,y)"
    17. "Which Mavenir AOI has the highest KPI_1 increase in the last week?"
    18. "How many sites have KPI_1 more than value_1 in last week?"
    19. "Which site has the lowest KPI_1 in cluster_1 and KPI_2 is more than value_1?"
    20. "List the sites where KPI_1 values are at least 30% of its maximum value."
    21. "What is the average of the KPI_1 for the sites which has 10 lowest KPI_2?"
    22. "How has KPI_1 changed over the last week?"
    23. "Compare KPI_2 values between January and February"
    24. "Is there an upward or downward trend in KPI_1 values this week?"
    25. "Do KPI_1 values show a daily or weekly pattern?"
    26. "What are the peak hours for high KPI_1 values?"
    27. "Identify any unusual spikes in KPI_1 values."
    28. "Are there any negative values in KPI_1?"
    29. "Is there a correlation between KPI_1 and KPI_2?"
    30. "Do higher values of KPI_1 result in lower values of KPI_2?"
    31. "Can you predict KPI_1 values for next week?"
    32. "What is the 90th percentile value of KPI_1?"
    33. "Does KPI_3 show a weekend spike?"
    34. "Compare the average value of KPI_4 between weekdays and weekends."
    35. "In the last dip in KPI_1 in AOI_1 which counter has the highest contribution?"
    36. "Which site has the highest KPI_1 to KPI_2 ratio in the last week?"
    37. "There was a change at time_1 on site_a, how it impacted KPI_1?"
    38. "What happens to KPI_1 if site traffic increases by 20%?"
    39. "What are the top 3 causes for a drop in KPI_1?"
    40. "Identify the root cause of the spike in KPI_1."
    41. "Drill down on AOI_1 KPI_1 to sites with KPI_1 above 50."
    42. "Show KPI_1 in AOI_1 on the map"
    43. "Zoom the map on site xxx0001"
    44. "Zoom on the highest contributor site of the KPI_1 in AOI_1 on the map"
    45. "What KPI is on the map?"
    46. "What is highest value of the KPI on the map?"
    47. "Zoom all on the map"
    48. "Zoom to DEN Airport on the map"
    49. "Show NCA event type _1 on the map"
    50. "Zoom/show the site which has the highest event type_1 in AOI_1 last week"
    """

class QueryClassifierAgent:
    def __init__(self, llm_model):
        self.llm_model = llm_model
        self.system_prompt = self._build_system_prompt()
        self.few_shot_examples = _load_few_shot_examples()

        # Build the agent graph
        graph = StateGraph(ClassifierAgentState)

        # Add nodes
        graph.add_node("analyze_context", self.analyze_context)
        graph.add_node("reason_classification", self.reason_classification)
        graph.add_node("validate_decision", self.validate_decision)
        graph.add_node("finalize_classification", self.finalize_classification)

        # Add edges
        graph.add_conditional_edges(
            "analyze_context",
            self.should_proceed_to_reasoning,
            {
                "validate": "validate_decision",
                "reason": "reason_classification"
            }
        )
        graph.add_conditional_edges(
            "reason_classification",
            self.should_validate,
            {
                "validate": "validate_decision",
                "finalize": "finalize_classification"
            }
        )
        graph.add_conditional_edges(
            "validate_decision",
            self.validation_result,
            {
                "reanalyze": "reason_classification",
                "finalize": "finalize_classification"
            }
        )
        graph.add_edge("finalize_classification", END)

        # Set entry point
        graph.set_entry_point("analyze_context")

        self.graph = graph.compile()

    def _build_system_prompt(self) -> str:
        return """
        You are a specialized Radio Access Network (RAN) query classifier. Your task is to categorize each user query into EXACTLY ONE of these four categories by analyzing its intent, content, structure, and conversation history, including previous queries and their responses:

        **CATEGORY 1: RAN_DOCUMENTS_QA**
        - Includes queries seeking general knowledge, capabilities, or specifications about RAN.
        - Covers questions about software versions, feature limitations, explanations of how features or protocols work, technical concepts, system behaviors, and troubleshooting.
        - Key indicators: "how does [feature] work?", "what is the maximum supported [value]?", "is there a known defect?", "explain [concept]."

        **CATEGORY 2: RAN_CONFIGURATION**
        - Includes queries about current settings, states, or parameters of specific RAN components. Also it will handles Queries related to misalignment / GPL audit / National PI works Audit.
        - Covers operational/administrative states, compliance with standards (e.g., GPL), current configuration values, and defined baselines.
        - Key indicators: "what is the current [setting]?", "show me the [parameter] for [component]", "what is the baseline for [parameter]?", "minimum."

        **CATEGORY 3: RAN_CONFIGURATION_UPDATE**
        - Includes queries requesting changes to the current configuration.
        - Covers requests to change, update, set, modify, enable, or disable specific parameters or settings.
        - Key indicators: Action verbs like "change", "update", "set", "modify", "enable", "disable", or phrases like "I want to [action]."

        **CATEGORY 4: RAN_PERFORMANCE_METRICS**
        - Includes queries related to performance metrics, KPIs, and trend analysis.
        - Covers performance trends, data visualization, statistical analysis, comparative analysis, correlation analysis, predictive analysis, and impact analysis.
        - Key indicators: Keywords like "KPI", "trend", "performance", "chart", "widget", "map", "correlation", "average", "predict."

        Your classification process should:
        1. Analyze conversation history, including previous queries and responses, to understand context and user intent.
        2. Use provided examples to guide classification.
        3. Validate decisions against disambiguation guidelines.
        4. Output the response as a JSON object with "category" (one of the four categories), "confidence" (0.0 to 1.0), and "reasoning" (brief explanation).
        """

    async def _invoke_llm(self, messages: List[AnyMessage]) -> str:
        """Helper method to invoke the LLM model using LangChain"""
        try:
            response = await self.llm_model.ainvoke(messages)
            if isinstance(response, AIMessage):
                return response.content
            elif isinstance(response, str):
                return response
            else:
                return str(response)
        except Exception as e:
            logger.error(f"Error invoking LLM: {e}")
            return "Error occurred during LLM invocation"

    async def analyze_context(self, state: ClassifierAgentState) -> Dict:
        """Analyze the conversation context and user query patterns"""
        query = state["query"]
        history = state["conversation_history"]

        context_analysis_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self.system_prompt),
            HumanMessagePromptTemplate.from_template("""
            Analyze the following user query and conversation history (including previous queries and responses) to understand the context:

            **CONVERSATION HISTORY:**
            {history}

            **USER QUERY:** {query}

            **FEW-SHOT EXAMPLES:**
            {few_shot_examples}

            **DISAMBIGUATION GUIDELINES:**
            1. **RAN_PERFORMANCE_METRICS vs RAN_CONFIGURATION**:
               - If the query asks about performance data, trends, or KPIs → RAN_PERFORMANCE_METRICS
               - If the query asks about configuration settings or parameters → RAN_CONFIGURATION
               - If the query asks about GPL misalignment / GPL Audit  → RAN_CONFIGURATION
               - Example: "What is the call drop rate?" → RAN_PERFORMANCE_METRICS
               - Example: "What is the power setting?" → RAN_CONFIGURATION
            2. **RAN_PERFORMANCE_METRICS vs RAN_DOCUMENTS_QA**:
               - If the query asks about actual performance data or metrics → RAN_PERFORMANCE_METRICS
               - If the query asks about theoretical knowledge or general concepts → RAN_DOCUMENTS_QA
               - Example: "What is the throughput trend for site X?" → RAN_PERFORMANCE_METRICS
               - Example: "What is the maximum theoretical throughput?" → RAN_DOCUMENTS_QA
            3. **RAN_CONFIGURATION vs RAN_DOCUMENTS_QA**:
               - If the query asks for specific parameter values or states → RAN_CONFIGURATION
               - If the query asks for explanations or general knowledge → RAN_DOCUMENTS_QA
               - Example: "What is the value of timer t311?" → RAN_CONFIGURATION
               - Example: "How does timer t311 work?" → RAN_DOCUMENTS_QA
            4. **RAN_CONFIGURATION_UPDATE vs RAN_CONFIGURATION**:
               - If the query requests a change or modification → RAN_CONFIGURATION_UPDATE
               - If the query only asks about current settings → RAN_CONFIGURATION
               - Example: "Set timer t311 to 10 seconds" → RAN_CONFIGURATION_UPDATE
               - Example: "What is the current value of timer t311?" → RAN_CONFIGURATION
            5. **Ambiguous Queries**:
               - Use conversation history, including previous responses, to resolve ambiguity. For example, if the previous query was about updating a configuration and the response mentioned a parameter, a follow-up like "what about minimum" likely refers to a configuration parameter → RAN_CONFIGURATION

            Provide a detailed analysis of the query in the context of the history and classify it into one of: RAN_DOCUMENTS_QA, RAN_CONFIGURATION, RAN_CONFIGURATION_UPDATE, RAN_PERFORMANCE_METRICS. Return the classification as a JSON object with the following keys:
            - "category": The most appropriate category
            - "confidence": Confidence level (0.0 to 1.0)
            - "reasoning": Brief explanation for the classification

            Return only the JSON object, enclosed in ```json``` tags.
            ```json
            {{
                "category": "[category_name]",
                "confidence": [confidence_score],
                "reasoning": "[brief_explanation]"
            }}
            ```
            """)
        ])

        try:
            context_analysis = await self._invoke_llm(context_analysis_prompt.format_messages(
                query=query,
                history=self._format_history(history),
                few_shot_examples=self.few_shot_examples
            ))
            logger.info(f"Context Analysis: {context_analysis}")

            # Extract classification from context analysis
            classification_result = self._extract_classification_from_response(context_analysis, query)
            follow_up = False
            if any(variant in classification_result.reasoning.lower() for variant in CONST.followup_variants):
                logger.info("It is identified as a follow up query")
                follow_up = True
            return {
                "messages": [
                    SystemMessage(content="Context analysis completed"),
                    AIMessage(content=context_analysis)
                ],
                "analysis_steps": [f"Context Analysis: {context_analysis}"],
                "current_classification": classification_result,
                "retry_count": state.get("retry_count", 0),
                "is_followup": follow_up
            }

        except Exception as e:
            logger.error(f"Error in context analysis: {e}")
            fallback_analysis = "Context analysis failed - proceeding with query-only analysis"
            classification_result = self._fallback_classification(query)
            return {
                "messages": [AIMessage(content=fallback_analysis)],
                "analysis_steps": [f"Context Analysis: {fallback_analysis}"],
                "current_classification": classification_result,
                "retry_count": state.get("retry_count", 0)
            }

    async def reason_classification(self, state: ClassifierAgentState) -> Dict:
        """Reason through the classification decision using domain knowledge and few-shot examples"""
        query = state["query"]
        analysis_steps = state.get("analysis_steps", [])

        reasoning_prompt = ChatPromptTemplate.from_messages([
            HumanMessagePromptTemplate.from_template("""
            Based on the previous analysis and provided examples, classify the query into one of: RAN_DOCUMENTS_QA, RAN_CONFIGURATION, RAN_CONFIGURATION_UPDATE, RAN_PERFORMANCE_METRICS.

            **USER QUERY:** {query}

            **PREVIOUS ANALYSIS:**
            {analysis_steps}

            **FEW-SHOT EXAMPLES:**
            {few_shot_examples}

            **DISAMBIGUATION GUIDELINES:**
            1. **RAN_PERFORMANCE_METRICS vs RAN_CONFIGURATION**:
               - If the query asks about performance data, trends, or KPIs → RAN_PERFORMANCE_METRICS
               - If the query asks about configuration settings or parameters → RAN_CONFIGURATION
               - If the query asks about GPL misalignment / GPL Audit for Samsung or Mavenir  → RAN_CONFIGURATION
               - Example: "What is the call drop rate?" → RAN_PERFORMANCE_METRICS
               - Example: "What is the power setting?" → RAN_CONFIGURATION
            2. **RAN_PERFORMANCE_METRICS vs RAN_DOCUMENTS_QA**:
               - If the query asks about actual performance data or metrics → RAN_PERFORMANCE_METRICS
               - If the query asks about theoretical knowledge or general concepts → RAN_DOCUMENTS_QA
               - Example: "What is the throughput trend for site X?" → RAN_PERFORMANCE_METRICS
               - Example: "What is the maximum theoretical throughput?" → RAN_DOCUMENTS_QA
            3. **RAN_CONFIGURATION vs RAN_DOCUMENTS_QA**:
               - If the query asks for specific parameter values or states → RAN_CONFIGURATION
               - If the query asks for explanations or general knowledge → RAN_DOCUMENTS_QA
               - Example: "What is the value of timer t311?" → RAN_CONFIGURATION
               - Example: "How does timer t311 work?" → RAN_DOCUMENTS_QA
            4. **RAN_CONFIGURATION_UPDATE vs RAN_CONFIGURATION**:
               - If the query requests a change or modification → RAN_CONFIGURATION_UPDATE
               - If the query only asks about current settings → RAN_CONFIGURATION
               - Example: "Set timer t311 to 10 seconds" → RAN_CONFIGURATION_UPDATE
               - Example: "What is the current value of timer t311?" → RAN_CONFIGURATION
            5. **Ambiguous Queries**:
               - Use conversation history, including previous responses, to resolve ambiguity. For example, if the previous query was about updating a configuration and the response mentioned a parameter, a follow-up like "what about minimum" likely refers to a configuration parameter → RAN_CONFIGURATION
               - Be very careful while analyzing based on Previous conversation , it can be a follow up or it can also be a question related to another category.
               - In reasoning always provide the analysis why do you think it is a follow-up query.
               
            Provide the classification as a JSON object with the following keys:
            - "category": The most appropriate category
            - "confidence": Confidence level (0.0 to 1.0)
            - "reasoning": Brief explanation for the classification

            Return only the JSON object, enclosed in ```json``` tags.
            ```json
            {{
                "category": "[category_name]",
                "confidence": [confidence_score],
                "reasoning": "[brief_explanation]"
            }}
            ```
            """)
        ])

        try:
            reasoning_content = await self._invoke_llm(reasoning_prompt.format_messages(
                query=query,
                analysis_steps="\n".join(analysis_steps),
                few_shot_examples=self.few_shot_examples
            ))
            logger.info(f"Classification Reasoning: {reasoning_content}")

            # Extract classification from the response
            classification_result = self._extract_classification_from_response(reasoning_content, query)

            current_steps = state.get("analysis_steps", [])

            return {
                "messages": [AIMessage(content=f"Classification reasoning: {reasoning_content}")],
                "analysis_steps": current_steps + [f"Classification Reasoning: {reasoning_content}"],
                "current_classification": classification_result,
                "retry_count": state.get("retry_count", 0)
            }

        except Exception as e:
            logger.error(f"Error in classification reasoning: {e}")
            fallback_classification = self._fallback_classification(query)
            current_steps = state.get("analysis_steps", [])
            return {
                "messages": [AIMessage(content="Classification reasoning failed")],
                "analysis_steps": current_steps + ["Classification reasoning failed"],
                "current_classification": fallback_classification,
                "retry_count": state.get("retry_count", 0)
            }

    def _extract_classification_from_response(self, response: str, query: str) -> QueryClassificationModel:
        """Extract classification from LLM response using provided JSON parsing utilities."""
        # Define valid categories
        category_mapping = {
            'RAN_DOCUMENTS_QA': QueryCategory.RAN_DOCUMENTS_QA,
            'RAN_CONFIGURATION': QueryCategory.RAN_CONFIGURATION,
            'RAN_CONFIGURATION_UPDATE': QueryCategory.RAN_CONFIGURATION_UPDATE,
            'RAN_PERFORMANCE_METRICS': QueryCategory.RAN_PERFORMANCE_METRICS
        }

        # Parse response using provided JSON parsing function
        parsed_response = extract_json_from_string(response)

        if parsed_response and isinstance(parsed_response, dict):
            category_str = parsed_response.get("category")
            confidence = parsed_response.get("confidence", 0.8)
            reasoning = parsed_response.get("reasoning", "Parsed from response")

            # Ensure confidence is a float
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.8

            # Map category string to QueryCategory enum
            category = category_mapping.get(category_str.upper() if isinstance(category_str, str) else None)
            if category:
                return QueryClassificationModel(
                    category=category,
                    confidence=min(max(confidence, 0.0), 1.0),
                    reasoning=str(reasoning)
                )

        # Fallback if parsing fails or category is invalid
        logger.warning(f"Failed to extract valid classification from response: {response}")
        return self._fallback_classification(query)

    def _fallback_classification(self, query: str) -> QueryClassificationModel:
        """Fallback classification using simple heuristics"""
        query_lower = query.lower()

        # Keyword-based classification
        if any(word in query_lower for word in ['change', 'update', 'set', 'modify', 'enable', 'disable', 'increase', 'decrease']):
            category = QueryCategory.RAN_CONFIGURATION_UPDATE
            reasoning = "Contains action/modification keywords"
        elif any(word in query_lower for word in ['kpi', 'performance', 'metric', 'trend', 'report', 'success rate', 'utilization', 'chart', 'widget', 'map', 'correlation', 'average', 'predict']):
            category = QueryCategory.RAN_PERFORMANCE_METRICS
            reasoning = "Contains performance/metrics keywords"
        elif any(word in query_lower for word in ['what is', 'show me', 'display', 'operational state', 'current', 'status', 'minimum', 'baseline', 'range']):
            category = QueryCategory.RAN_CONFIGURATION
            reasoning = "Contains status/configuration inquiry keywords"
        else:
            category = QueryCategory.RAN_DOCUMENTS_QA
            reasoning = "General knowledge/documentation query"

        return QueryClassificationModel(
            category=category,
            confidence=0.6,
            reasoning=f"Fallback classification: {reasoning}"
        )

    def should_proceed_to_reasoning(self, state: ClassifierAgentState) -> str:
        """Decide whether to proceed to reasoning or validate based on analyze_context confidence"""
        classification = state.get("current_classification")
        retry_count = state.get("retry_count", 0)
        max_retries = 2

        if retry_count >= max_retries:
            logger.info(f"Max retries ({max_retries}) reached, proceeding to validate")
            return "validate"

        if classification and classification.confidence > 0.7:
            logger.info(f"High confidence ({classification.confidence}) from analyze_context, proceeding to validate")
            return "validate"

        logger.info("Low confidence from analyze_context, proceeding to reason_classification")
        return "reason"

    def should_validate(self, state: ClassifierAgentState) -> str:
        """Decide if validation is needed based on retry count and confidence"""
        retry_count = state.get("retry_count", 0)
        max_retries = 2
        classification = state.get("current_classification")

        if retry_count >= max_retries:
            logger.info(f"Max retries ({max_retries}) reached, proceeding to finalize")
            return "finalize"

        if classification and classification.confidence > 0.9:
            logger.info("High confidence classification, skipping validation")
            return "finalize"

        return "validate"

    async def validate_decision(self, state: ClassifierAgentState) -> Dict:
        """Validate the classification decision"""
        classification = state["current_classification"]
        query = state["query"]
        history = state["conversation_history"]
        retry_count = state.get("retry_count", 0)

        validation_prompt = ChatPromptTemplate.from_messages([
            HumanMessagePromptTemplate.from_template("""
            Validate the following classification decision:

            **CONVERSATION HISTORY (QUERIES AND RESPONSES):**
            {history}

            **CURRENT QUERY:** {query}
            **CLASSIFICATION:** {category}
            **CONFIDENCE:** {confidence}
            **REASONING:** {reasoning}

            **FEW-SHOT EXAMPLES:**
            {few_shot_examples}

            **DISAMBIGUATION GUIDELINES:**
            1. **RAN_PERFORMANCE_METRICS vs RAN_CONFIGURATION**:
               - If the query asks about performance data, trends, or KPIs → RAN_PERFORMANCE_METRICS
               - If the query asks about configuration settings or parameters → RAN_CONFIGURATION
               - Example: "What is the call drop rate?" → RAN_PERFORMANCE_METRICS
               - Example: "What is the power setting?" → RAN_CONFIGURATION
            2. **RAN_PERFORMANCE_METRICS vs RAN_DOCUMENTS_QA**:
               - If the query asks about actual performance data or metrics → RAN_PERFORMANCE_METRICS
               - If the query asks about theoretical knowledge or general concepts → RAN_DOCUMENTS_QA
               - Example: "What is the throughput trend for site X?" → RAN_PERFORMANCE_METRICS
               - Example: "What is the maximum theoretical throughput?" → RAN_DOCUMENTS_QA
            3. **RAN_CONFIGURATION vs RAN_DOCUMENTS_QA**:
               - If the query asks for specific parameter values or states → RAN_CONFIGURATION
               - If the query asks for explanations or general knowledge → RAN_DOCUMENTS_QA
               - Example: "What is the value of timer t311?" → RAN_CONFIGURATION
               - Example: "How does timer t311 work?" → RAN_DOCUMENTS_QA
            4. **RAN_CONFIGURATION_UPDATE vs RAN_CONFIGURATION**:
               - If the query requests a change or modification → RAN_CONFIGURATION_UPDATE
               - If the query only asks about current settings → RAN_CONFIGURATION
               - Example: "Set timer t311 to 10 seconds" → RAN_CONFIGURATION_UPDATE
               - Example: "What is the current value of timer t311?" → RAN_CONFIGURATION
            5. **Ambiguous Queries**:
               - Use conversation history, including previous responses, to resolve ambiguity. For example, if the previous query was about updating a configuration and the response mentioned a parameter, a follow-up like "what about minimum" likely refers to a configuration parameter → RAN_CONFIGURATION

            Questions to consider:
            1. Is the classification consistent with the query's intent and conversation context, including previous responses?
            2. Are there any contradictions or missed indicators from the history or responses?
            3. Would a domain expert agree with this classification given the context?
            4. Does the confidence level match the clarity of the query and history?

            Provide the validation feedback as a JSON object with the following keys:
            - "decision": "APPROVE" or "REANALYZE"
            - "reasoning": Brief explanation for the decision

            Return only the JSON object, enclosed in ```json``` tags.
            ```json
            {{
                "decision": "[APPROVE or REANALYZE]",
                "reasoning": "[brief_explanation]"
            }}
            ```
            """)
        ])

        try:
            validation_content = await self._invoke_llm(validation_prompt.format_messages(
                history=self._format_history(history),
                query=query,
                category=classification.category,
                confidence=classification.confidence,
                reasoning=classification.reasoning,
                few_shot_examples=self.few_shot_examples
            ))
            logger.info(f"Validation: {validation_content}")

            # Parse validation response
            parsed_validation = extract_json_from_string(validation_content)
            current_steps = state.get("analysis_steps", [])
            validation_result = "APPROVE"

            if parsed_validation and isinstance(parsed_validation, dict):
                validation_result = parsed_validation.get("decision", "APPROVE").upper()
                validation_reasoning = parsed_validation.get("reasoning", "Parsed from validation response")
                current_steps.append(f"Validation: {validation_result} - {validation_reasoning}")
            else:
                current_steps.append(f"Validation: Failed to parse response, defaulting to APPROVE")

            return {
                "messages": [AIMessage(content=f"Validation: {validation_content}")],
                "analysis_steps": current_steps,
                "validation_result": validation_result,
                "retry_count": retry_count + 1
            }

        except Exception as e:
            logger.error(f"Error in validation: {e}")
            return {
                "messages": [AIMessage(content="Validation failed - proceeding with current classification")],
                "validation_result": "APPROVE",
                "retry_count": retry_count + 1
            }

    def validation_result(self, state: ClassifierAgentState) -> str:
        """Route based on validation result"""
        result = state.get("validation_result", "APPROVE").lower()
        return "reanalyze" if result == "reanalyze" else "finalize"

    async def finalize_classification(self, state: ClassifierAgentState) -> Dict:
        """Finalize the classification decision"""
        classification = state["current_classification"]

        logger.info(f"Final Classification: {classification.category} (Confidence: {classification.confidence})")

        return {
            "messages": [AIMessage(content=f"Classification finalized: {classification.category}")],
            "final_decision": True,
            "retry_count": state.get("retry_count", 0)
        }

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Format conversation history for prompts, including queries and truncated responses"""
        if not history:
            return "No previous conversation history."

        formatted = []
        for i, entry in enumerate(history, 1):
            query = entry.get('user_query', 'N/A')
            category = entry.get('category', 'N/A')
            response = entry.get('response', 'No response available')
            formatted.append(f"{i}. User Query: {query}\n   Category: {category}\n   Response: {response}")
        return "\n".join(formatted)

    async def classify_query_with_agent(self, session_id: str, query: str) -> QueryClassificationModelWithFollwUpIndicator:
        """Main method to classify query using the agent"""
        try:
            # Fetch conversation history
            history = await fetch_conversation_history(session_id)

            # Initialize agent state
            initial_state = ClassifierAgentState(
                messages=[],
                query=query,
                conversation_history=history,
                current_classification=None,
                analysis_steps=[],
                final_decision=False,
                retry_count=0,
                is_followup = False
            )

            # Run the agent
            final_state = await self.graph.ainvoke(initial_state)


            classification = final_state["current_classification"]
            return QueryClassificationModelWithFollwUpIndicator(
                category=classification.category,
                confidence=classification.confidence,
                reasoning=classification.reasoning,
                is_followup=final_state["is_followup"]  # Keep as boolean
            )

        except Exception as e:
            logger.error(f"Agent classification failed: {e}")
            fallback = self._fallback_classification(query)
            return QueryClassificationModelWithFollwUpIndicator(
                category=fallback.category,
                confidence=fallback.confidence,
                reasoning=fallback.reasoning,
                is_followup=False  # Fallback to False (boolean)
            )


def format_conversation_for_llm(conversation_history: List[Dict[str, str]]) -> str:
    """
    Convert conversation history JSON to a clear format for LLM context understanding.

    Args:
        conversation_history: List of dictionaries with user_query, category, and response

    Returns:
        Formatted string that provides clear context for LLM
    """
    if not conversation_history:
        return "No previous conversation history available."

    context_parts = [
        "=== CONVERSATION HISTORY ===",
        f"Previous interactions: {len(conversation_history)} messages",
        ""
    ]

    for i, interaction in enumerate(conversation_history, 1):
        user_query = interaction.get('user_query', 'No query recorded')
        category = interaction.get('category', 'Unknown')
        response = interaction.get('response', 'No response available')

        context_parts.extend([
            f"--- Interaction {i} ---",
            f"User Query: {user_query}",
            f"Category: {category}",
            f"Previous Response: {response}",
            ""
        ])

    context_parts.extend([
        "=== END CONVERSATION HISTORY ===",
        "",
        "Instructions for LLM:",
        "- Use this conversation history to understand the user's previous questions and context",
        "- If the user asks follow-up questions, consider the previous responses",
    ])
    return "\n".join(context_parts)


def format_conversation_for_llm_concise(conversation_history: List[Dict[str, str]]) -> str:
    """
    Convert conversation history to a more concise format for LLM context.
    Better for token efficiency while maintaining clarity.
    """
    if not conversation_history:
        return "No previous conversation history."

    context_parts = ["CONVERSATION CONTEXT:"]

    for i, interaction in enumerate(conversation_history, 1):
        user_query = interaction.get('user_query', 'No query')
        category = interaction.get('category', 'Unknown')
        response = interaction.get('response', 'No response')

        context_parts.append(
            f"{i}. [{category}] User: {user_query} | Response: {response}"
        )

    context_parts.append("\nUse this context to maintain conversation continuity.")
    return "\n".join(context_parts)


def format_conversation_for_llm_structured(conversation_history: List[Dict[str, str]]) -> str:
    """
    Convert conversation history to a structured format with clear sections.
    Good for complex conversations with multiple topics.
    """
    if not conversation_history:
        return "No conversation history available."

    # Group by category for better organization
    categorized_history = {}
    for interaction in conversation_history:
        category = interaction.get('category', 'General')
        if category not in categorized_history:
            categorized_history[category] = []
        categorized_history[category].append(interaction)

    context_parts = [
        "CONVERSATION HISTORY SUMMARY:",
        f"Total interactions: {len(conversation_history)}",
        ""
    ]

    # Add recent interactions chronologically
    context_parts.append("RECENT INTERACTIONS (chronological):")
    for i, interaction in enumerate(conversation_history, 1):
        user_query = interaction.get('user_query', 'No query')
        category = interaction.get('category', 'Unknown')
        response = interaction.get('response', 'No response')

        context_parts.extend([
            f"Turn {i}: [{category}]",
            f"  User: {user_query}",
            f"  Assistant: {response}",
            ""
        ])

    # Add category summary
    if len(categorized_history) > 1:
        context_parts.append("TOPICS DISCUSSED:")
        for category, interactions in categorized_history.items():
            context_parts.append(f"- {category}: {len(interactions)} interactions")
        context_parts.append("")

    context_parts.append("Continue this conversation maintaining context and continuity.")
    return "\n".join(context_parts)

# Function to fetch recent conversation history with responses
async def fetch_conversation_history(session_id: str, limit: int = 5) -> str:
    """
    Fetch the last `limit` user queries, their categories, and responses from conversation history.
    Truncate responses to 100 words.
    """
    try:
        if not session_id or session_id == 'null':
            logger.warning("Empty or null session_id provided.")
            return "No previous conversation history available."

        async with get_session() as db_session:
            query = text("""
                SELECT 
                    user_query, 
                    response_type AS category,
                    watsonx_response AS response
                FROM 
                    conversation_logs.messages
                WHERE 
                    conversation_id = :session_id
                ORDER BY 
                    created_timestamp DESC
                LIMIT :limit
            """)
            result = await db_session.execute(query, {"session_id": session_id, "limit": limit})
            rows = result.fetchall()

            if not rows:
                logger.warning(f"No messages found for session_id={session_id}")
                return "No previous conversation history available."

            # Function to truncate response to 100 words
            def truncate_response(text: str, max_words: int = 150) -> str:
                if not text:
                    return "No response available"
                words = text.split()
                if len(words) <= max_words:
                    return text
                return ' '.join(words[:max_words]) + '...'

            rows.reverse()
            final_resp = [
                {
                    "user_query": row.user_query,
                    "category": CONST.CATEGORY_MAPPING.get(row.category, row.category),
                    "response": truncate_response(row.response)
                }
                for row in rows
            ]

            final_resp = format_conversation_for_llm(final_resp)

            logger.info(f"Session history: \n{final_resp}")
            return final_resp
    except Exception as e:
        logger.error(f"Error fetching conversation history for session_id={session_id}: {e}")
        return "No previous conversation history available."



# Initialize the classifier agent
classifier_agent = QueryClassifierAgent(chatmodel_ran_automation)

# Main query processing function
async def process_user_query(session_id: str, query: str) -> Dict:
    """
    Main query processing function that handles query classification using the agent.
    """
    classification = await classifier_agent.classify_query_with_agent(session_id, query)
    logger.info(f"Query processed by agent: Category={classification.category}, Confidence={classification.confidence}")
    return {
        "is_follw_up": classification.is_followup,
        "category" : classification.category
    }