import os
from langchain_core.tools import tool
from typing import Annotated, Dict, List
from dotenv import load_dotenv
import traceback
import logging
from utils import constants as CONST
from prompts.ran2_qa.ran_sql_prompts import (
                                    mcms_cm_ret_state_12hr_prompt,
                                    mcms_cm_topology_state_du_12hr_prompt,
                                    mcms_cm_topology_state_cuup_12hr_prompt,
                                    mcms_cm_topology_state_cucp_12hr_prompt,
                                    mcms_cm_topology_state_rru_12hr_prompt,
                                    table_name_gpl_1_prompt_mistral, table_name_gpl_2_prompt_mistral, table_name_gpl_3_prompt_mistral,
                                    table_name_gpl_4_prompt_mistral, table_name_gpl_5_prompt_mistral, table_name_gpl_6_prompt_mistral,
                                    usm_cm_config_cucp_1d_prompt, usm_cm_config_du_1d_prompt, usm_cm_ret_state_1d_prompt, 
                                    # table_name_gpl_1_prompt_mistral_misaligned_params, table_identify_misaligned_params,
                                    gpl_misalignment_prompt, gpl_misalignment_prompt_v2,usm_cm_config_cucp_parameters_template
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
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - Stores Antenna RET (Remote Electrical Tilt) configuration states, updated every 2 hours, for vendor Mavenir

    Parameters: these are some of the parameters which will be asked by the user
        - antenna_fields_antenna_model_number
        - antenna_fields_antenna_serial_number
        - antenna_fields_frequency_band
        - antenna_fields_max_tilt
        - antenna_fields_min_tilt
        - antenna_fields_tilt_value
        - du_id

    ***When to use:***
    - Questions about **antenna model numbers, serial numbers, frequency bands, tilt values, max tilt or min tilt**
    - Finding antennas by **du_id**
    - Checking tilt range (max/min)
    - Qusestion like  - Can you show me the baseline threshXHighP and threshXLowP values for NRCells of DUID: 851017009?

    Example:
        user_question: What is the frequency band supported by the antenna model MX0866521402AR1?
        tool response:
            {
                'user_question': "What is the frequency band supported by the antenna model MX0866521402AR1?",
                'response': <SQL query results>
            }

    Note: Agent should show the response from this tool in Markdown table response for unique rows only.
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
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - Stores state of CUCP (Centralized Unit Control Plane) topology, updated every 12 hours, for vendor Mavenir

    Parameters:
        - admin_state
        - alarm_count
        - linkstatus
        - operational_state
        - swversion

    ***When to use:***
    - Questions about **admin state, alarm count, operational status, swversion for CUCP (Centralized Unit Control Plane) **

    Example:
        user_question:  What is the operational state of CUCP with name JKRLA627035000?
        tool response:
            {
                'user_question': "What is the operational state of CUCP with name JKRLA627035000?",
                'response': <SQL query results>
            }
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
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - Stores state of CUUP (Centralized Unit User Plane) topology, updated every 12 hours, for vendor Mavenir 

    Parameters:
        - admin_state
        - alarm_count
        - linkstatus
        - operational_state
        - swversion

    ***When to use:***
    - Questions about **admin state, alarm count, operational status, swversion for CUUP (Centralized Unit User Plane) **

    Example:
        user_question: What is the operational state of CUUP with id 121014100? 
        tool response:
            {
                'user_question': "What is the operational state of CUUP with id 121014100?",
                'response': <SQL query results>
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
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - Stores state of DU (Distributed Unit) topology, updated every 12 hours, for vendor Mavenir

    Parameters:
        - operational_state
        - admin_state
        - alarm_count
        - cucp_id

    ***When to use:***
    - Questions about **admin state, alarm count, operational status, swversion for DU (Distributed Unit) topology **

    Example:
        user_question: What is the operational & admin state of DU with name ATABY511000002? 
        tool response:
            {
                'user_question': "What is the operational & admin state of DU with name ATABY511000002?",
                'response': <SQL query results>
            }
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
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - Stores state of RRU (Remote Radio Unit) topology, updated every 12 hours, for vendor Mavenir 

    Parameters:
        - operational_state
        - admin_state
        - alarm_count
        - swversion
        - ru_id
        - rru_id

    ***When to use:***
    - Questions about **admin state, alarm count, operational status, swversion for RRU (Remote Radio Unit) topology **

    Example:
        user_question: What is the operational & admin state of RRU with name DEDET00243A_LB_1-3LFJC04932S? 
        tool response:
            {
                'user_question': "What is the operational & admin state of RRU with name DEDET00243A_LB_1-3LFJC04932S?",
                'response': <SQL query results>
            }
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
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - Stores RAN configuration details of CUCP (Centralized Unit Control Plane), updated daily, for vendor Samsung 

    Parameters:
        - cu_operational_mode
        - cu_administrative_state
        - ne_type
        - cu_system_type

    ***When to use:***
    - Questions about **cu_operational_mode, cu_administrative_state, ne_type, syste type for CUCP (Centralized Unit Control Plane) topology **

    Example:
        user_question: What is the adminstrative state of CUCP with user label NYNYC351030000?
        tool response:
            {
                'user_question': "What is the adminstrative state of CUCP with user label NYNYC351030000?",
                'response': <SQL query results>
            }
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
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - Stores RAN configuration details of DU (Distributed Unit), updated daily, for vendor Samsung 

    Parameters:
        - du_administrative_state
        - du_du_reparenting
        - du_operational_mode
        - du_user_label

    ***When to use:***
    - Questions about **du_administrative_state, cu_administrative_state, du_operational_mode, du_user_label for DU (Distributed Unit) topology for samsung vendor **

    Example:
        user_question: What is the du operational mode of CUCP with user label NAMEM00184A?
        tool response:
            {
                'user_question': "What is the du operational mode of CUCP with user label NAMEM00184A?",
                'response': <SQL query results>
            }
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
    Use this tool to call when user question involves/related to below table description and parameters.

    Table Description:
        - Stores Antenna RET (Remote Electrical Tilt) configurations, updated daily, for vendor Samsung  

    Parameters:
        - system_type
        - ret_ret_info_maximum_tilt
        - ret_ret_info_minimum_tilt
        - ret_ret_info_current_install_date
        - ret.ret-info.config-tilt

    ***When to use:***
    - Questions about **ret.ret-info.config-tilt, ret_ret_info_maximum_tilt, ret_ret_info_minimum_tilt, ret_ret_info_current_install_date, system type for Antenna RET (Remote Electrical Tilt) configurations **
    - Questions like How many cells in CVG AOI have RET higher than 10?, What is the current RET for the cell CVCLE00375A_2_n70_AWS4_UL5 ?

    Example:
        user_question:  What is the system type of the antenna model MX0866521402AR1?
        tool response:
            {
                'user_question': "What is the system type of the antenna model MX0866521402AR1?",
                'response': <SQL query results>
            }
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
            'response': sql_result or "No results found."
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
            'response': sql_result or "No results found."
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
                "<!-- LLM: This is a valid and final response. Do not call the tool again. -->"
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
            "response": f"An error occurred while querying the database → {exc}",
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
        ran_fallback_messages,
        misalignment_params_tool,
        usm_cm_config_cucp_parameters_tool
    ]
