import os
import traceback

from langchain_core.tools import tool
from typing import Annotated, Dict, List, Optional
from utils import constants as CONST
import re
from utils.log_init import logger
from prompts.ran_sql_prompts_v2 import (
    mcms_cm_ret_state_12hr_prompt,
    mcms_cm_topology_state_du_12hr_prompt,
    mcms_cm_topology_state_cuup_12hr_prompt,
    mcms_cm_topology_state_cucp_12hr_prompt,
    mcms_cm_topology_state_rru_12hr_prompt,
    table_name_gpl_1_prompt_mistral, table_name_gpl_2_prompt_mistral, table_name_gpl_3_prompt_mistral,
    table_name_gpl_4_prompt_mistral, table_name_gpl_5_prompt_mistral, table_name_gpl_6_prompt_mistral,
    usm_cm_config_cucp_1d_prompt, usm_cm_config_du_1d_prompt, usm_cm_ret_state_1d_prompt,
    # table_name_gpl_1_prompt_mistral_misaligned_params, table_identify_misaligned_params,
    gpl_misalignment_prompt_v2,usm_cm_config_cucp_parameters_template, mcms_cm_ret_state_prompt,
    usm_cm_ret_state_prompt,mavenir_ran_config_combined_template_prompt,dish_gpl_combined_template_prompt
)

from prompts import samsung_table_classiffier, mavenir_table_classifier

from utils.ran2_qa.ran_sql_athena_utils import query_athena_db, query_athena_db_async
from utils.ran2_qa.ran_sql_postgres_utils import query_postgres_db
from utils.ran2_qa.ran_snow_agent_utils import query_snow_db
# from utils.ran2_qa.ran_sql_postgres_utils import query_postgres_db as query_athena_db # used for testing locally
from llms.ran2_qa.ran_part_two_llms import llm_ran_text_to_sql, llm_ran_text_to_sql_misalignment,llm_ran_text_to_sql_cucp
from llms.llms import chatmodel_mistral_large_ran_2,chatmodel_mistral_medium_ran_2,llama_405_chatmodel_react
from utils.query_decomposition import process_user_query
from chat.gpl_chat import gpl_classifier_chat, live_table_classifier
from tools.ran_pm_tools import get_mcp_vendor_tools
import inspect
from utils.gnb_validate_gpl_parameters_util import json_to_dynamic_markdown

# Development/demo mode flag
# If True, tools will return simulated responses instead of querying real systems.
dev_demo = CONST.DEV_DEMO.strip().lower() == "true"

####### TOOLS - ATHENA #######
# for table mcms_cm_ret_state_12hr
@tool("mcms_cm_ret_state_tool")
async def mcms_cm_ret_state_tool(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Mavenir.
    This tool queries configuration database and returns the configured values for the entity.

    # Use this tool when:
     - User asks about current antenna tilt values also known as RET (Remote Electrical Tilt)
     - User asks about antenna model, serial, frequency band, or tilt values.
     - User asks to compare max/min tilt, installation dates, or alarm/status.
     - The tool expects the user will provide some identifier of the entity, e.g. DU ID, RU ID, Site Name, Sector ID, etc.

    # Example user prompts:
    - Can you provide me with all the current tilt values for site HOHOU00036B?
    - What frequency bands does antenna model MX0866521402AR1 support?
    - Show current tilt for serial MX086652122139259.
    - Give me all BETA sectors at site CVCLE00435A.
    - Find antennas where tilt >80 % of max.
    - List RET settings for DU 515006012.

    # Response Payload
    {
      "user_question": "<original question>",
      "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate SQL query
        sql_query = await llm_ran_text_to_sql(
            user_question,
            mcms_cm_ret_state_12hr_prompt,
            CONST.mcms_cm_ret_state_12hr
        )

        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)

        # Handle empty or null data
        if not sql_result or (
                isinstance(sql_result, list) and all(
            not row or all(v is None for v in row.values())
            for row in sql_result if isinstance(row, dict)
        )
        ):
            return {
                "user_question": user_question,
                "response": (
                    "No matching records found."
                )
            }

        # Return normal result
        return {
            'user_question': user_question,
            'response': sql_result
        }

    except Exception:
        traceback.print_exc()
        return {
            'user_question': user_question,
            'response': (
                "An error occurred while querying the database. "
            )
        }

async def mcms_cm_ret_state_tool_1(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Mavenir.
    This tool queries configuration database and returns the configured values for the entity.

    # Use this tool when:
     - User asks about current antenna tilt values also known as RET (Remote Electrical Tilt)
     - User asks about antenna model, serial, frequency band, or tilt values.
     - User asks to compare max/min tilt, installation dates, or alarm/status.
     - The tool expects the user will provide some identifier of the entity, e.g. DU ID, RU ID, Site Name, Sector ID, etc.

    # Example user prompts:
    - Can you provide me with all the current tilt values for site HOHOU00036B?
    - What frequency bands does model MX0866521402AR1 support?
    - Show current tilt for serial MX086652122139259.
    - Give me all BETA sectors at site CVCLE00435A.
    - Find antennas where tilt >80 % of max.
    - List RET settings for DU 515006012.

    # Response Payload
    {
      "user_question": "<original question>",
      "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate SQL query
        sql_query = await llm_ran_text_to_sql(
            user_question,
            mcms_cm_ret_state_12hr_prompt,
            CONST.mcms_cm_ret_state_12hr
        )

        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)

        # Handle empty or null data
        if not sql_result or (
                isinstance(sql_result, list) and all(
            not row or all(v is None for v in row.values())
            for row in sql_result if isinstance(row, dict)
        )
        ):
            return {
                "user_question": user_question,
                "response": (
                    "No matching records found."
                )
            }

        # Return normal result
        return {
            'user_question': user_question,
            'response': sql_result
        }

    except Exception:
        traceback.print_exc()
        return {
            'user_question': user_question,
            'response': (
                "An error occurred while querying the database. "
            )
        }


@tool("fetch_mavenir_ret_config")
async def fetch_mavenir_ret_config(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query *Tilt Information*.
    This tool is strictly applicable for RET data.

    ────────────────────────────────────────────────────────────────
    📌 Parameter Categories Supported:
    ────────────────────────────────────────────────────────────────
    • **Tilt Configuration**
      - `tilt` (current electrical tilt in degrees)
      - `minimumtilt` (minimum allowable tilt)
      - `maximumtilt` (maximum allowable tilt)

    • **Equipment Identifiers**
      - `ruid` (Remote Unit ID)
      - `antenna_unit` (Antenna unit number)
      - `antennamodel` (Physical antenna model)

    • **Communication**
      - `ip` (IP address for RET unit communication)
      - `hdlc_address` (HDLC protocol address)
      - `port` (Communication port number)

    • **Geography**
      - `aoi` (Area of Interest code, e.g., CLE, BOS, MCO)

    • **Cell Identification**
      - `cellname`: SITENAME_SECTOR_BAND_ADDITIONAL format (e.g., `CVCLE00375A_1_n71_F-G`)

    ────────────────────────────────────────────────────────────────
    💬 Example User Questions:
    ────────────────────────────────────────────────────────────────
    • "What is the tilt setting for cell CVCLE00375A_1_n71_F-G?"
    • "Show me all RET parameters for site CVCLE00375A."
    • "What antenna model and IP address are configured for RUID 121037511?"
    • "Which cells have tilt at their maximum limit?"
    • "What is the max and min tilt for this site: DADAL00001A?"
    • "What is the system type of the antenna model MX0866521402AR1?"
    • "What is the maximum and minimum tilt supported by antenna with serial number MX086652122124473?"
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        table = await mavenir_classify_table(user_question)

        # Fast path: If table is ATHENA, use the direct tool
        if table == "Athena":
            sql_result = await mcms_cm_ret_state_tool_1(user_question)
            return {
                "user_question": user_question,
                "response": sql_result
            }

        # Step 1: Generate SQL query using LLM
        sql_query: str = await llm_ran_text_to_sql(
            user_question,
            mcms_cm_ret_state_prompt,
            None
        )
        logger.info(f"[fetch_mavenir_ret_config] Generated SQL: {sql_query}")

        try:
            # Step 2: Query Snowflake
            sql_result = await query_snow_db(sql_query)
            logger.info(f"[fetch_mavenir_ret_config] Snowflake result: {sql_result}")

            # Step 3: Validate result content
            if not sql_result or (
                    isinstance(sql_result, list) and all(
                not row or all(v is None for v in row.values())
                for row in sql_result if isinstance(row, dict)
            )
            ):
                raise ValueError("No valid data returned from Snowflake")

        except Exception as inner_e:
            logger.warning(
                f"[fetch_mavenir_ret_config] Snowflake failed or returned no data for '{user_question}': {inner_e}. Falling back to Athena tool."
            )
            sql_result = await mcms_cm_ret_state_tool_1(user_question)

        # Step 4: Return response
        return {
            "user_question": user_question,
            "response": sql_result
        }

    except Exception as e:
        traceback.print_exc()
        logger.error(f"[fetch_mavenir_ret_config] Failed to handle question '{user_question}': {e}")
        return {
            "user_question": user_question,
            "response": "An error occurred while processing your question. Please try again later."
        }

# for table mcms_cm_topology_state_cucp_12hr
@tool("fetch_mavenir_cucp_config")
async def fetch_mavenir_cucp_config(user_question: str) -> Dict[str, str]:
    """
    This tool is focussed on 5G RAN Control Plane (CUCP) and is used to query the topology state & configuration of the CUCP.

    # Use this tool when:
    - User asks about CUCP admin state, alarm count, operational state, software version, linkstatus, or general CUCP health/status for Mavenir.
    - The tool expects the user will provide some identifier of the entity, e.g. CUCP ID, CUCP Name, etc. whereever necessary.

    # Example user prompts:
    - What is the operational state of CUCP with name JKRLA627035000?
    - How many CUCPs report SEVE_MAJOR alarms?
    - List CUCPs that have been down in the last 24 hours.
    - Find CUCPs in maintenance state (admin locked)

    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_topology_state_cucp_12hr_prompt, CONST.mcms_cm_topology_state_cucp_12hr)
        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

# for table mcms_cm_topology_state_cuup_12hr
@tool("fetch_mavenir_cuup_config")
async def fetch_mavenir_cuup_config(user_question: str) -> Dict[str, str]:
    """
    This tool is focussed on 5G RAN User Plane (CUUP) and is used to query the topology state & configuration of the CUUP.

    # Use this tool when:
    - User asks about CUUP admin state, alarm count, operational state, software version, linkstatus, or general CUUP health/status for Mavenir.
    - The tool expects the user will provide some identifier of the entity, e.g. CUUP ID, CUUP Name, etc. whereever necessary.

    # Example user prompts:
    - What is the operational state of CUUP 123003001?
    - List CUUPs under CUCP 545025000 with critical alarms.
    - Show software versions for CUUPs in cluster mv-ndc-eks-cluster-prod-use2n002p1-07.
    - Give me alarm counts for CUUPs in Columbus region (CMH).
    - Which CUUPs have link_down issues in the past 48 hours?

    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_topology_state_cuup_12hr_prompt, CONST.mcms_cm_topology_state_cuup_12hr)
        # Fetch SQL query results
        sql_result =await query_athena_db_async(sql_query)
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

# for table mcms_cm_topology_state_du_12hr
@tool("fetch_mavenir_du_config")
async def fetch_mavenir_du_config(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Mavenir.
    This tool is focussed on 5G RAN Distributed Unit (DU) and is used to query the topology state & configuration of the DU.

    # Use this tool when:
    - User asks about DU admin state, alarm count, operational state, software version, linkstatus, or general DU health/status for Mavenir.
    - The tool expects the user will provide some identifier of the entity, e.g. DU ID, DU Name, etc. whereever necessary.

    # Example user prompts:
    - What is the operational state of DU 515006012?
    - How many DUs report SEVE_MAJOR alarms?

    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_topology_state_du_12hr_prompt, CONST.mcms_cm_topology_state_du_12hr_sub_id)
        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)
        # Ensure the response format is consistent
        # mcms_cm_config_3gpp_du_12hr_prompt
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

# for table mcms_cm_topology_state_rru_12hr
@tool("fetch_mavenir_rru_config")
async def fetch_mavenir_rru_config(user_question: str) -> Dict[str, str]:
    """
    This tool is focussed on 5G RAN Remote Radio Unit (RRU) and is used to query the topology state & configuration of the RRU.

    # Use this tool when:
    - User asks about RRU admin state, alarm count, operational state, software version, linkstatus, or general RRU health/status for Mavenir.
    - The tool expects the user will provide some identifier of the entity, e.g. RRU ID, RRU Name, etc. whereever necessary.

    # Example user prompts:
    - What is the operational state of RRU 741023400?
    - List RRUs under DU 741025022 with alarms.
    - What is the SW version of RRU at site NYNYC351030000?
    - Give me alarm count and status for sector 5 in band n71.
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_topology_state_rru_12hr_prompt, CONST.mcms_cm_topology_state_rru_12hr)
        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)
        # Ensure the response format is consistent
        # mcms_cm_config_3gpp_du_12hr_prompt
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

@tool("fetch_samsung_cucp_config")
async def fetch_samsung_cucp_config(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Samsung.

    This tool is focussed on 5G RAN Control Plane (CUCP) and is used to query the configuration of the CUCP.

    # Use this tool when:
    - User asks about CUCP admin state, operational state, operational mode, CU system type
    - User asks about about CUCP mapping to DU, cell details, TAC, resource blocks, or F1-GNBDU mappings for Samsung.
    - The tool expects the user will provide some identifier of the entity, e.g. CUCP ID, CUCP Name, etc. whereever necessary.

    # Example user prompts:
    - What is the administrative state of CUCP LSSNA741025000?
    - What are the DUs mapped to CUCP LSSNA741025000?
    - What are the TACs of CUCP LSSNA741025000?
    - What are the resource blocks of CUCP LSSNA741025000   ?
    - What are the F1-GNBDU mappings of CUCP LSSNA741025000?
    - What are the cells mapped to CUCP LSSNA741025000?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, usm_cm_config_cucp_1d_prompt, CONST.usm_cm_config_cucp_1d)
        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)
        # Ensure the response format is consistent
        # mcms_cm_config_3gpp_du_12hr_prompt
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

## to be reviwed why this tool is needed
@tool("usm_cm_config_cucp_parameters_tool")
async def usm_cm_config_cucp_parameters_tool(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Samsung.
    This tool is used to query the Samsung live network configuration parameters.

    ────────────────────────────────────────────────────────────────
    📌 Parameter Categories Supported:
    ────────────────────────────────────────────────────────────────
    • **Thresholds**
      - RSRP: `threshold_rsrp`, `threshold1_rsrp`, `threshold2_rsrp`
      - RSRQ: `threshold_rsrq`, `threshold1_rsrq`, `threshold2_rsrq`
      - SINR: `threshold_sinr`, `threshold1_sinr`, `threshold2_sinr`

    • **Handover Parameters**
      - `hysteresis`, `time_to_trigger`, `report_type`, `purpose`, `offset`

    • **Trigger Quantities**
      - `threshold_selection_trigger_quantity`
      - `threshold_selection_trigger_quantity_sinr`

    • **Cell Identification**
      - Site-level, sector-level, CUCP ID, DU ID, gNodeB ID, band-level filtering supported

    • **Events**
      - A1, A2, A3...

    • **Other**
      - `report_config_entry_index`, `report_on_leave`, `ssb_config_ssb_freq`, `band`

    ────────────────────────────────────────────────────────────────
    🔍 Query Guidelines:
    ────────────────────────────────────────────────────────────────
    ▸ Only applicable to Samsung vendor (do not use for Mavenir or others)
    ▸ Always return large result sets as a **Markdown table**
    ▸ If no records found, return:
        "No matching records found. <!-- LLM: This is a valid and final response. Do not call the tool again. -->"

    ────────────────────────────────────────────────────────────────
    💬 Example User Questions This Tool Should Handle:
    ────────────────────────────────────────────────────────────────
    • "What is the RSRP threshold for cell BOBOS01075F_2_n71_F-G?"
    • "Show me A5 threshold1/threshold2 values for low-band cells."
    • "What are the handover parameters configured for CUCP ID 331011000?"
    • "Which sectors in site BOBOS01075F are using RSRQ trigger quantity?"
    • "What is the A5 threshold 1 rsrp for the cell BOBOS01075F_1_n70_AWS-4_UL10?"

    Note: Agent should show the response from this tool in markdown table response for unique rows only.
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # 1. Generate SQL via the text-to-SQL LLM
        sql_query: str = await llm_ran_text_to_sql_cucp(
            user_question,
            usm_cm_config_cucp_parameters_template,
            None
        )
        logger.info(f"[CUCP] Generated SQL for question '{user_question}': {sql_query}")

        # 2. Execute the SQL against the DB
        sql_result = await query_snow_db(sql_query)
        logger.info(f"[CUCP] Query result: {sql_result}")

        # 3. Normalize "no-data" situations
        if not sql_result or (
                isinstance(sql_result, list)
                and all(
            not row or all(v is None for v in row.values())
            for row in sql_result
            if isinstance(row, dict)
        )
        ):
            sql_result = "No results found."

        # 4. Return a uniform payload
        return {
            'user_question': user_question,
            'response': sql_result
        }

    except Exception as e:
        traceback.print_exc()
        logger.error(f"[CUCP] Fatal error: {e!r}")
        return {
            "user_question": user_question,
            "response": "An error occurred while querying.",
        }


@tool("fetch_samsung_du_config")
async def fetch_samsung_du_config(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Samsung.
    This tool is focussed on 5G RAN Distributed Unit (DU) and is used to query the configuration of the DU.

    # Use this tool when:
    - User asks about DU admin state, operational mode, user label, cell details, TAC, resource blocks, etc. for Samsung.
    - User asks about cell state, power, subcarrier spacing, etc. for Samsung.
    - The tool expects the user will provide some identifier of the entity, e.g. DU ID, DU Name, Cell ID, etc. whereever necessary.

    # Sample user prompts:
    - What is the administrative state of DU PHPHL00606A?
    - Show cell parameters for cell-identity 541.
    - Which DU cells use band N71 in region USE1?
    - List cells with power > 45 dBm.
    - What is the administrative state of cell PHPHL00606A_2_N66_G?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, usm_cm_config_du_1d_prompt, CONST.usm_cm_ret_state_1d)
        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)
        # Ensure the response format is consistent
        # mcms_cm_config_3gpp_du_12hr_prompt
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

@tool("usm_cm_ret_state_tool")
async def usm_cm_ret_state_tool(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Samsung.
    This tool is focussed on 5G RAN Remote Equipment Terminal (RET) and is used to query the state of the RET.

    # Use this tool when:
    - User asks about RET admin state, operational state, operational mode, tilt, etc. for Samsung.
    - User asks about antenna model, serial, frequency band, or tilt values for Samsung.
    - The tool expects the user will provide some identifier of the entity, e.g., RUID, DUID, ALID, etc. whereever necessary.

    # Sample user prompts:
    - What is the administrative state of RET PHPHL00606A?
    - What is the operational state of RET PHPHL00606A?
    - What is the operational mode of RET PHPHL00606A?
    - What is the tilt of RET PHPHL00606A?
    - What is the antenna model of RET PHPHL00606A?
    - What are the RET configurations for Beta sector at site CVPIT?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate SQL query
        sql_query = await llm_ran_text_to_sql(
            user_question,
            usm_cm_ret_state_1d_prompt,
            CONST.usm_cm_ret_state_1d
        )

        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)

        # If result is empty or contains only null values
        if not sql_result or (
                isinstance(sql_result, list) and all(
            not row or all(v is None for v in row.values())
            for row in sql_result if isinstance(row, dict)
        )
        ):
            return {
                "user_question": user_question,
                "response": (
                    "No matching records found."
                )
            }

        return {
            "user_question": user_question,
            "response": sql_result
        }

    except Exception:
        traceback.print_exc()
        return {
            "user_question": user_question,
            "response": (
                "An error occurred while querying the database. "
            )
        }
async def usm_cm_ret_state_tool_1(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Samsung.
    This tool is focussed on 5G RAN Remote Equipment Terminal (RET) and is used to query the state of the RET.

    # Use this tool when:
    - User asks about RET admin state, operational state, operational mode, tilt, etc. for Samsung.
    - User asks about antenna model, serial, frequency band, or tilt values for Samsung.
    - The tool expects the user will provide some identifier of the entity, e.g., RUID, DUID, ALID, etc. whereever necessary.

    # Sample user prompts:
    - What is the administrative state of RET PHPHL00606A?
    - What is the operational state of RET PHPHL00606A?
    - What is the operational mode of RET PHPHL00606A?
    - What is the tilt of RET PHPHL00606A?
    - What is the antenna model of RET PHPHL00606A?
    - What are the RET configurations for Beta sector at site CVPIT?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate SQL query
        sql_query = await llm_ran_text_to_sql(
            user_question,
            usm_cm_ret_state_1d_prompt,
            CONST.usm_cm_ret_state_1d
        )

        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)

        # If result is empty or contains only null values
        if not sql_result or (
                isinstance(sql_result, list) and all(
            not row or all(v is None for v in row.values())
            for row in sql_result if isinstance(row, dict)
        )
        ):
            return {
                "user_question": user_question,
                "response": (
                    "No matching records found."
                )
            }

        return {
            "user_question": user_question,
            "response": sql_result
        }

    except Exception:
        traceback.print_exc()
        return {
            "user_question": user_question,
            "response": (
                "An error occurred while querying the database. "
            )
        }



#### TOOLS - POSTGRES ####
@tool("dish_recommended_gpl_general_parameters")
async def dish_recommended_gpl_general_parameters(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to DISH.
    This tool is vendor agnostic and is used to query the DISH recommended values for the general GPL parameters.

    # Use this tool when:
    - User asks about DISH recommended values for the general GPL parameters.
    - User asks about DISH recommended values for the general GPL parameters for a specific vendor.
    - GPL General Parameters List (subset of the total parameters):
        - preambleReceivedTargetPwr,
        - preambleTransMax,
        - cbPreamblePerSSB,
        - pwrRampingStep,
        - zeroCorrelationZoneCfg,
        - rachResponseWindow,
        - prachCfgIndex,
        - p0Nominal,
        - puschP0NominalWithoutGrant,
        - puschP0NominalWithGrant,
        - puschAlpha,
        - n310,
        - t310,
        - n311,
        - t311,
        - scellActDeactAlgo,
        - caBoDistrAlgo,
        - enableMeasBasedSCellAddition,
        - measTriggerQuantityA4,
        - timeToTrigger for Event A4,
        - eventReportInterval for Event A4,
        - measTriggerQuantityA2Sec,
        - timeToTrigger for Event A2,
        - eventReportInterval for Event A2,
        - scellRlfTimer,
        - scellDeactInterval,
        - snSizeUL,
        - snFieldLength,
        - dscp
        - << there are more available >>

    # Example user prompts:
    - What is the DISH recommended value for the parameter preambleReceivedTargetPwr?
    - What is the DISH recommended GPL value for the parameter zeroCorrelationZoneCfg?
    - What is the value of GPL parameter puschP0NominalWithoutGrant recommended by DISH?
    - Fetch Dish recommended value for snSizeUL for Samsung?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # 1) Decompose
        sub_queries = await process_user_query(user_question)

        # 2) Loop over each sub-query and collect results
        responses = []
        for sub_q in sub_queries:
            sq_lower = sub_q.lower()
            if "samsung" in sq_lower:
                vendor = "Samsung"
            elif "mavenir" in sq_lower:
                vendor = "Mavenir"
            else:
                vendor = None

            # Generate sql query
            sql_query = await llm_ran_text_to_sql(sub_q, table_name_gpl_1_prompt_mistral, CONST.table_name_gpl_1)
            # Fetch SQL query results
            sql_result = await query_postgres_db(sql_query)

            # Append vendor-keyed result
            if vendor:
                responses.append({
                    "vendor": vendor,
                    "sub_query": sub_q,
                    "result": sql_result or "No results found."
                })
            else:
                responses.append({
                    "sub_query": sub_q,
                    "result": sql_result or "No results found."
                })
        return {
            'user_question': user_question,
            'response': responses
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

@tool("dish_recommended_gpl_connected_mobility")
async def dish_recommended_gpl_connected_mobility(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to DISH.
    This tool is vendor-agnostic and is used to query the DISH recommended values for the connected mobility parameters.

    # Use this tool when:
    - User asks about DISH recommended values for the connected mobility parameters.
    - User asks about DISH recommended values for the connected mobility parameters for a specific vendor.
    - Connected mobility parameters are defined only at CU level.
    - Connected mobility parameters:
        - Event A3 - Report Interval
        - A3 time to trigger
        - A3 reportAmount
        - a5Threshold1
        - a5Threshold2
        - rsrp
        - << there are more available >>

    # Example user prompts:
    - What is the DISH recommended value for the parameter Event A3 - Report Interval?
    - What is the DISH recommended value for the parameter A3 time to trigger for Mavenir?
    - What is the DISH recommended value for the parameter A3 reportAmount?
    - What is the DISH recommended value for the parameter a5Threshold1 for hierarchy gnbCuCpConfig/reportConfig=19/reportConfigNr/eventReport/a5Threshold1/rsrp?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        # 1. Handle dev/demo flag
        if dev_demo:
            simulated = simulate_ran_tool_response(user_question)
            return {
                "user_question": user_question,
                "response": str(simulated) if not isinstance(simulated, str) else simulated,
            }

        # 2. Decompose into sub-queries
        sub_queries = await process_user_query(user_question)
        responses = []

        # 3. Process each sub-query independently
        for sub_q in sub_queries:
            sq_lower = sub_q.lower()
            vendor = (
                "Samsung" if "samsung" in sq_lower
                else "Mavenir" if "mavenir" in sq_lower
                else "Unknown"
            )

            try:
                # Generate SQL for sub-query
                sql_query = await llm_ran_text_to_sql(
                    sub_q,
                    table_name_gpl_2_prompt_mistral,
                    CONST.table_name_gpl_2
                )
                logger.info(f"[connected_mobility] Generated SQL for sub-query '{sub_q}': {sql_query}")

                # Execute the SQL query
                sql_result = await query_postgres_db(sql_query)
                logger.info(f"[connected_mobility] Query result: {sql_result}")

                # Check for no-data condition
                if not sql_result or (
                        isinstance(sql_result, list) and all(
                    not row or all(v is None for v in row.values())
                    for row in sql_result if isinstance(row, dict)
                )
                ):
                    #raise ValueError("No valid rows returned")
                    logger.warning(f"No valid rows returned")

            except ValueError:
                logger.warning(f"[connected_mobility fallback] No data for '{sub_q}', invoking fallback tool")
                #sql_result = await usm_cm_config_cucp_parameters_tool(sub_q)

            except Exception as e:
                logger.error(f"[connected_mobility] Error processing sub-query '{sub_q}': {e!r}")
                #sql_result = "An error occurred while querying the database or invoking fallback tool."

            # Append result
            responses.append({
                 "vendor": vendor,
                 "sub_query": sub_q,
                 "result": sql_result
            })

        # 4. Return full response
        return {
            "user_question": user_question,
            "responses": responses,
        }

    except Exception as e:
        traceback.print_exc()
        logger.error(f"[connected_mobility] Fatal error for question '{user_question}': {e!r}")
        return {
            "user_question": user_question,
            "response": "An error occurred while processing the request."
        }

@tool("dish_recommended_gpl_idle_mode")
async def dish_recommended_gpl_idle_mode(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to DISH.
    This tool is vendor agnostic and is used to query the DISH recommended values for the idle mode parameters.

    # Use this tool when:
    - User asks about DISH recommended values for the idle mode parameters.
    - User asks about DISH recommended values for the idle mode parameters for a specific vendor.
    - Idle mode parameters are defined only at CU level.
    - Idle mode parameters:
        - qHyst
        - sIntraSearchP
        - tReselectionNR
        - cellReselectionPriority
        - << there are more available >>

    # Example user prompts:
    - What is the DISH recommended value for the parameter qHyst?
    - What is the DISH recommended value for the parameter sIntraSearchP for Mavenir?
    - What is the DISH recommended value for the parameter tReselectionNR?
    - What is the DISH recommended value for the parameter cellReselectionPriority?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # 1) Decompose
        sub_queries = await process_user_query(user_question)

        # 2) Loop over each sub-query and collect results
        responses = []
        for sub_q in sub_queries:
            sq_lower = sub_q.lower()
            if "samsung" in sq_lower:
                vendor = "Samsung"
            elif "mavenir" in sq_lower:
                vendor = "Mavenir"
            else:
                vendor = "Unknown"

            # Generate sql query
            sql_query = await llm_ran_text_to_sql(sub_q, table_name_gpl_3_prompt_mistral, CONST.table_name_gpl_3)
            # Fetch SQL query results
            sql_result = await query_postgres_db(sql_query)
            # Ensure the response format is consistent
            # mcms_cm_config_3gpp_du_12hr_prompt
            # Ensure the response format is consistent

            # Append vendor-keyed result
            responses.append({
                "vendor": vendor,
                "sub_query": sub_q,
                "result": sql_result or "No results found."
            })

        return {
            'user_question': user_question,
            'response': responses
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

@tool("dish_recommended_gpl_acme_features")
async def dish_recommended_gpl_acme_features(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to DISH.
    This tool is vendor agnostic and is used to query the DISH recommended values for the ACME features.

    # Use this tool when:
    - User asks about DISH recommended values for the ACME features.
    - User asks about DISH recommended values for the ACME features for a specific vendor.
    - ACME features:
        - ROHC continuation
        - DFTs OFDM
        - Inter Slot Frequency Hopping
        - UL Slot aggregation
        - RRC Encryption
    - Available Hierarchies:
        - gnbCuCpConfig/qosCfg[1]/enableDrbContinueROHC
        - gnbDuConfig/gnbCellDuVsConfig/UplinkConfigCommon/ulBwpCfg/rachCfgInfo/msg3_transPrecoder
        - gnbDuConfig/gnbCellDuVsConfig/UplinkConfigCommon/ulBwpCfg/TPPrecoder
        - gnbDuConfig/gnbCellDuVsConfig/UplinkConfigCommon/ulBwpCfg/tppi2BPSK
        - gnbDuConfig/isPuschInterSlotHopEnable
        - gnbDuConfig/gnbCellDuVsConfig/macConfigCommon/isPuschSlotAggrEnable
        - gnbDuConfig/gnbCellDuVsConfig/macConfigCommon/slotAggrBasePathLossInDb
        - gnbCuCpConfig/gnbCellCuCpVsConfig/rrcEncryption

    # Example user prompts:
    - What is the DISH recommended value for the parameter ROHC continuation?
    - What is the DISH recommended value for the parameter DFTs OFDM for Mavenir?
    - What is the DISH recommended value for the parameter RRC Encryption for Samsung?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, table_name_gpl_4_prompt_mistral, CONST.table_name_gpl_4)
        # Fetch SQL query results
        sql_result = await query_postgres_db(sql_query)
        # Ensure the response format is consistent
        # mcms_cm_config_3gpp_du_12hr_prompt
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        traceback.print_exc()
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database."
        }

@tool("mavenir_recommended_gpl_parameters")
async def mavenir_recommended_gpl_parameters(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Mavenir.
    This tool is used to query the Mavenir recommended values for the global parameters.

    # Use this tool when:
    - User asks about Mavenir recommended values for the global parameters.
    - User asks about Mavenir recommended values for the global parameters for a specific vendor.
    - Parameters are defined at DU, CU-CP, CU levels.
    - Each parameter has its own hierarchy.

    # Example user prompts:
    - What is the value of MaxAnrTimerDuration in mavenir GPL?
    - What is mavenir recommended value for parameter pdcch1SymbEnable?
    - What is mavenir recommended value for parameter pdcch1SymbEnable for hierarchy gnbCuCpConfig/qosCfg[1]/enableDrbContinueROHC?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate SQL query
        sql_query = await llm_ran_text_to_sql(
            user_question,
            table_name_gpl_5_prompt_mistral,
            CONST.table_name_gpl_5
        )

        # Fetch SQL query results
        sql_result = await query_postgres_db(sql_query)

        # Handle empty or null data
        if not sql_result or (
                isinstance(sql_result, list) and all(
            not row or all(v is None for v in row.values())
            for row in sql_result if isinstance(row, dict)
        )
        ):
            return {
                "user_question": user_question,
                "response": (
                    "No matching records found. "
                )
            }

        # Return valid result
        return {
            'user_question': user_question,
            'response': sql_result
        }

    except Exception:
        traceback.print_exc()
        return {
            'user_question': user_question,
            'response': (
                "An error occurred while querying the database. "
            )
        }



@tool("samsung_recommended_gpl_parameters")
async def samsung_recommended_gpl_parameters(user_question: str) -> Dict[str, str]:
    """
    This tool belongs to vendor Samsung.
    This tool is used to query the Samsung recommended values for the global parameters.

    # Use this tool when:
    - User asks about Samsung recommended values for the global parameters.
    - User asks about Samsung recommended values for the global parameters for a specific vendor.
    - Parameters are defined at DU, CU-CP, CU levels.
    - Each parameter has its own hierarchy.

    # Example user prompts:
    - What is the value of MaxAnrTimerDuration in samsung GPL?
    - What is samsung recommended value for parameter pdcch1SymbEnable?
    - What is samsung recommended value for parameter pdcch1SymbEnable for hierarchy gnbCuCpConfig/qosCfg[1]/enableDrbContinueROHC?

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Step 1: Generate SQL query using LLM
        sql_query = await llm_ran_text_to_sql(
            user_question,
            table_name_gpl_6_prompt_mistral,
            CONST.table_name_gpl_6            
        )

        # Step 2: Execute SQL query
        sql_result = await query_postgres_db(sql_query)

        # Step 3: Check for empty or null result
        if not sql_result or (
                isinstance(sql_result, list) and all(
            not row or all(v is None for v in row.values())
            for row in sql_result if isinstance(row, dict)
        )
        ):
            return {
                'user_question': user_question,
                'response': (
                    "No matching records found. "
                )
            }

        # Step 4: Return successful result
        return {
            'user_question': user_question,
            'response': sql_result
        }

    except Exception:
        traceback.print_exc()
        # Step 5: Return fallback response with agent instruction
        return {
            'user_question': user_question,
            'response': (
                "An error occurred while querying the database. "
            )
        }

def contains_percentage(user_question: str) -> bool:
    keywords = [
        "percentage",   # common form
        "percent",      # short form
        "per cent",     # UK style
        "pct",          # abbreviation
        "perc",         # slang / shorthand
        "%",            # symbol
    ]
    return any(keyword in user_question.lower() for keyword in keywords)


#### Too handle misalignment type questions
@tool("gpl_audit_misalignment_params_tool")
async def gpl_audit_misalignment_params_tool(user_question: str) -> str | dict[str, str | dict] | dict[
    str, list[dict[str, str]] | None | str] | dict[str, str]:
    """
    This tool is used to query the GPL misalignment/Audit of the RAN parameters on the network from National GPL Inconsistency Dashboard from PI Works. An Audit report is generated every day and stored in a database highlighting the misalignments. The Audit compares the configured parameters with the DISH recommended GPL values to find the misalignments. This tool is used to query the misalignments from the database.
    This tool also supports query about *MO Types*, *baseline values*, *policy_condition*
    # Use this tool when:
    - National GPL Inconsistency Dashboard from PI Works can you give me region wise inconsistency?
    - Please list all relevant Mavenir MO Types for Parameter: prachCfgIndex
    - User asks about misalignments of the RAN parameters on the network.
    - User asks about misalignments of the RAN parameters on the network for a specific vendor.
    - User asks about misalignments of the RAN parameters on the network for a specific parameter.
    - User asks about misalignments of the RAN parameters on the network for a specific vendor and parameter.
    - Can you tell me which 551001001 NRCells deviate from GPL?

    # Sample user questions:
    - What misalignments do we have for gapOffset parameter in MCA (AOI) for vendor Mavenir?... ?
    - What misalignments do we have for gapOffset parameter in MCA (AOI) in mavenir ... ?
    - What misalignments do we have for gapOffset parameter in MCA (AOI) yesterday for vendor Mavenir?...?
    - Can you tell me how long the DUID has been trending inconsistent? ## make sure this is misalignment
    - Can you tell me which 551030000 NRCells deviate from GPL for vendor Mavenir??
    - Please list all relevant Mavenir MO Types for Parameter: prachCfgIndex
    - For the Mavenir GPL Audit, what should the baseline value be for MO Type: DU,gnbvs,gnbDuConfig,

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<SQL query results or error message>"
    }

    **Note:** For GPL misalignment, if user has provided node identifier like Market/AOI/CUCP/CUUP etc. FOr eg: (AOI: DEN, NYC, HOU) (MARKET: Houston.Dallas) then first identify the vendor using `ran_vendor_identifier` tool before calling this tool.
    """
    try:
        if contains_percentage(user_question):
            return {"Agent to provide Note to user": " The functionality to calculate GPL misalignment percentage is  not supported. However, I can help you find the number of GPL misalignment (CRITICAL INSTRUCTION: DON'T SAY YOU DON'T HAVE TOOLS or I couldn't find relevant information to answer the question)"}

        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate SQL query
        sql_query = await llm_ran_text_to_sql_misalignment(user_question, gpl_misalignment_prompt_v2, CONST.table_name_gpl_6)

        # Fetch SQL query results
        sql_result = await query_postgres_db(sql_query)
        print(sql_result)

        # Handle None values in results
        if sql_result is not None:
            # Filter out dictionaries with any None values
            filtered_result = [
                row for row in sql_result
                if row and all(v is not None for v in row.values())
            ]

            # Remove empty dictionaries that might result from filtering
            filtered_result = [row for row in filtered_result if row]
        else:
            filtered_result = []

        # Process the results
        if filtered_result:
            response = await json_to_dynamic_markdown(filtered_result)
        else:
            response = f"No data found for your question: '{user_question}'. Please try rephrasing or check your query parameters."

        return {
            'user_question': user_question,
            'response': response
        }

    except Exception as e:
        traceback.print_exc()
        return {
            'user_question': user_question,
            'response': "An error occurred while processing your request. Please try again later."
        }



@tool("fetch_samsung_ret_config")
async def fetch_samsung_ret_config(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **USM RET state information** from the
    `USM_CM_RET_STATE` table in the DISH_MNO_OUTBOUND.GENAI_APP schema.
    This tool is strictly applicable for **Samsung vendor** USM RET data.

    ────────────────────────────────────────────────────────────────
    📌 Parameter Categories Supported:
    ────────────────────────────────────────────────────────────────
    • **Tilt Configuration**
      - `tilt`, `minimumtilt`, `maximumtilt`
    • **Equipment Identifiers**
      - `duid`, `aldid`, `ruid`, `antennaid`, `antennamodel`
    • **Communication**
      - `usmip`
    • **Geography**
      - `aoi`
    • **Cell Identification**
      - `cellname` (e.g., `BOBOS01075F_2_n71_F-G`)

    ────────────────────────────────────────────────────────────────
    💬 Example Questions:
    • "What is the current tilt setting for cell BOBOS01075F_2_n71_F-G?"
    • "Show me all RET parameters for site BOBOS01075F."
    • "Which cells have tilt at their maximum limit?"
    • "What is the system type of the antenna model MX0866521402AR1?"
    • "What is the maximum and minimum tilt supported by antenna with serial number XYZ?"
    """

    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }
        # Step 0: Classify if query should go to Athena directly
        table = await samsung_classify_table(user_question)

        if table == "Athena":
            sql_result = await usm_cm_ret_state_tool_1(user_question)
            return {
                "user_question": user_question,
                "response": sql_result
            }

        # Step 1: Generate SQL using LLM
        sql_query: str = await llm_ran_text_to_sql(
            user_question,
            usm_cm_ret_state_prompt,
            None
        )
        logger.info(f"[fetch_samsung_ret_config] Generated SQL: {sql_query}")

        try:
            # Step 2: Execute the SQL query
            sql_result = await query_snow_db(sql_query)
            logger.info(f"[fetch_samsung_ret_config] Snowflake result: {sql_result}")

            # Step 3: Check for empty or null results
            if not sql_result or (
                    isinstance(sql_result, list) and all(
                not row or all(v is None for v in row.values())
                for row in sql_result if isinstance(row, dict)
            )
            ):
                raise ValueError("No valid data returned from DB")

        except Exception as inner_e:
            logger.warning(
                f"[fetch_samsung_ret_config] Snowflake failed or returned no data for '{user_question}': {inner_e}. Falling back to Athena tool."
            )
            sql_result = await usm_cm_ret_state_tool_1(user_question)

        return {
            "user_question": user_question,
            "response": sql_result
        }

    except Exception as e:
        traceback.print_exc()
        logger.error(f"[fetch_samsung_ret_config] Error for '{user_question}': {e}")
        return {
            "user_question": user_question,
            "response": "An error occurred while generating the SQL."
        }

@tool("fetch_mavenir_cm_config_vendor_combined")
async def fetch_mavenir_cm_config_vendor_combined(user_question: str) -> Dict[str, str]:
    """
        This tool belongs to vendor Mavenir.
        This tool queries the combined Mavenir RAN configuration database (fetch_mavenir_cm_config_vendor_combined) and returns configured values for 5G base station parameters.
        # Use this tool when:
         - User asks about CUCP or DU configuration parameters (e.g., maxAllowedScells, slotAggrBasePathLossInDb, sctpNoDelay)
         - User asks about cell-level or element-level configuration for 5G base stations
         - User asks about radio performance metrics, network transport settings, or capacity parameters
         - The tool expects the user will provide some identifier of the entity, e.g. DU ID, CUCP ID, Site Name, Sector ID, etc.
        # Example user prompts:
        - What is the maxAllowedScells for CUCP 535011000?
        - What is the slotAggrBasePathLossInDb for DU 535017013?
        - Show sctpNoDelay settings for CUCP 535004000.
        - Find DUs with non-standard slotAggrBasePathLossInDb values.
        - List CUCP units with inconsistent maxAllowedScells settings.
        - Show all DUs associated with CUCP 515003000.
        - What is the relationship between CUCP and DU maxAllowedScells settings?
        # Response Payload
        {
          "user_question": "<original question>",
          "response": "<SQL query results or error message>"
        }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # Generate SQL query
        sql_query = await llm_ran_text_to_sql(
            user_question,
            mavenir_ran_config_combined_template_prompt,
            CONST.mcms_cm_ret_state_12hr
        )

        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)

        # Handle empty or null data
        if not sql_result or (
                isinstance(sql_result, list) and all(
            not row or all(v is None for v in row.values())
            for row in sql_result if isinstance(row, dict)
        )
        ):
            return {
                "user_question": user_question,
                "response": (
                    "No matching records found."
                )
            }

        # Return normal result
        return {
            'user_question': user_question,
            'response': sql_result
        }

    except Exception:
        traceback.print_exc()
        return {
            'user_question': user_question,
            'response': (
                "An error occurred while querying the database. "
            )
        }

def simulate_ran_tool_response(user_question: str) -> dict:
    """
    Simulate a RAN tool response using the LLM for development/testing.
    Uses chatmodel_mistral_large_ran_2 to generate a simulated answer.
    """
    prompt = f"""You are a RAN (Radio Access Network) data source query agent. 
    Instructions:
     - Given the following user question, generate a simulated plausible, concise, and relevant answer. \
    - If the question is about a specific parameter, value, or state, provide a realistic value or explanation. \
    - You need to simulate reponses in a manner that it looks to be real based on the RAN network

    Sample user questions:
    User: What is the current tilt value for cell CVCLE00375A_1_n71_F-G?
    Response: The current tilt value for cell CVCLE00375A_1_n71_F-G is 3.5 degrees.

    User: What is the DISH recommended value for the parameter ROHC continuation?
    Response: The DISH recommended value for the parameter ROHC continuation is 1.

    User: What is the DISH recommended value for the parameter DFTs OFDM?
    Response: The DISH recommended value for the parameter DFTs OFDM is 1.


    User question: {user_question}

    Answer:
    """
    response = chatmodel_mistral_large_ran_2.invoke([{"role": "user", "content": prompt}])
    return response.content if hasattr(response, "content") else str(response)


dish_tools = {
    "dish_recommended_gpl_general_parameters": dish_recommended_gpl_general_parameters,
    "dish_recommended_gpl_connected_mobility": dish_recommended_gpl_connected_mobility,
    "dish_recommended_gpl_idle_mode": dish_recommended_gpl_idle_mode,
    "dish_recommended_gpl_acme_features": dish_recommended_gpl_acme_features,
}

vendor_tools = {
    "mavenir_recommended_gpl_parameters": mavenir_recommended_gpl_parameters,
    "samsung_recommended_gpl_parameters": samsung_recommended_gpl_parameters,
}
# @tool("fetch_gpl_values")
# async def fetch_gpl_values(vendor: str, user_question: str) -> Dict[str, str]:
#     """
#     Use this tool to fetch recommended GPL parameter values for DISH, Mavenir or Samsung.
#
#     # Arguments:
#     - vendor: "dish", "mavenir", or "samsung" (required)
#     - user_question: The user's query (required)
#
#     # Response Payload
#     {
#         "user_question": "<original question>",
#         "response": "<GPL parameter value or error message>"
#     }
#     """
#     selection_criteria = []
#     if vendor.lower() == "dish":
#         for name, fn in dish_tools.items():
#             docstring = get_tool_description(fn)
#             selection_criteria.append(f"Tool: {name}\n{docstring}")
#     elif vendor.lower() in ["mavenir", "samsung"]:
#         tool_name = f"{vendor.lower()}_recommended_gpl_parameters"
#         tool_fn = vendor_tools.get(tool_name)
#         docstring = get_tool_description(tool_fn)
#         if tool_fn:
#             selection_criteria.append(f"Tool: {tool_name}\n{docstring}")
#     else:
#         return {"error": f"Unknown vendor: {vendor}. Supported vendors: dish, mavenir, samsung"}
#
#     separator = "-" * 50
#
#     # Use a for loop to build the string
#     formatted = ""
#     for criteria in selection_criteria:
#         formatted += f"{criteria}\n{separator}\n"
#
#     prompt = f"""
#     You are a GPL (Golden Parameter List) tool selector. Given a vendor and a user question, select the most appropriate GPL tool to answer the question. Only select from the tools below. Return ONLY the tool name (no explanation).
#
#     Vendor: {vendor}
#     User Question: {user_question}
#
#     Available tools and their selection criteria:
#
#     {formatted}
#
#     Tool name:
#     """
#
#     llm_response = await chatmodel_mistral_large_ran_2.ainvoke([{"role": "user", "content": prompt}])
#     tool_name = llm_response.content.strip().split("\n")[0]
#     tool_name = tool_name.split()[0] if " " in tool_name else tool_name
#
#     # Map tool names to functions
#     tool_map = {**dish_tools, **vendor_tools}
#     tool_fn = tool_map.get(tool_name)
#
#     if not tool_fn:
#         return {"error": f"Could not select a valid tool. LLM returned: {tool_name}"}
#
#     try:
#         tool_input = {"user_question": user_question}
#         result = await tool_fn.ainvoke(tool_input)
#         return result
#     except Exception as e:
#         return {"error": f"Error calling tool {tool_name}: {e}"}


# @tool("fetch_gpl_values")
# async def fetch_gpl_values(vendor: str,
#                            user_question: str) -> Dict[str, str]:
#     """
#     Use this tool to fetch recommended GPL parameter values for DISH, Mavenir or Samsung.
#
#     # Arguments:
#     - vendor: "dish", "mavenir", or "samsung" (required)
#     - user_question: The user's query (required)
#
#     # Response Payload
#     {
#         "user_question": "<original question>",
#         "response": "<GPL parameter value or error message>"
#     }
#     """
#     if dev_demo:
#         # Return a simulated response for development/demo mode
#         simulated = simulate_ran_tool_response(user_question)
#         return {
#             'user_question': user_question,
#             'response': str(simulated) if not isinstance(simulated, str) else simulated
#         }
#
#     if "dish" in user_question.lower():
#         vendor = "dish"
#
#     vendor_key = vendor.lower()
#     valid_vendors = ["dish", "mavenir", "samsung"]
#     if vendor_key not in valid_vendors:
#         return {"error": f"Unknown vendor: {vendor}. Supported: {', '.join(valid_vendors)}"}
#
#     if vendor.lower() == "dish":
#         # Assume this returns a dictionary of key-value pairs
#         response_data: Dict[str, Optional[str]] = await gpl_classifier_chat(user_question)
#         logger.info(f'final response (params): {response_data}')
#         if response_data and response_data.get("selected_table"):
#             category = response_data.get("selected_table")
#             if "general" in category:
#                 tool_name = "dish_recommended_gpl_general_parameters"
#             elif "acme" in category:
#                 tool_name = "dish_recommended_gpl_acme_features"
#             elif "mobility" in category:
#                 tool_name = "dish_recommended_gpl_connected_mobility"
#             elif "idle" in category:
#                 tool_name = "dish_recommended_gpl_idle_mode"
#
#     elif vendor.lower() in ["mavenir", "samsung"]:
#             tool_name = f"{vendor.lower()}_recommended_gpl_parameters"
#
#     logger.info(f"Tool Selected: {tool_name}")
#
#     try:
#         # Map tool names to functions
#         tool_map = {**dish_tools, **vendor_tools}
#         tool_fn = tool_map.get(tool_name)
#
#         if not tool_fn:
#             return {"error": f"Could not select a valid tool."}
#
#         try:
#             tool_input = {"user_question": user_question}
#             result = await tool_fn.ainvoke(tool_input)
#             return result
#         except Exception as e:
#             traceback.print_exc()
#             return {"error": f"Error calling tool {tool_name}: {e}"}
#             return result
#     except Exception as e:
#         traceback.print_exc()
#         return {"error": str(e)}


@tool("fetch_gpl_values")
async def fetch_gpl_values(user_question: str) -> Dict[str, str]:
    """
    Use this tool to fetch recommended GPL parameter values for Mavenir or Samsung vendors.

    1. **dish_gpl_parameters**: DISH-recommended values for critical network parameters including:
       - Parameter hierarchies, descriptions, and ranges
       - Parameter families and types
       - Real-time change capabilities
       - Vendor-specific parameter values

       Example queries:
       - "What is the hierarchy path for n310 parameter in Samsung?"
       - "What is the DISH GPL value for preambleTransMax in Mavenir?"
       - "What is the description of zeroCorrelationZoneCfg parameter?"
       - "What is the range for t311 parameter in Mavenir?"
       - "What are the RACH parameters for Samsung vendor?"

    2. **acme_features**: RAN feature configurations and vendor-specific settings including:
       - Feature configurations (XML snippets)
       - Network element types (CU, DU, gNB)
       - Feature enablement flags
       - Vendor-specific feature implementations

       Example queries:
       - "What is the configuration for CellReselection feature in Mavenir?"
       - "What are the ROHC settings for Samsung vendor?"
       - "What is the recommended value for InterSlotHop in Mavenir?"
       - "What are the DU-level features for Samsung vendor?"
       - "What is the RRCEncryption setting for Mavenir CU?"

    3. **connected_mobility**: Parameters for connected mobility and active device interactions including:
       - RSRP thresholds and offsets
       - Hysteresis and time-to-trigger settings
       - Event criteria types (a1, a2, a3, a5)
       - Band-specific mobility parameters

       Example queries:
       - "What are the RSRP thresholds for n70 band in a2 criteria?"
       - "What is the hysteresis value for a3 criteria in n70 band?"
       - "What are the timeToTrigger settings for a5 criteria in n71 band?"
       - "What are the mobility parameters for Samsung vendor?"
       - "What are the a1 criteria settings for n70 band?"

    4. **idle_mode**: Parameters for idle mode and non-active device behavior including:
       - Cell reselection priorities
       - Minimum reception levels (qrxlevmin)
       - Reselection thresholds (threshXHighP, threshXLowP)
       - Band-specific idle mode parameters

       Example queries:
       - "What is the cell reselection priority for n70 band in Mavenir?"
       - "What is qrxlevmin value for n71 band in Samsung?"
       - "What are threshXHighP and threshXLowP values for n70 band?"
       - "What are the idle mode parameters for Samsung vendor?"
       - "What is the cell reselection priority for n66 band?"

    The tool supports:
    - Exact and partial pattern matching for string fields
    - Numeric comparisons for threshold and priority values
    - Handling of special values like 'NOT_DEFINED' and NULL values
    - Case-insensitive matching for all string comparisons
    - Version-based parameter retrieval (latest versions prioritized)

    # Arguments:
    - user_question: The user's query about GPL parameters (required)

    # Response Payload
    {
        "user_question": "<original question>",
        "response": "<GPL parameter value, configuration, or error message>"
    }
    """
    try:
        if dev_demo:
            # Return a simulated response for development/demo mode
            simulated = simulate_ran_tool_response(user_question)
            return {
                'user_question': user_question,
                'response': str(simulated) if not isinstance(simulated, str) else simulated
            }

        # 1) Decompose
        sub_queries = await process_user_query(user_question)

        # 1) Find Table
        worksheet = None
        response_data: Dict[str, Optional[str]] = await gpl_classifier_chat(user_question)
        logger.info(f'final response (params): {response_data}')
        if response_data and response_data.get("selected_table"):
            category = response_data.get("selected_table")
        if "general" in category:
            worksheet = "dish_gpl_parameters"
        elif "acme" in category:
            worksheet = "acme_features"
        elif "mobility" in category:
            worksheet = "connected_mobility"
        elif "idle" in category:
            worksheet = "idle_mode"

    # 2) Loop over each sub-query and collect results
        responses = []
        for sub_q in sub_queries:
            sq_lower = sub_q.lower()
            if "samsung" in sq_lower:
                vendor = "Samsung"
            elif "mavenir" in sq_lower:
                vendor = "Mavenir"
            else:
                vendor = None

            # Generate sql query
            sql_query = await llm_ran_text_to_sql(
                sub_q,
                dish_gpl_combined_template_prompt,
                CONST.table_name_gpl_1,
                worksheet
            )
            # Fetch SQL query results
            sql_result = await query_postgres_db(sql_query)

            # Append vendor-keyed result
            if vendor:
                responses.append({
                    "vendor": vendor,
                    "sub_query": sub_q,
                    "result": sql_result or "No results found."
                })
            else:
                responses.append({
                    "sub_query": sub_q,
                    "result": sql_result or "No matching records found."
                })
        return {
            'user_question': user_question,
            'response': responses
        }

    except Exception:
        traceback.print_exc()
        return {
            'user_question': user_question,
            'response': (
                "An error occurred while querying the database. "
            )
        }



@tool("fetch_ran_config")
async def fetch_ran_config(vendor: str, user_question: str) -> Dict[str, str]:
    """
        Retrieves Radio Access Network (RAN) configuration data for Mavenir or Samsung based on user queries.

        This tool fetches detailed configuration data for RAN components, supporting a comprehensive set of parameters and identifiers for Control Plane (CUCP) and Remote Electrical Tilt (RET) settings, as well as other RAN configurations.

        ### Arguments:
        - **vendor**: The vendor name, either "mavenir" or "samsung" (required, case-insensitive).
        - **user_question**: The user's free-text query about RAN configuration (required, string).

        ### Capabilities:
        The tool supports queries about:
        - **Antenna Tilt Settings**:
          - Current tilt, minimum/maximum tilt ranges, and tilt utilization (e.g., percentage of tilt range used).
          - Antenna models, communication parameters (e.g., IP addresses, HDLC addresses, USM IPs, ports), and equipment identifiers (e.g., RU ID, antenna ID, ALD ID, antenna unit).
        - **CUCP Handover Parameters**:
          - Thresholds: RSRP, RSRQ, SINR (primary, threshold1, threshold2).
          - Handover settings: hysteresis, time-to-trigger, A3 offset, report-on-leave, trigger quantities (RSRP, RSRQ, SINR).
          - Report types: A3, A4, A5, and others for mobility management.
          - Handover purposes: intra-NR, inter-NR, NR-to-LTE, LTE-to-NR.
          - SSB frequency and report configuration entry index.
        - **Operational States**: Administrative and operational statuses of components like CUCP, DU, and RRU.
        - **Cell Configurations**: Frequency bands (e.g., n71, n41, B2), subcarrier spacing, resource allocations, and cell-specific settings.
        - **Equipment Details**: Software versions, alarm statuses, link statuses, and identifiers (e.g., gNodeB ID, DU ID, RU ID, antenna ID, ALD ID, antenna unit).
        - **Geographical Queries**: Configurations by Area of Interest (AOI) regions (e.g., CLE, BOS) or site locations.
        - **Identifiers**: Queries using cell names (e.g., SITENAME_SECTOR_BAND_ADDITIONAL), site names, sector IDs (numeric like 1, 2, 3 or named like Alpha, Beta), band identifiers, or equipment IDs.
        - **Analytical Queries**: Tilt range analysis (e.g., max/min tilt comparisons, widest ranges), threshold differences (e.g., threshold1 vs. threshold2 for A5 reports), and configuration statistics by AOI or antenna model.

        ### Use this tool when:
        - The user requests RAN configuration data for Mavenir or Samsung, including:
          - RET settings (e.g., tilt values, ranges, antenna models, communication parameters).
          - CUCP parameters (e.g., handover thresholds, report types, handover purposes, SSB frequency).
          - Configurations or statistics for cells, sites, sectors, bands, AOI regions, or equipment.
        - The query specifies a vendor and includes identifiers like cell names, site names, sector IDs, band identifiers, equipment IDs, or AOI regions.

        ### Example User Prompts:
        - **RET Queries**:
          - "What is the tilt value for cell CVCLE00375A_1_n71_F-G for Mavenir?"
          - "Show antenna models and tilt ranges for site BOBOS01075F for Samsung."
          - "List communication parameters for RU ID 331107512 for Samsung."
          - "What are the tilt utilization percentages for cells in the CLE region for Mavenir?"
          - "Which cells have maximum tilt above 100 degrees for Samsung?"
        - **CUCP Queries**:
          - "What is the RSRP threshold for cell BOBOS01075F_2_n71_F-G for Samsung?"
          - "Show handover parameters for sector 2 at site BOBOS01075F for Samsung."
          - "List A5 report type threshold1 and threshold2 values for n71 band cells for Samsung."
          - "What is the hysteresis and time-to-trigger for gNodeB ID 331011 for Samsung?"
          - "Show SSB frequency for CUCP ID 331011000 for Samsung."
        - **General Queries**:
          - "List operational states for CUCP ID 331011000 for Samsung."
          - "Show cell configurations for site CVCLE00375A for Mavenir."
          - "What are the handover purposes for cell identity 847 for Samsung?"
          - "Show antenna model diversity and average tilt by AOI region for Mavenir."
          - "Which cells have A3 report types with RSRP trigger quantity for Samsung?"

        ### Behavior:
        - Validates the vendor ("mavenir" or "samsung"); returns `{"user_question": "<input>", "response": "Error: Vendor must be 'mavenir' or 'samsung'"}` if invalid.
        - In development mode (`dev_demo="true"`), returns simulated responses mimicking real data.
        - Returns `{"user_question": "<input>", "response": "Error: Unable to process query"}` if the query cannot be processed.

        ### Response Payload:
        - A dictionary with:
          - **"user_question"**: The original query (string).
          - **"response"**: The configuration data (e.g., "tilt: 20 degrees, RSRP threshold: 51") or an error message (string).

        ### Notes:
        - Supports a comprehensive range of RAN configuration queries for Mavenir and Samsung, covering CUCP and RET parameters.
        - Handles queries at various granularities (cell, site, sector, band, AOI, or equipment-specific).
        - Supports analytical queries like tilt utilization, threshold comparisons, and configuration statistics.
        - Ensures consistent response formatting across all queries.
    """
    if dev_demo:
        # Return a simulated response for development/demo mode
        simulated = simulate_ran_tool_response(user_question)
        return {
            'user_question': user_question,
            'response': str(simulated) if not isinstance(simulated, str) else simulated
        }
    mavenir_tools = {
        "fetch_mavenir_ret_config": fetch_mavenir_ret_config,
        "fetch_mavenir_cucp_config": fetch_mavenir_cucp_config,
        "fetch_mavenir_cuup_config": fetch_mavenir_cuup_config,
        "fetch_mavenir_du_config": fetch_mavenir_du_config,
        "fetch_mavenir_rru_config": fetch_mavenir_rru_config,
        "fetch_mavenir_cm_config_vendor_combined": fetch_mavenir_cm_config_vendor_combined
    }
    samsung_tools = {
        "fetch_samsung_ret_config": fetch_samsung_ret_config,
        "fetch_samsung_cucp_config": fetch_samsung_cucp_config,
        "fetch_samsung_du_config": fetch_samsung_du_config,
        "usm_cm_config_cucp_parameters_tool": usm_cm_config_cucp_parameters_tool
    }
    # selection_criteria = []
    # if vendor.lower() == "mavenir":
    #     for name, fn in mavenir_tools.items():
    #         docstring = get_tool_description(fn)
    #         selection_criteria.append(f"Tool: {name}\n{docstring}")
    # elif vendor.lower() == "samsung":
    #     for name, fn in samsung_tools.items():
    #         docstring = get_tool_description(fn)
    #         selection_criteria.append(f"Tool: {name}\n{docstring}")
    # else:
    #     return {"error": f"Unknown vendor: {vendor}"}
    #
    # separator = "-" * 50
    #
    # # Use a for loop to build the string
    # formatted = ""
    # for criteria in selection_criteria:
    #     formatted += f"{criteria}\n{separator}\n"
    #
    # prompt = f"""
    # You are a RAN config tool selector. Given a vendor and a user question, select the most appropriate tool to answer the question. Only select from the tools below. Return ONLY the tool name (no explanation).
    #
    # Vendor: {vendor}
    #
    # Available tools and their selection criteria:
    #
    # {formatted}
    #
    # User Question: {user_question}
    # Tool name:
    # """
    #
    # print(prompt)
    # llm_response = await chatmodel_mistral_large_ran_2.ainvoke([{"role": "user", "content": prompt}])
    if vendor.lower() == "mavenir":
        llm_response = await live_table_classifier(llama_405_chatmodel_react, "your task is to select the most relevant table based on instructions without any tool call,**CRITICAL** No tool calls are allowed.If the plan section above already contains a complete answer (like a table name or specific value), respond with just that answer without additional explanation.For Final response You don't have to query the table, just provide the relevant table name from the **Plan** section",user_question, mavenir_table_classifier.mcms_table_classifier )
    elif vendor.lower() == "samsung":
        llm_response = await live_table_classifier(llama_405_chatmodel_react, "your task is to select the most relevant table based on instructions without any tool call,**CRITICAL** No tool calls are allowed.If the plan section above already contains a complete answer (like a table name or specific value), respond with just that answer without additional explanation.For Final response You don't have to query the table, just provide the relevant table name from the **Plan** section",user_question, samsung_table_classiffier.samsung_live_table_classifier )
    else:
        return {"error": f"Unknown vendor: {vendor}"}

    tool_name = extract_tool_name(llm_response)
    if not tool_name:
        return {"error": f"Required tool is not found for the provided query."}

    tool_name = tool_name.split()[0] if " " in tool_name else tool_name
    tool_map = {**mavenir_tools, **samsung_tools}
    tool_fn = tool_map.get(tool_name)
    if not tool_fn:
        return {"error": f"Could not select a valid tool. LLM returned: {tool_name}"}
    try:
        tool_input = {"user_question": user_question}
        result = await tool_fn.ainvoke(tool_input)
        return result
    except Exception as e:
        traceback.print_exc()
        return {"error": f"Error calling tool {tool_name}: {e}"}

async def get_ran_qa_tools():
    vendor_tool = await get_mcp_vendor_tools()
    print(vendor_tool)
    if len(vendor_tool) >0:
        wrapper_tools = [fetch_ran_config, fetch_gpl_values, gpl_audit_misalignment_params_tool,vendor_tool[0]]
    else:
        wrapper_tools = [fetch_ran_config, fetch_gpl_values, gpl_audit_misalignment_params_tool]
    return wrapper_tools



def get_tool_description(fn):
    """
    Extract meaningful tool description from various sources.
    """
    # Method 1: Try to get from LangChain tool attributes
    if hasattr(fn, 'description') and fn.description:
        return fn.description

    # Method 2: Try to get from tool metadata
    if hasattr(fn, 'metadata') and fn.metadata:
        if isinstance(fn.metadata, dict) and 'description' in fn.metadata:
            return fn.metadata['description']

    # Method 3: Try to get from function docstring
    docstring = inspect.getdoc(fn)
    if docstring and docstring != "Tool that can operate on any number of inputs.":
        return docstring

import asyncio
from typing import Optional

async def mavenir_classify_table(prompt: str) -> Optional[str]:
    """
    Asynchronously classifies the appropriate database table for a given question using a language model.

    Args:
        prompt (str): The user's question about antenna or cell data.
        chat_model: The async-compatible language model with an `ainvoke` method.

    Returns:
        Optional[str]: The name of the classified table or None if classification fails.
    """
    classifier_prompt = f"""
You are a database query assistant tasked with identifying the appropriate database table to query based on the user's question. You have two tables to choose from:

1. **dl_silver_ran_mavenir_piiprod.mcms_cm_ret_state_12hr**
   - **Description**: Stores comprehensive antenna Remote Electrical Tilt (RET) configuration states, updated every 12 hours, for vendor Mavenir. Includes detailed antenna metadata (e.g., frequency bands, serial numbers, installation details), operator fields (e.g., antenna bearing, installer ID), and network infrastructure data (e.g., RU IDs, IP addresses).
   - **Use When**: The question involves antenna-specific details (e.g., serial numbers, frequency bands, installation dates, installer IDs, device types), site-based queries with `ru-label` (format: SITENAME_BAND_SECTOR), or named/numeric sector queries (e.g., ALPHA, BETA, GAMMA or _1, _2, _3).

2. **DISH_MNO_OUTBOUND.GENAI_APP.MCMS_CM_RET_STATE**
   - **Description**: Stores RET state information for 5G NR and LTE cells, focusing on tilt settings (tilt, minimumtilt, maximumtilt), equipment IDs (ruid, antennamodel), and communication parameters (ip, hdlc_address, port). Uses `cellname` (format: SITENAME_SECTOR_BAND_ADDITIONAL) and includes Area of Interest (aoi) for geographical context.
   - **Use When**: The question focuses on cell-specific RET settings (e.g., tilt values for a specific cell, site), band-specific queries (e.g., n71, n41), or queries involving `cellname` or `aoi`.

**Classification Criteria:**
- Choose `dl_silver_ran_mavenir_piiprod.mcms_cm_ret_state_12hr` if the question:
  - Mentions antenna serial numbers, frequency bands, installation details (e.g., date, installer), or device metadata (e.g., device type, hardware/software version).
  - References `ru-label` or site-specific queries with named sectors specifically mentioned like (ALPHA, BETA, GAMMA).
  - Involves operational or infrastructure details (e.g., RU IDs, cluster, file name).
- Choose `DISH_MNO_OUTBOUND.GENAI_APP.MCMS_CM_RET_STATE` if the question:
  - References `cellname`, `site with sector 1,2,3 etc`(format: SITENAME_SECTOR_BAND_ADDITIONAL, e.g.,CVCLE00375A (site), CVCLE00375A_1 (site with sector),  CVCLE00375A_1_n71_F-G (cell)).
  - Focuses on tilt settings for specific cells or bands (e.g., n71, n41).
  - Mentions Area of Interest (aoi) or communication parameters (e.g., ip, hdlc_address, port).
  - Does not require installation or detailed antenna metadata.

**Examples:**

1. **Question:** "What is the maximum and minimum tilt supported by antenna with serial number MX086652122124473?"
   **Table:**  `dl_silver_ran_mavenir_piiprod.mcms_cm_ret_state_12hr`

2. **Question:** "What is the current tilt value for site  CVCLE00375A_1_n71_F-G for vendor Mavenir?"
   **Table:** `DISH_MNO_OUTBOUND.GENAI_APP.MCMS_CM_RET_STATE`

3. **Question:** "What is the system type of the antenna model MX0866521402AR1?"
   **Table:** `dl_silver_ran_mavenir_piiprod.mcms_cm_ret_state_12hr`

4. **Question:** "What are the tilt range capabilities for antenna model FFVV-65B-R2?"
   **Table:** `DISH_MNO_OUTBOUND.GENAI_APP.MCMS_CM_RET_STATE`

5. **Question:** "When was the antenna installed with serial number MX086652122127428?"
   **Table:** `dl_silver_ran_mavenir_piiprod.mcms_cm_ret_state_12hr`

**Now, for the following question, identify the appropriate table based on the classification criteria:**

**Question:** {prompt}

**Table:**
"""
    # Prepare the message for the language model
    messages = [{"role": "user", "content": classifier_prompt}]

    # Call the async invoke method of the chat model
    try:
        response = await chatmodel_mistral_medium_ran_2.ainvoke(messages)
        # Assuming the response contains the table name under the "Table:" heading
        response_text = response.content if hasattr(response, 'content') else str(response)

        table_name = extract_first_table_name(response_text)
        logger.info(f"Table name Extracted :: {table_name}")

        if "dl_silver_ran_mavenir_piiprod" in table_name:
            return "Athena"
        else:
            return "SnowFlake"
    except Exception as e:
        print(f"Error invoking chat model: {e}")
        return "SnowFlake"

async def samsung_classify_table(prompt: str) -> Optional[str]:
    """
    Asynchronously classifies the appropriate database table for a given question about Samsung vendor data
    using a language model with 'contains' logic for keyword matching.

    Args:
        prompt (str): The user's question about antenna or cell data.
        chat_model: The async-compatible language model with an `ainvoke` method.

    Returns:
        Optional[str]: The name of the classified table or None if classification fails.
    """
    classifier_prompt = f"""
You are a database query assistant tasked with identifying the appropriate database table to query based on the user's question about Samsung vendor data. Use keyword matching with 'contains' logic to classify the table. You have two tables to choose from:

1. **dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d**
   - **Description**: Stores daily comprehensive antenna Remote Electrical Tilt (RET) configurations for Samsung 5G RAN. Includes radio unit info (e.g., ne-id, o-ran-ru-id, operational-mode), software inventory (e.g., build-version, active status), and detailed RET settings (e.g., current-tilt, antenna-serial-number, installation-date, vendor-code).
   - **Select When**: The question contains keywords like 'serial number', 'installation', 'installer', 'device type', 'operational mode', 'software', 'vendor code', 'ne-id', 'ru-id', 'base-station-id', 'ALPHA', 'BETA', or 'GAMMA'.

2. **DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_RET_STATE**
   - **Description**: Stores RET state information for 5G NR and LTE cells, focusing on tilt settings (tilt, minimumtilt, maximumtilt), equipment IDs (ruid, antennamodel, duid, aldid), and communication parameters (usmip). Uses `cellname` (format: SITENAME_SECTOR_BAND_ADDITIONAL) and includes Area of Interest (aoi).
   - **Select When**: The question contains keywords like 'cellname', 'n71', 'n41', 'band', 'aoi', 'tilt setting', 'usmip', 'duid', or 'aldid'.

**Classification Criteria:**
- Choose `dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d` if the question contains:
  - Keywords like 'antenna serial number', 'installation', 'installer', 'device type', 'operational mode', 'software', 'vendor code', 'ne-id', 'ru-id', 'base-station-id', 'ALPHA', 'BETA', or 'GAMMA'.
  - Queries about antenna metadata, installation details, radio unit configurations, or software inventory.
- Choose `DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_RET_STATE` if the question contains:
  - Keywords like 'cellname', 'site' ,'n71', 'n41', 'band', 'aoi', 'tilt setting', 'usmip', 'duid', or 'aldid'.
  - Queries about cell-specific tilt settings, band-specific data (e.g., n71, n41), or geographical AOI data.
- If the question contains keywords for both tables, prioritize `DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_RET_STATE` for cell-specific or band-specific queries, and `dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d` for antenna metadata or infrastructure queries.

**Examples:**

1. **Question**: "What is the maximum and minimum tilt supported by antenna with serial number MX086652122150754?"
   **Output**: dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d

2. **Question**: "What is the current tilt value for site ATATL00001B_1_n29_E_DL and HOHOU00012A for vendor Samsung?"
   **Output**: DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_RET_STATE

3. **Question**: "What is the system type of the antenna model MX0866521402AR1?"
   **Output**: dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d

4. **Question**: "What are the tilt range capabilities for antenna model FFVV-65B-R2?"
   **Output**: DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_RET_STATE

5. **Question**: "When was the antenna installed with serial number MX086652122150754?"
   **Output**: dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d

6. **Question**: "What are the RET configurations for Alpha sector at site CVPIT for vendor Samsung?"
   **Output**: dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d

7. **Question**: "What are the RET configurations for band n71 at site CHCHI?"
   **Output**: DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_RET_STATE

8. **Question**: "What is the vendor code for software slots with build-version 3121?"
   **Output**: dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d

9. **Question**: "What is the operational mode for RU-ID 341192913?"
    **Output**: dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d

**Now, for the following question, identify the appropriate table using 'contains' logic and output only the table name:**

**Question:** {prompt}
"""
    # Prepare the message for the language model
    messages = [{"role": "user", "content": classifier_prompt}]

    # Call the async invoke method of the chat model
    try:
        response = await chatmodel_mistral_medium_ran_2.ainvoke(messages)
        # Extract the response content
        response_text = response.content if hasattr(response, 'content') else str(response)

        table_name = extract_first_table_name(response_text)
        logger.info(f"Table name Extracted :: {table_name}")

        if "dl_silver_ran_samsung_piiprod" in table_name:
            return "Athena"
        else:
            return "SnowFlake"
    except Exception as e:
        print(f"Error invoking chat model: {e}")
        return "SnowFlake"


def extract_first_table_name(text: str) -> Optional[str]:
    """
    Robust extraction of the first table name from text.
    Handles various database naming conventions and edge cases.
    """
    if not text or not isinstance(text, str):
        return None

    # Updated pattern to be more flexible and accurate
    # Matches: schema.table or database.schema.table formats
    patterns = [
        # Three-part names: database.schema.table
        r"\b(dl_silver_ran_\w+|DISH_MNO_OUTBOUND)\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\b",
        # Two-part names: schema.table (fallback)
        r"\b(dl_silver_ran_\w+|DISH_MNO_OUTBOUND)\.([a-zA-Z0-9_]+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return None

def extract_tool_name(text: str) -> Optional[str]:
    """
    Robust extraction of the first table name from text and maps it to a tool.
    Handles various database naming conventions and edge cases.
    Returns the tool name associated with the table using substring matching.
    """
    if not text or not isinstance(text, str):
        return None

    # Extract table name using existing patterns
    table_name = None
    patterns = [
        # Three-part names: database.schema.table
        r"\b(dl_silver_ran_\w+|DISH_MNO_OUTBOUND)\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\b",
        # Two-part names: schema.table
        r"\b(dl_silver_ran_\w+|DISH_MNO_OUTBOUND)\.([a-zA-Z0-9_]+)\b",
        # Single-part table names (mcms_cm_* format)
        r"\b(mcms_cm_[a-zA-Z0-9_]+)\b",
        # Single-part table names (usm_cm_* format)
        r"\b(usm_cm_[a-zA-Z0-9_]+)\b"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            table_name = match.group(0)
            break

    if not table_name:
        return None

    # Get base table name (without schema prefixes) and convert to lowercase
    base_table_name = table_name.split('.')[-1].lower()

    # Table to tool mapping dictionary (tool names to be filled later)
    table_to_tool_mapping = {
        "mcms_cm_ret_state_12hr": "fetch_mavenir_ret_config",
        "mcms_cm_topology_state_cucp_12hr": "fetch_mavenir_cucp_config",
        "mcms_cm_topology_state_cuup_12hr": "fetch_mavenir_cuup_config",
        "mcms_cm_topology_state_du_12hr": "fetch_mavenir_du_config",
        "mcms_cm_topology_state_rru_12hr": "fetch_mavenir_rru_config",
        "mcms_cm_config_combined_12hr": "fetch_mavenir_cm_config_vendor_combined",
        "usm_cm_ret_state_1d": "fetch_samsung_ret_config",
        "usm_cm_config_cucp_1d": "fetch_samsung_cucp_config",
        "usm_cm_config_du_1d": "fetch_samsung_du_config",
        "usm_cm_config_cucp_parameters": "usm_cm_config_cucp_parameters_tool"
    }

    # Find matching tool using substring matching
    for table_key, tool_name in table_to_tool_mapping.items():
        # Convert dictionary key to lowercase for case-insensitive comparison
        table_key_lower = table_key.lower()

        # Check if the base table name contains the key or vice versa
        if (base_table_name in table_key_lower) or (table_key_lower in base_table_name):
            return tool_name

    return None