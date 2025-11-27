import os
from langchain_core.tools import tool
from typing import Annotated, Dict, List
from dotenv import load_dotenv
import traceback
import logging
from utils import constants as CONST
from prompts.ran2_qa.ran_sql_prompts_v2 import (
    mcms_cm_ret_state_12hr_prompt,
    mcms_cm_topology_state_du_12hr_prompt,
    mcms_cm_topology_state_cuup_12hr_prompt,
    mcms_cm_topology_state_cucp_12hr_prompt,
    mcms_cm_topology_state_rru_12hr_prompt,
    table_name_gpl_1_prompt_mistral, table_name_gpl_2_prompt_mistral, table_name_gpl_3_prompt_mistral,
    table_name_gpl_4_prompt_mistral, table_name_gpl_5_prompt_mistral, table_name_gpl_6_prompt_mistral,
    usm_cm_config_cucp_1d_prompt, usm_cm_config_du_1d_prompt, usm_cm_ret_state_1d_prompt,
    # table_name_gpl_1_prompt_mistral_misaligned_params, table_identify_misaligned_params,
    gpl_misalignment_prompt_v2,usm_cm_config_cucp_parameters_template, mcms_cm_ret_state_prompt, usm_cm_ret_state_prompt
)
from utils.logger import logger
from utils.ran2_qa.ran_sql_athena_utils import query_athena_db, query_athena_db_async
from utils.ran2_qa.ran_sql_postgres_utils import query_postgres_db
from utils.ran2_qa.ran_snow_agent_utils import query_snow_db
# from utils.ran2_qa.ran_sql_postgres_utils import query_postgres_db as query_athena_db # used for testing locally
from llms.ran2_qa.ran_part_two_llms import llm_ran_text_to_sql, llm_ran_text_to_sql_misalignment,llm_ran_text_to_sql_cucp
from utils.query_decomposition import process_user_query
try:
    WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL = os.environ['WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL']
    WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL_PARAMS = os.environ['WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL_PARAMS']
    WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA = os.environ['WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA']
    WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA_PARAMS = os.environ['WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA_PARAMS']
    WATSONX_PROJECT_ID = os.environ['WATSONX_PROJECT_ID']
    WATSONX_URL= os.environ['WATSONX_URL']
    WATSONX_API_KEY=os.environ['WATSONX_API_KEY']
    mcms_cm_topology_state_du_12hr_sub_id=os.environ['mcms_cm_topology_state_du_12hr_sub_id']
    mcms_cm_ret_state_12hr_sub_id=os.environ['mcms_cm_ret_state_12hr']
    mcms_cm_topology_state_cuup_12hr_sub_id=os.environ['mcms_cm_topology_state_cuup_12hr']
    mcms_cm_topology_state_cucp_12hr_sub_id=os.environ['mcms_cm_topology_state_cucp_12hr']
    mcms_cm_topology_state_rru_12hr_sub_id=os.environ['mcms_cm_topology_state_rru_12hr']
    usm_cm_config_cucp_1d_sub_id=os.environ['usm_cm_config_cucp_1d']
    usm_cm_config_du_1d_sub_id=os.environ['usm_cm_config_du_1d']
    table_name_gpl_1_sub_id=os.environ['table_name_gpl_1']
    table_name_gpl_2_sub_id=os.environ['table_name_gpl_2']
    table_name_gpl_3_sub_id=os.environ['table_name_gpl_3']
    table_name_gpl_4_sub_id=os.environ['table_name_gpl_4']
    table_name_gpl_5_sub_id=os.environ['table_name_gpl_5']
    table_name_gpl_6_sub_id=os.environ['table_name_gpl_6']
    usm_cm_ret_state_1d_sub_id=os.environ['usm_cm_ret_state_1d']

except Exception as e:
    print(e)
    load_dotenv()
    print("Loading Environmment Variables from local .env file")
    WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL = os.environ['WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL']
    WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL_PARAMS = os.environ['WATSONX_MODEL_ID_TEXT_TO_SQL_MISTRAL_PARAMS']
    WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA = os.environ['WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA']
    WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA_PARAMS = os.environ['WATSONX_MODEL_ID_TEXT_TO_SQL_LLAMA_PARAMS']
    WATSONX_PROJECT_ID = os.environ['WATSONX_PROJECT_ID']
    WATSONX_URL= os.environ['WATSONX_URL']
    WATSONX_API_KEY=os.environ['WATSONX_API_KEY']
    mcms_cm_topology_state_du_12hr_sub_id=os.environ['mcms_cm_topology_state_du_12hr_sub_id']
    mcms_cm_ret_state_12hr_sub_id=os.environ['mcms_cm_ret_state_12hr']
    mcms_cm_topology_state_cuup_12hr_sub_id=os.environ['mcms_cm_topology_state_cuup_12hr']
    mcms_cm_topology_state_cucp_12hr_sub_id=os.environ['mcms_cm_topology_state_cucp_12hr']
    mcms_cm_topology_state_rru_12hr_sub_id=os.environ['mcms_cm_topology_state_rru_12hr']
    usm_cm_config_cucp_1d_sub_id=os.environ['usm_cm_config_cucp_1d']
    usm_cm_config_du_1d_sub_id=os.environ['usm_cm_config_du_1d']
    table_name_gpl_1_sub_id=os.environ['table_name_gpl_1']
    table_name_gpl_2_sub_id=os.environ['table_name_gpl_2']
    table_name_gpl_3_sub_id=os.environ['table_name_gpl_3']
    table_name_gpl_4_sub_id=os.environ['table_name_gpl_4']
    table_name_gpl_5_sub_id=os.environ['table_name_gpl_5']
    table_name_gpl_6_sub_id=os.environ['table_name_gpl_6']
    usm_cm_ret_state_1d_sub_id=os.environ['usm_cm_ret_state_1d']

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

####### TOOLS - ATHENA #######
# for table mcms_cm_ret_state_12hr
@tool("athena_mcms_cm_ret_state_12hr")
async def athena_mcms_cm_ret_state_12hr(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **2‑hourly snapshots of Antenna RET (Remote Electrical Tilt) state**
    from the `dl_silver_ran_mavenir_piiprod.mcms_cm_ret_state_12hr` table.

    ────────────────────────────────────────────────────────────────
    📌 Core Parameter Families
    ────────────────────────────────────────────────────────────────
    • **Antenna Specification**
      - `antenna-fields.antenna-model-number`
      - `antenna-fields.antenna-serial-number`
      - `antenna-fields.frequency-band`
      - `antenna-fields.tilt-value`, `antenna-fields.max-tilt`, `antenna-fields.min-tilt`

    • **Site / Sector Context**
      - `ru-label`  (SITENAME_BAND_SECTOR, e.g. `CVCLE00435A_MB_2`)
      - `operator-fields.sector-id`(ALPHA,BETA,GAMMA …)
      - `du-id`, `ru-id`, `ru-ip-address`

    • **Operational & Install**
      - `operator-fields.installation-date`, `operator-fields.antenna-bearing`
      - `recent-command-status`, `info.software-version`, `info.vendor-code`

    • **Metadata / Partitioning**
      - `timestamp`, `cluster`, `file_name`
      - `dl_year`, `dl_month`, `dl_day`, `dl_hour`

    ────────────────────────────────────────────────────────────────
    🔍 Query Construction Rules
    ────────────────────────────────────────────────────────────────
    1. **NULL / Blank Filtering** – Every selected `VARCHAR`
       **must** include `NULLIF(col,'')IS NOT NULL` in `WHERE`.

    2. **Sector Logic**
       • Numeric sectors → filter on `ru-label` with `_1`, `_2`, `_3`.
       • Named sectors (ALPHA/BETA/GAMMA) → filter on `operator-fields.sector-id`.
       • Comprehensive searches check **both** fields.

    3. **Case‑Insensitive Matching** – Use `LIKE '%VAL%'`
       on model / serial / site / sector / band / ids.

    4. **Partition Push‑Down** – If the user provides a date,
       apply `dl_year=<yr> AND dl_month=<mo> [AND dl_day=<day>]`;
       default to the current partition (2025/6).

    5. **Latest Snapshot** – For “latest / most recent” requests,
       append `ORDER BY timestampDESC LIMIT 1`.

    6. **LIMIT** – Return `LIMIT 10` rows by default,
       `LIMIT 1` for exact‑match queries.

    7. **Single SQL Only** – The generated SQL must **start with** `SELECT`
       and **end with** `;`.

    ────────────────────────────────────────────────────────────────
    💬 When to Invoke
    ────────────────────────────────────────────────────────────────
    ▸ User asks about antenna model, serial, frequency band, or tilt values.
    ▸ Queries that locate RET settings by `du-id`, site, sector, or vendor.
    ▸ Investigations comparing max/min tilt, installation dates, or alarm/status.

    Example user prompts
    ––––––––––––––––––––
    • “What frequency bands does model MX0866521402AR1 support?”
    • “Show current tilt for serial MX086652122139259.”
    • “Give me all BETA sectors at site CVCLE00435A.”
    • “Find antennas where tilt >80 % of max.”
    • “List RET settings for DU 515006012.”

    ────────────────────────────────────────────────────────────────
    📤 Response Payload
    ────────────────────────────────────────────────────────────────
    ```json
    {
      "user_question": "<original question>",
      "response": "<SQL query or error message>"
    }
    Note: ℹ️ After the SQL executes, display unique result rows to the user in a Markdown table.
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_ret_state_12hr_prompt, mcms_cm_ret_state_12hr_sub_id)
        # Fetch SQL query results
        sql_result =await query_athena_db_async(sql_query)
        # logger.info(f"Generated SQL Query: {sql_query}")
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        logger.error(f"Error in athena_mcms_cm_ret_state_12hr: {e}")
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }



# for table mcms_cm_topology_state_cucp_12hr
@tool("athena_mcms_cm_topology_state_cucp_12hr")
async def athena_mcms_cm_topology_state_cucp_12hr(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **CUCP topology‑state snapshots (12‑hour)** for the
    **Mavenir** network from the
    `dl_silver_ran_mavenir_piiprod.mcms_cm_topology_state_cucp_12hr` table.

    ────────────────────────────────────────────────────────────────
    📌 Core Parameters Supported:
    ────────────────────────────────────────────────────────────────
    • Administrative / Operational – `admin_state`, `operational_state`
    • Alarm Metrics – `alarm_count`, `alarm_severity`
    • Connectivity – `linkstatus`
    • Software & Versioning – `swversion`
    • Identification – `cnfname`, `cucp_id`, `name`, `gnbid`
    • Timestamp / Partitions – `timestamp`, `dl_year`, `dl_month`, `dl_day`, `dl_hour`

    ────────────────────────────────────────────────────────────────
    🔍 Query Construction Rules (must follow):
    ────────────────────────────────────────────────────────────────
    1. **NULL Handling** – Always wrap potentially‑null columns with `COALESCE` in SELECT and conditions.
    2. **Case‑Insensitive Matching** – Use `ILIKE '%val%'`; for state comparisons use
       `LOWER(COALESCE("admin_state", '')) = 'unlocked'`, etc.
    3. **Latest Data** – Use `ORDER BY "timestamp" DESC` when caller asks for “latest/most recent”.
    4. **Default LIMIT** – 5 rows unless user requests otherwise.
    5. **Return Only One SQL** – Must start with `SELECT` and terminate with `;`.

    ────────────────────────────────────────────────────────────────
    💬 When to Invoke This Tool:
    ────────────────────────────────────────────────────────────────
    ▸ User asks about CUCP *admin state*, *alarm count*, *operational state*,
      *software version*, *linkstatus*, or general CUCP health/status for Mavenir.
    ▸ Example questions:
        • “What is the operational state of CUCP with name JKRLA627035000?”
        • “How many CUCPs report SEVE_MAJOR alarms?”
        • “List CUCPs that have been down in the last 24 hours.”

    ────────────────────────────────────────────────────────────────
    📤 Response Payload:
    ────────────────────────────────────────────────────────────────
    Returns a dict:
      { "user_question": <original>, "response": <SQL‑or‑error> }
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_topology_state_cucp_12hr_prompt, mcms_cm_topology_state_cucp_12hr_sub_id)
        # Fetch SQL query results
        sql_result = await query_athena_db_async(sql_query)
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }


# for table mcms_cm_topology_state_cuup_12hr
@tool("athena_mcms_cm_topology_state_cuup_12hr")
async def athena_mcms_cm_topology_state_cuup_12hr(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **12‑hourly snapshots of CUUP (Centralized Unit User Plane) topology state**
    from the `dl_silver_ran_mavenir_piiprod.mcms_cm_topology_state_cuup_12hr` table.

    ────────────────────────────────────────────────────────────────
    📌 Core Parameter Families
    ────────────────────────────────────────────────────────────────
    • **Health & Alarms**
      - `admin_state`, `operational_state`
      - `alarm_count`, `alarm_severity`, `linkstatus`

    • **Topology & Software**
      - `cuup_id`, `cucp_id`
      - `swversion`, `cluster`, `type`

    • **Metadata / Partitioning**
      - `timestamp`, `file_name`, `file_size`
      - `dl_year`, `dl_month`, `dl_day`, `dl_hour`

    ────────────────────────────────────────────────────────────────
    🔍 Query Construction Rules
    ────────────────────────────────────────────────────────────────
    1. **NULL / Blank Filtering** – Every selected `VARCHAR` **must** include
       `NULLIF(column,'') IS NOT NULL` in the `WHERE` clause.

    2. **Case‑Insensitive Matching** – Use `LIKE '%VAL%'` (or `ILIKE` if available)
       on `cuup_id`, `cucp_id`, `name`, `alarm_severity`, `swversion`, `linkstatus`.

    3. **Partition Push‑Down** – If the user specifies year / month (and optionally day),
       apply `dl_year=<year> AND dl_month=<month> [AND dl_day=<day>]`;
       otherwise default to `2025 / 6`.

    4. **Latest Snapshot** – When the user requests “latest”, append
       `ORDER BY timestamp DESC LIMIT 1`.

    5. **LIMIT** – Return `LIMIT 10` rows by default; use `LIMIT 1` for exact‑match queries
       (e.g., a single `cuup_id`).

    6. **Single SQL Only** – The generated SQL must start with `SELECT` and end with `;`.

    ────────────────────────────────────────────────────────────────
    💬 When to Invoke
    ────────────────────────────────────────────────────────────────
    ▸ The user asks about CUUP status, alarms, software version, or connectivity.
    ▸ Typical intents include:
        • Checking administrative / operational state of a CUUP
        • Counting or listing alarms by CUUP, CUCP, or cluster
        • Retrieving CUUP software versions or link status details
        • Mapping CUUPs to a given CUCP or to a geographic region

    ▸ Example user prompts:
        • “What is the operational state of CUUP 123003001?”
        • “List CUUPs under CUCP 545025000 with critical alarms.”
        • “Show software versions for CUUPs in cluster mv‑ndc‑eks‑cluster‑prod‑use2n002p1‑07.”
        • “Give me alarm counts for CUUPs in Columbus region (CMH).”
        • “Which CUUPs have link_down issues in the past 48 hours?”

    ────────────────────────────────────────────────────────────────
    📤 Response Payload
    ────────────────────────────────────────────────────────────────
    ```json
    {
      "user_question": "<original question>",
      "response": "<SQL query or error message>"
    }
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_topology_state_cuup_12hr_prompt, mcms_cm_topology_state_cuup_12hr_sub_id)
        # Fetch SQL query results
        sql_result =await query_athena_db_async(sql_query)
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found."
        }
    except Exception as e:
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }


# for table mcms_cm_topology_state_du_12hr
@tool("athena_mcms_cm_topology_state_du_12hr")
async def athena_mcms_cm_topology_state_du_12hr(user_question: str) -> Dict[str, str]:
    """
       Use this tool to query **12‑hourly snapshots of DU (Distributed Unit) topology state**
       from `dl_silver_ran_mavenir_piiprod.mcms_cm_topology_state_du_12hr`.

       ────────────────────────────────────────────────────────────────
       📌 Core Parameter Families
       ────────────────────────────────────────────────────────────────
       • **DU Status & Alarms**
         - `admin_state`, `operational_state`
         - `alarm_count`, `alarm_severity`, `linkstatus`

       • **Mapping & Identity**
         - `cnfname`, `cucp_id`, `du_id`

       • **Software & Topology**
         - `swversion`, `type`, `cluster`

       • **Metadata / Partitioning**
         - `timestamp`, `file_name`, `file_size`
         - `dl_year`, `dl_month`, `dl_day`, `dl_hour`

       ────────────────────────────────────────────────────────────────
       🔍 Query Construction Rules
       ────────────────────────────────────────────────────────────────
       1. **NULL/Blank Filtering** – Every selected VARCHAR column must have
          `NULLIF(col,'') IS NOT NULL` in the `WHERE` clause.
       2. **Case‑Insensitive Matching** – Use `ILIKE '%val%'` for `cnfname`,
          `cucp_id`, `du_id`, `alarm_severity`, and `linkstatus`.
       3. **Partition Push‑Down** – Apply `dl_year=<year>` and `dl_month=<month>`;
          default is 2025/6 if unspecified.
       4. **Time Ordering** – For “latest” queries, use `ORDER BY timestamp DESC LIMIT 1`.
       5. **Default Limits** – Use `LIMIT 10` for general queries, `LIMIT 1` for exact matches.
       6. **Single SQL Statement** – Query must start with `SELECT` and end with `;`.

       ────────────────────────────────────────────────────────────────
       💬 When to Invoke
       ────────────────────────────────────────────────────────────────
       ▸ User asks about:
         - Administrative or operational state of a DU
         - Alarm count or severity for a DU
         - Software version of a DU
         - DU linked to a specific CUCP or CNF name
         - Link status or cluster information for DUs

       ────────────────────────────────────────────────────────────────
       📤 Response Payload
       ────────────────────────────────────────────────────────────────
         ```json
         {
           "user_question": "<original question>",
           "response": "<SQL query results or error>"
         }
         ```
       """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_topology_state_du_12hr_prompt, mcms_cm_topology_state_du_12hr_sub_id)
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
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

# for table mcms_cm_topology_state_rru_12hr
@tool("athena_mcms_cm_topology_state_rru_12hr")
async def athena_mcms_cm_topology_state_rru_12hr(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **12-hourly snapshots of RRU (Remote Radio Unit) topology state**
    from the `dl_silver_ran_mcms_piiprod.mcms_cm_topology_state_rru_12hr` table.

    ────────────────────────────────────────────────────────────────
    📌 Core Parameter Families
    ────────────────────────────────────────────────────────────────
    • **RRU Status / Alarms**
      - `administrativestate`, `operationalstate`
      - `alarmcount`, `alarmseverity`, `linkstatus`

    • **Software & Topology**
      - `swversion`, `topologystatus`, `topologyservingstatus`

    • **Mapping & Location**
      - `rruid`, `duid`, `cucpid`, `sitename`, `sectorid`, `band`

    • **Metadata / Partitioning**
      - `zip_time_stamp`, `dl_year`, `dl_month`, `dl_day`

    ────────────────────────────────────────────────────────────────
    🔍 Query Construction Rules
    ────────────────────────────────────────────────────────────────
    1. **NULL / Blank Filtering** – Every selected `VARCHAR` MUST have
       `NULLIF(col,'') IS NOT NULL` in `WHERE`.
    2. **Case‑Insensitive Matching** – Use `LIKE '%VAL%'` on `sitename`,
       `rruid`, `duid`, `band`, `cucpid`, and `sectorid`.
    3. **Partition Push‑Down** – If the user specifies year/month, apply
       `dl_year=<year> AND dl_month=<month>`; default is 2025/6.
    4. **Latest Data** – If the user asks for "latest" or "recent", use
       `ORDER BY zip_time_stamp DESC LIMIT 1`.
    5. **LIMIT** – Return 10 rows by default; use 1 row for exact-match queries.
    6. **Return One SQL** – Query MUST start with `SELECT` and end with `;`.

    ────────────────────────────────────────────────────────────────
    💬 When to Invoke
    ────────────────────────────────────────────────────────────────
    ▸ User asks about the state, alarm, or version of an RRU.
    ▸ Queries related to:
        • Administrative / operational state of a specific RRU or site
        • Alarm count or severity per RRU or region
        • RRU software version or link status
        • RRU mapped to DU / CUCP / Sector / Band

    ▸ Typical prompts:
        • “Show the operational state of RRU 741023400.”
        • “List RRUs under DU 741025022 with alarms.”
        • “What is the SW version of RRU at site NYNYC351030000?”
        • “Give me alarm count and status for sector 5 in band n71.”
        • “What is the operational & admin state of RRU with name DEDET00243A_LB_1-3LFJC04932S?"

    ────────────────────────────────────────────────────────────────
    📤 Response Payload
    ────────────────────────────────────────────────────────────────
      ```json
      { "user_question": <original>, "response": <SQL or error> }
      ```
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, mcms_cm_topology_state_rru_12hr_prompt, mcms_cm_topology_state_rru_12hr_sub_id)
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
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("athena_usm_cm_config_cucp_1d")
async def athena_usm_cm_config_cucp_1d(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **daily Samsung CUCP (Centralised‑Unit Control‑Plane) configurations** from
    `dl_silver_ran_samsung_piiprod.usm_cm_config_cucp_1d`.

    ────────────────────────────────────────────────────────────────
    📌 Core Parameter Families
    ────────────────────────────────────────────────────────────────
    • **CU‑Level State**
      - `cu.administrative-state` (unlocked / locked)
      - `cu.operational-state`   (enabled / disabled)
      - `cu.operational-mode`, `cu.cu-reparenting`, `cu.system-type`, `cu.user-label`

    • **Cell Entries** *(prefix `gutran-cu-cell-entries.*`)*
      - `cell-identity`, `f1-gnb-du-id`, DSS flag, disaster‑recovery flag, UL coverage, pre‑emption, UL primary‑path mode

    • **Served‑Cell Info** *(prefix `served-cell-info.*`)*
      - DL / UL ARFCN, NR band, SCS DL/UL, NRB DL/UL, physical‑cell‑ID, TAC, service‑state

    • **Metadata / Partitioning**
      - `region`, `zip_time_stamp`, `xml_time_stamp`, `dl_year`, `dl_month`, `dl_day`

    ────────────────────────────────────────────────────────────────
    🔍 Query Construction Rules
    ────────────────────────────────────────────────────────────────
    1. **NULL / Blank Filtering** – Every selected `VARCHAR` MUST have
       `NULLIF(col,'') IS NOT NULL` in `WHERE`.
    2. **Case‑Insensitive Pattern Matching** – Use `LIKE '%VAL%'` on
       `cu.user-label` (site), region, NR band, or `gutran-cu-cell-entries.object` path.
    3. **Band Keywords** – Map *Mid‑band* → NR bands 66 / 70, *Low‑band* → 71.
    4. **Partition Push‑Down** – If the user supplies year/month, add
       `dl_year=<year> AND dl_month=<month>`; else default to 2025/6.
    5. **Latest Data** – Use `ORDER BY "zip_time_stamp" DESC` if user asks for
       “latest / most recent”.
    6. **LIMIT** – 10 rows by default; 1 for highly specific queries.
    7. **Return One SQL** – Must start with `SELECT` and end with `;`.

    ────────────────────────────────────────────────────────────────
    💬 When to Invoke
    ────────────────────────────────────────────────────────────────
    ▸ User asks about CUCP admin / operational state, CU system‑type, band‑level
      cell details, TAC, resource blocks, or F1‑GNBDU mappings.
    ▸ Typical prompts:
        • “What is the administrative state of CUCP LSSNA741025000?”
        • “List in‑service n71 cells in region USE1.”
        • “Show cells mapped to DU 741025022.”
        • “What is the administrative state of CUCP for site NYNYC351030000?"

    ────────────────────────────────────────────────────────────────
    📤 Response Payload
    ────────────────────────────────────────────────────────────────
      ```json
      { "user_question": <original>, "response": <SQL or error> }
      ```
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, usm_cm_config_cucp_1d_prompt, usm_cm_config_cucp_1d_sub_id)
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
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("athena_usm_cm_config_du_1d")
async def athena_usm_cm_config_du_1d(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **daily Distributed‑Unit (DU) configuration** for
    **Samsung 5G RAN** from
    `dl_silver_ran_samsung_piiprod.usm_cm_config_du_1d`.

    ────────────────────────────────────────────────────────────────
    📌 Core Parameter Families
    ────────────────────────────────────────────────────────────────
    • **DU‑Level State**
      - `du.administrative-state`  (unlocked / locked)
      - `du.du-reparenting`        (boolean)
      - `du.operational-mode`
      - `du.user-label`            (site identifier)
      - `ne-id`, `ne-type`

    • **Cell‑Level Config** *(prefix `gutran-du-cell-entries.*`)*
      - `administrative-state`, `auto-unlock-flag`, `cell-identity`, `user-label`
      - Sub‑carrier spacing (`dl/ul`), `power`, `cell-num`, `cell-path-type`

    • **Access Control** *(prefix `cell-access-info.*`)*
      - Barred / reserved flags, TAC / RAC values, reselection flags

    • **Physical Layer** *(prefix `cell-physical-conf-idle.*`)*
      - DL/UL ARFCN, bandwidth, PCI, `sdl-support`

    • **Metadata / Partitioning**
      - `region`, `zip_time_stamp`, `xml_time_stamp`, `dl_year`, `dl_month`, `dl_day`

    ────────────────────────────────────────────────────────────────
    🔍 Query Construction Rules
    ────────────────────────────────────────────────────────────────
    1. **NULL / Blank Filtering** – Every selected `VARCHAR` **must** have
       `NULLIF(col,'') IS NOT NULL` in `WHERE`.
    2. **Case‑Insensitive Matching** – Use `LIKE` or `ILIKE` patterns on
       `du.user-label`, `gutran-du-cell-entries.user-label`, bands (e.g. `%N66%`).
    3. **Partition Pushdown** – If user provides year/month, use
       `dl_year = <year>` AND `dl_month = <month>`; else default to 2025/6.
    4. **Latest Data** – Use `ORDER BY "zip_time_stamp" DESC` when the user asks
       for “latest” or “recent”.
    5. **Default LIMIT** – 10 rows unless the user specifies otherwise.
    6. **Return Exactly One SQL** – Must start with `SELECT` and end with `;`.

    ────────────────────────────────────────────────────────────────
    💬 When to Invoke
    ────────────────────────────────────────────────────────────────
    ▸ User asks about DU administrative state, re‑parenting, operational mode,
      or any cell/ARFCN/band/power configuration for Samsung DU.
    ▸ Typical prompts:
        • “What is the administrative state of DU PHPHL00606A?”
        • “Show cell parameters for cell‑identity 541.”
        • “Which DU cells use band N71 in region USE1?”
        • “List cells with power > 45 dBm.”
        • “What is the du operational mode of CUCP with user label NAMEM00184A?”

    ────────────────────────────────────────────────────────────────
    📤 Response Payload
    ────────────────────────────────────────────────────────────────
      ```json
      { "user_question": <original>, "response": <SQL or error> }
      ```
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, usm_cm_config_du_1d_prompt, usm_cm_config_du_1d_sub_id)
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
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("athena_usm_cm_ret_state_1d")
async def athena_usm_cm_ret_state_1d(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **daily Samsung antenna RET configurations** from
    `dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d`.

    ────────────────────────────────────────────────────────────────
    📌 Core Parameter Families
    ────────────────────────────────────────────────────────────────
    • **System / RU Info** – `system-type`, `ne-id`, `o-ran-ru-id`, `user-label`
    • **RET Geometry** – `ret.ret-info.current-tilt`, `maximum-tilt`, `minimum-tilt`,
      `current-antenna-bearing`, `config-tilt`, install dates, sector‑ID, base‑station‑ID
    • **Antenna Identity** – model / serial, vendor code, antenna‑ID
    • **Software Slot** – `software-inventory.software-slot.*` (build, version, active)
    • **Metadata / Partitioning** – `region`, `zip_time_stamp`, `dl_year`, `dl_month`, `dl_day`, `dl_hour`

    ────────────────────────────────────────────────────────────────
    🔍 Query Construction Rules
    ────────────────────────────────────────────────────────────────
    1. **NULL / Blank Filtering** – Every selected `VARCHAR` MUST have
       `NULLIF(col,'') IS NOT NULL` in `WHERE`.
    2. **Pattern Matching** – Use `LIKE` patterns on `user-label` or
       `ret.ret-info.current-base-station-id` for site / sector / band logic
       (Alpha→`_A_`/`ALPHA`, Beta→`_B_`/`BETA`, Gamma→`_C_`/`GAMMA`).
    3. **Sector Mapping** – Alpha≡A, Beta≡B, Gamma≡C; prioritise explicit words
       (BETA) over single‑letter patterns to avoid false matches.
    4. **Band Keywords** – Mid‑band→`%M%` or `%MB%`, Low‑band→`%L%` or `%LOWBAND%`,
       or explicit bands (`%n71%`, `%B2%`). Check both base‑station‑ID and
       `antenna-operating-band`.
    5. **Partition Pushdown** – If the user supplies a year/month, use
       `dl_year=<year>` AND `dl_month=<month>`; otherwise default to 2025/6.
    6. **Ordering** – For latest data, `ORDER BY "zip_time_stamp" DESC`.
    7. **LIMIT** – 10 rows by default; 1 row for specific serial / RU‑ID queries.
    8. **Return One SQL** – Must start with `SELECT` and end with `;`.

    ────────────────────────────────────────────────────────────────
    💬 When to Invoke
    ────────────────────────────────────────────────────────────────
    ▸ User asks about antenna model, tilt (current / max / min / config),
      install date, bearing, system‑type, or vendor/serial info for Samsung RET.
    ▸ Example prompts:
        • “What is the system type of antenna model MX0866521402AR1?”
        • “How many cells in CVG AOI have RET higher than 10?”
        • “Show all Gamma‑sector mid‑band cells at site CVPIT.”
        • “How many cells in CVG AOI have RET higher than 10?, What is the current RET for the cell CVCLE00375A_2_n70_AWS4_UL5 ?"
        • “What is the system type of the antenna model MX0866521402AR1?"

    ────────────────────────────────────────────────────────────────
    📤 Response Payload
    ────────────────────────────────────────────────────────────────
      ```json
      { "user_question": <original>, "response": <SQL or error> }
      ```
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, usm_cm_ret_state_1d_prompt, usm_cm_ret_state_1d_sub_id)
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
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

#### TOOLS - POSTGRES ####
@tool("postgres_table_name_gpl_1_prompt_mistral")
async def postgres_table_name_gpl_1_prompt_mistral(user_question: str) -> Dict[str, str]:
    """
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - GPL refer to Golden Parameters List which refer to a predefined set of key configuration parameters that are critical for the optimal network performance and stability of a network. 
        - The table captures DISH recommended values for the golden parameters. 
        - These parmeters are global values and so are applicable to all SITEs on the network.  
        - param_name column specifies the parameter name 
        - dish_gpl_value column specifies the recommended value by DISH. 
        - hierarchy specifies the hierarchy of the selected parameter name

    Parameters:
        - fsib5
        - param_name
        - hierarchy
        - param_family
        - related_feature_desc_id
        - desc
        - param_type
        - unit
        - range
        - dish_gpl_value
        - real_time_change
        - comments
        - file_name
        - s3_url
        - version
        - vendor

    ***When to use:***
        - Questions about gpl parameters dish_gpl_value, param_name, hierarchy, etc**

        
    Example:
        user_question: "What is the default value Dish has in GPL for the n310 parameter?"
        tool response:
            {
                'user_question': "What is the default value Dish has in GPL for the n310 parameter?",
                'response': <SQL query results>
            }
    Special Examples: when user asks below type of questions make sure to use this tool
    - What is the recommended dish GPL value of n310 parameter of Mavenir vendor?
    - What is the recommended dish GPL value of n310 parameter in Mavenir vendor?
    - What is the description for the parameter zeroCorrelationZoneCfg?

    """
    try:
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
            sql_query = await llm_ran_text_to_sql(sub_q, table_name_gpl_1_prompt_mistral, table_name_gpl_1_sub_id)
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
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("postgres_table_name_gpl_2_prompt_mistral")
async def postgres_table_name_gpl_2_prompt_mistral(user_question: str) -> Dict[str, str]:
    """
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
       * These are the dish gpl parameters for connected mobility
            - Connected mobility means that the state of the device (UE - User Equipment) is in use and is interacting with the network. 
            - Connected mobility parameters are specific to Markets based on available frequency band 
            - These are DISH specified parameters with recommended values and NOT specific to any vendor. 

    Parameters:
        - criteria      
        - cell_num_params
        - a2_threshold_rsrp
        - hysteresis
        - timetoTrigger
        - A3 offset 

    ***When to use:***
        - Questions about gpl parameters for connected mobility  - criteria, \
            cell_num_params, a2_threshold_rsrp, timetoTrigger, hysteresis, A3 offset **
        - Questions like - What is the a5-threshold1-rsrp for n70 in Mavenir and Samsung

    Example:
        user_question: what are the recommended criterias used for the vendor mavenir?
        tool response:
            {
                'user_question': what are the recommended criterias used for the vendor mavenir?,
                'response': <SQL query results>
            }
    """
    try:

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

            # Generate the SQL for this sub-query
            sql_query = await llm_ran_text_to_sql(
                sub_q,
                table_name_gpl_2_prompt_mistral,
                table_name_gpl_2_sub_id
            )
            # Execute against Postgres
            sql_result = await query_postgres_db(sql_query)

            # Append vendor-keyed result
            responses.append({
                "vendor": vendor,
                "sub_query": sub_q,
                "result": sql_result or "No results found."
            })

        # 3) Return combined payload
        return {
            "user_question": user_question,
            "responses": responses
        }
    except Exception as e:
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("postgres_table_name_gpl_3_prompt_mistral")
async def postgres_table_name_gpl_3_prompt_mistral(user_question: str) -> Dict[str, str]:
    """
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
    * There are the dish gpl parameters for idle_mode
        - Idle Mode' means that the state of the device (UE - User Equipment) is NOT in use and is NOT interacting with the network.
        - Idle mode parameters are specific to Markets based on available frequency
        - These are DISH specified parameters with recommended values and NOT specific to any vendor

    Parameters:
        - cellreselectionpriority
        - cellreselectionsubpriority
        - qrxlevmin
        - threshXLowP
        - threshXHighP

    ***When to use:***
        - Questions about gpl parameters for idle_mode  - cellreselectionpriority, cellreselectionsubpriority, \
            qrxlevmin, freqBandIndicatorNR, threshXLowP, threshXHighP**
        - Questions like - What is the cell reselection priority for band n70 in Mavenir and Samsung

    Example:
        user_question: what is the recommended value for CellReselectionPriority for freqBandIndicatorNR n70
        tool response:
            {
                'user_question': "what is the recommended value for CellReselectionPriority for freqBandIndicatorNR n70",
                'response': <SQL query results>
            }
    """
    try:

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
            sql_query = await llm_ran_text_to_sql(sub_q, table_name_gpl_3_prompt_mistral, table_name_gpl_3_sub_id)
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
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("postgres_table_name_gpl_4_prompt_mistral")
async def postgres_table_name_gpl_4_prompt_mistral(user_question: str) -> Dict[str, str]:
    """
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
    * These are the dish gpl parameters for the acme feautres
        - The table captures DISH recommended values for certain Feature specific GPL parameters. 

    Parameters:
        - dish_gpl_value
        - feature
        - config

    ***When to use:***
        - Questions about gpl parameters for acme feautres  - dish_gpl_value, feature, config **

    Example:
        user_question: what is the default gpl value for feature RRC Encryption ?
        tool response:
            {
                'user_question': "what is the default gpl value for feature RRC Encryption ?",
                'response': <SQL query results>
            }
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, table_name_gpl_4_prompt_mistral, table_name_gpl_4_sub_id)
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
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("postgres_table_name_gpl_5_prompt_mistral")
async def postgres_table_name_gpl_5_prompt_mistral(user_question: str) -> Dict[str, str]:
    """
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
    * These are the dish gpl parameters for the mavenir
        - The table captures GPL parameters that are specific to Vendor mavenir. 

    Parameters for Mavenir:
        - param_origin
        - desc
        - param_name

    ***When to use:***
        - Questions about gpl parameters for Mavenir  - param_origin, desc, param_name **

    Example:
        user_question: what is the recommended parma name of param origin cuCpId?
        tool response:
            {
                'user_question': "what is the recommended parma name of param origin cuCpId?",
                'response': <SQL query results>
            }

    Note: Use this Tool only for GPL parameters for Mavenir , And Not For GPL misalignment or Audit related questions
    Note: If No results found. Please check in Global GPL parameters
    """
    try:

        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, table_name_gpl_5_prompt_mistral, table_name_gpl_5_sub_id)
        # Fetch SQL query results
        sql_result = await query_postgres_db(sql_query)
        # Ensure the response format is consistent
        # mcms_cm_config_3gpp_du_12hr_prompt
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found.Please check in Global GPL parameters. Call it only once"
        }
    except Exception as e:
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("postgres_table_name_gpl_6_prompt_mistral")
async def postgres_table_name_gpl_6_prompt_mistral(user_question: str) -> Dict[str, str]:
    """
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
    * These are the dish gpl parameters for the Samsung
        - The table captures GPL parameters that are specific to Vendor Samsung. 

    Parameters for Samsung:
        - param_origin
        - desc
        - param_name

    ***When to use:***
        - Questions about gpl parameters for Samsung  - param_origin, desc, param_name **

    Example:
        user_question: what is the recommended parma name of feature desc id OAMP-CM0102?
        tool response:
            {
                'user_question': "what is the recommended parma name of feature desc id OAMP-CM0102?",
                'response': <SQL query results>
            }

    Note: If No results found. Please check in Global GPL parameters
    """
    try:
        # Generate sql query
        sql_query = await llm_ran_text_to_sql(user_question, table_name_gpl_6_prompt_mistral, table_name_gpl_6_sub_id)
        # Fetch SQL query results
        sql_result = await query_postgres_db(sql_query)
        # Ensure the response format is consistent
        # mcms_cm_config_3gpp_du_12hr_prompt
        # Ensure the response format is consistent
        return {
            'user_question': user_question,
            'response': sql_result or "No results found. Please check in Global GPL parameters. Call it only once"
        }
    except Exception as e:
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

### Fallback
@tool("ran_fallback_messages")
def ran_fallback_messages(user_question: str) -> Dict[str,str]:
    """Use this tool to when user asks questions which are not related to network information. \
        This tool accepts natural language query and generates fallback response AND The tool will return \
        the `user_question` and `response` as dict object. `user_question` will be the user question.

    For example:
    user_question: who is the president of usa?
    
    tool response:
        {
            'user_question': 'who is the president of usa?',
            'response': 'The question is not related to the RAN documents that I have been trained on. Please provide a relevant query and I will be happy to help!"
        }
    """
    ran_status = "The question is not related to the RAN documents that I have been trained on. Please provide a relevant query and I will be happy to help!"
    return {'user_question': user_question, 'response': ran_status}

#### Too handle misalignment type questions
@tool("misalignment_params_tool")
async def misalignment_params_tool(user_question: str) -> Dict[str, str]:
    """
    Use this tool to call when user question involves/related to below Instructions and Special Instructions.
    Make sure to use Markdown table to show large responses from this tool for better user experience.
    But for small responses use *bullet* points.

    Instructions:
        - user questions about parameter misalignments
        - If the tool returns "No misalignments found. <!-- LLM: This is a valid and final response. Do not call the tool again. -->" treat this as a final and correct response. Do NOT call the tool again and other than this if tools responses anything that is also acceptable.
        - if tools response is [{"Misalignments": 1}], then consider this as one of accepted responses and summarize this in user frindly as Total Misalignments found is one

    ### Special Instructions:
        - if user asks questions like this "What misalignments do we have for gapOffset parameter in MCA (AOI)? ", "What misalignments do we have in MCA (AOI)?" \
            make sure to return ask user about the vendor info and acceptable inputs from user's are samsung, mavenir, all. If user provides \
            these vendor inputs then decide that to use in the sql query generation using the defined prompts

    # Sample user questions:
    - What misalignments do we have for gapOffset parameter in MCA (AOI)?... ?
    - What misalignments do we have for gapOffset parameter in MCA (AOI) in mavenir ... ?
    - What misalignments do we have for gapOffset parameter in MCA (AOI)? yesterday...?
    - Can you tell me how long the DUID has been trending inconsistent? ## make sure this is misalignment
    - Can you tell me which 551030000 NRCells deviate from GPL?

    Example:
        user_question: What misalignments do we have for gapOffset parameter in MCA (AOI), mavenir vendor?
        tool response:
            {
                'user_question': "What misalignments do we have for gapOffset parameter in MCA (AOI)?",
                'response': <SQL query results>
            }

    **Note:** Always verify and display the **Audit Date** based on the **current tool response**. Do **not** reuse or carry over the Audit Date from any **previous responses**. Ensure the date accurately reflects the data retrieved in the current execution.
    """
    try:
        # Generate sql query
        sql_query = await llm_ran_text_to_sql_misalignment(user_question, gpl_misalignment_prompt_v2, table_name_gpl_6_sub_id)
        # Fetch SQL query results
        sql_result = await query_postgres_db(sql_query)
        # print("sql_result---->", sql_result)

        # if sql_result in ([], None) or (
        #     isinstance(sql_result, list) and sql_result and sql_result[0].get("count", 1) == 0
        # ):
        #     sql_result  = "No misalignments found. <!-- LLM: This is a valid and final response. Do not call the tool again. -->"

        # else:
        #     sql_result = f'Total misalignments found: {sql_result[0].get("count", None)}.'


        return {
            'user_question': user_question,
            'response': sql_result
        }

    except Exception as e:
        # Return a user-friendly error message
        return {
            'user_question': user_question,
            'response': f"An error occurred while querying the database. -> {e}"
        }

@tool("usm_cm_config_cucp_parameters_tool")
async def usm_cm_config_cucp_parameters_tool(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **Samsung live network configuration parameters** from the
    `USM_CM_CONFIG_CUCP_PARAMETERS` table. This tool is strictly applicable **only for Samsung vendor** data.

    ────────────────────────────────────────────────────────────────
    📌 Parameter Categories Supported:
    ────────────────────────────────────────────────────────────────
    • **Thresholds**
      - RSRP: `threshold_rsrp`, `threshold1_rsrp`, `threshold2_rsrp`
      - RSRQ: `threshold_rsrq`, `threshold1_rsrq`, `threshold2_rsrq`
      - SINR: `threshold_sinr`, `threshold1_sinr`, `threshold2_sinr`

    • **Handover Parameters**
      - `hysteresis`, `time_to_trigger`, `report_type`, `purpose`

    • **Trigger Quantities**
      - `threshold_selection_trigger_quantity`
      - `threshold_selection_trigger_quantity_sinr`

    • **Cell Identification**
      - Site-level, sector-level, CUCP ID, DU ID, gNodeB ID, band-level filtering supported

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
    • “What is the RSRP threshold for cell BOBOS01075F_2_n71_F-G?”
    • “Show me A5 threshold1/threshold2 values for low-band cells.”
    • “What are the handover parameters configured for CUCP ID 331011000?”
    • “Which sectors in site BOBOS01075F are using RSRQ trigger quantity?”

    Note: Agent should show the response from this tool in markdown table response for unique rows only.
    """
    try:
        sql_query: str = await llm_ran_text_to_sql_cucp(
            user_question,
            usm_cm_config_cucp_parameters_template,
            None,  # e.g. "USM_CM_CONFIG_CUCP_PARAMETERS"
        )

        # 2. Run the SQL against Postgres/Athena
        sql_result = await query_snow_db(sql_query)

        # 3. Normalise “no-data” situations so the agent doesn’t loop
        if not sql_result:
            sql_result = (
                "No matching records found. "
                "Please verify in the postgres_table_name_gpl_2_prompt_mistral tool if it has not already been checked.-->"
            )

        # 4. Return a uniform payload (the orchestrator already expects this shape)
        return {
            "user_question": user_question,
            "response": sql_result,
        }

    except Exception as exc:
        # Bubble a user-friendly error back to the agent / UI
        return {
            "user_question": user_question,
            "response": f"An error occurred while querying the database → Please verify in the postgres_table_name_gpl_2_prompt_mistral tool if it has not already been checked.",
        }


@tool("usm_cm_ret_state_tool")
async def usm_cm_ret_state_tool(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **USM RET state information** from the
    `USM_CM_RET_STATE` table in the DISH_MNO_OUTBOUND.GENAI_APP schema.
    This tool is strictly applicable for **Samsung vendor** USM RET data.

    ────────────────────────────────────────────────────────────────
    📌 Parameter Categories Supported:
    ────────────────────────────────────────────────────────────────
    • **Tilt Configuration**
      - `tilt` (current electrical tilt in degrees)
      - `minimumtilt` (minimum allowable tilt)
      - `maximumtilt` (maximum allowable tilt)

    • **Equipment Identifiers**
      - `duid` (Device Unit ID)
      - `aldid` (Antenna Line Device ID)
      - `ruid` (Remote Unit ID)
      - `antennaid` (Antenna identifier within equipment)
      - `antennamodel` (Physical antenna model)

    • **Communication**
      - `usmip` (USM IP address for RET unit)

    • **Geography**
      - `aoi` (Area of Interest code, e.g., BOS, IND, MCO)

    • **Cell Identification**
      - `cellname`: SITENAME_SECTOR_BAND_ADDITIONAL format (e.g., `BOBOS01075F_2_n71_F-G`)

    ────────────────────────────────────────────────────────────────
    🔍 Query Construction Rules:
    ────────────────────────────────────────────────────────────────
    ▸ ONLY applicable to Samsung vendor data; do not use for other vendors.
    ▸ ALWAYS include `NULLIF(column, '') IS NOT NULL` for every column in SELECT.
    ▸ Use `ILIKE '%pattern%'` for case-insensitive matching on `cellname`, `antennamodel`, `ruid`, `duid`, `usmip`, `aoi`.
    ▸ **Site queries**: match `%SITENAME%` (e.g., `%BOBOS01075F%`).
    ▸ **Sector queries**: match `%SITENAME_SECTOR_%` (e.g., `%BOBOS01075F_2_%`).
    ▸ **Band queries**: include `%n##%` or `%B##%` in pattern.
    ▸ For numerical comparisons on tilt, CAST as FLOAT: `CAST(tilt AS FLOAT)`, etc.
    ▸ Always append `LIMIT 10` if no explicit limit is requested.
    ▸ Return only the SQL statement starting with `SELECT` and ending with `;`.

    ────────────────────────────────────────────────────────────────
    💬 Example User Questions:
    ────────────────────────────────────────────────────────────────
    • “What is the current tilt setting for cell BOBOS01075F_2_n71_F-G?”
    • “Show me all RET parameters for site BOBOS01075F.”
    • “What antenna model and USM IP address are configured for RUID 331107512?”
    • “Which cells have tilt at their maximum limit?”
    • “What are the tilt statistics (min, max, avg) by AOI region?”

    ────────────────────────────────────────────────────────────────
    Response:
      Returns a dict with:
        - "user_question": original question
        - "response": generated SQL query or error message
    """
    try:
        # 1. Generate SQL via the shared text-to-SQL LLM function
        sql_query: str = await llm_ran_text_to_sql(
            user_question,
            usm_cm_ret_state_prompt,
            None
        )

        # 2. Execute the SQL against Athena/Postgres
        sql_result = await query_snow_db(sql_query)

        # 3. If no data, stop further tool invocation
        if not sql_result:
            return {
                "user_question": user_question,
                "response": (
                    "No matching records found. "
                    " Please verify in the athena_usm_cm_ret_state_1d tool if it has not already been checked. -->"
                )
            }

        return {
            "user_question": user_question,
            "response": sql_result
        }

    except Exception as exc:
        return {
            "user_question": user_question,
            "response": f"An error occurred while querying the database → Please verify in the athena_usm_cm_ret_state_1d tool if it has not already been checked.",
        }


@tool("mcms_cm_ret_state_tool")
async def mcms_cm_ret_state_tool(user_question: str) -> Dict[str, str]:
    """
    Use this tool to query **MCMs RET state information** from the
    `MCMS_CM_RET_STATE` table in the DISH_MNO_OUTBOUND.GENAI_APP schema.
    This tool is strictly applicable for **Mavenir vendor** RET data.

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
    🔍 Query Construction Rules:
    ────────────────────────────────────────────────────────────────
    ▸ ONLY applicable to Mavenir vendor data; do not use for other vendors.
    ▸ ALWAYS include `NULLIF(column, '') IS NOT NULL` for every column in SELECT.
    ▸ Use `ILIKE '%pattern%'` for case-insensitive matching on `cellname`, `antennamodel`, `ruid`, `ip`, `aoi`.
    ▸ **Site queries**: match `%SITENAME%` (e.g., `%CVCLE00375A%`).
    ▸ **Sector queries**: match `%SITENAME_SECTOR_%` (e.g., `%CVCLE00375A_1_%`).
    ▸ **Band queries**: include `%n##%` or `%B##%` in pattern.
    ▸ For numerical comparisons on tilt, CAST as FLOAT: `CAST(tilt AS FLOAT)`, etc.
    ▸ Always append `LIMIT 10` if no explicit limit is requested.
    ▸ Return only the SQL statement starting with `SELECT` and ending with `;`.

    ────────────────────────────────────────────────────────────────
    💬 Example User Questions:
    ────────────────────────────────────────────────────────────────
    • “What is the current tilt setting for cell CVCLE00375A_1_n71_F-G?”
    • “Show me all RET parameters for site CVCLE00375A.”
    • “What antenna model and IP address are configured for RUID 121037511?”
    • “Which cells have tilt at their maximum limit?”
    • “What are tilt utilization percentages for each cell?”

    ────────────────────────────────────────────────────────────────
    Response:
      Returns a dict with:
        - "user_question": original question
        - "response": generated SQL query or error message
    """
    try:
        sql_query: str = await llm_ran_text_to_sql(
            user_question,
            mcms_cm_ret_state_prompt,
            None
        )
        sql_result = await query_snow_db(sql_query)
        if not sql_result:
            return {"user_question": user_question,
                    "response": (
                        "No records found. "
                        "<!--Please verify in the athena_mcms_cm_ret_state_12hr tool if it has not already been checked. -->"
                    )}
        return {"user_question": user_question, "response": sql_result}
    except Exception as exc:
        return {
            "user_question": user_question,
            "response": f"An error occurred while querying the database → Please verify in the athena_mcms_cm_ret_state_12hr tool if it has not already been checked.",
        }





tools = [
    # network_config
    athena_mcms_cm_ret_state_12hr,
    athena_mcms_cm_topology_state_cucp_12hr,
    athena_mcms_cm_topology_state_cuup_12hr,
    athena_mcms_cm_topology_state_du_12hr,
    athena_mcms_cm_topology_state_rru_12hr,
    athena_usm_cm_config_cucp_1d,
    athena_usm_cm_config_du_1d,
    athena_usm_cm_ret_state_1d,
    postgres_table_name_gpl_1_prompt_mistral, postgres_table_name_gpl_2_prompt_mistral,postgres_table_name_gpl_3_prompt_mistral,
    postgres_table_name_gpl_4_prompt_mistral, postgres_table_name_gpl_5_prompt_mistral, postgres_table_name_gpl_6_prompt_mistral,
    misalignment_params_tool,
    usm_cm_config_cucp_parameters_tool,
    usm_cm_ret_state_tool,
    mcms_cm_ret_state_tool
]
