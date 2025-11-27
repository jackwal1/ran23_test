import traceback
from langchain_core.tools import tool
from utils.log_init import logger
from utils.ran2_qa.ran_snow_agent_utils import query_snow_db
#from utils.ran2_qa.ran_sql_postgres_utils import query_postgres_db
from llms.ran2_qa.ran_part_two_llms import llm_ran_nca_text_to_sql
from prompts.ran_nca_sql_prompts import ran_nca_prompt,ran_nca_device_prompt, ran_customer_order_device_prompt
from utils import constants as CONST


async def queryDb(user_question: str,prompt):
    try:
        # Step 1: Generate SQL using LLM
        logger.info(f"Generating SQL for NCA question: {user_question}")
        sql_query: str = await llm_ran_nca_text_to_sql(user_question,prompt,None)
              
        try:
            # Step 2: Execute the SQL query
            sql_result = await query_snow_db(sql_query)
            
            # Step 3: Check for empty or null results
            if not sql_result or (
                    isinstance(sql_result, list) and all(
                not row or all(v is None for v in row.values())
                for row in sql_result if isinstance(row, dict)
            )
            ):
                raise ValueError("No valid data returned from DB")
        
        except Exception as inner_e:
            logger.error(f"NCA Snowflake failed or returned no data for '{user_question}': {inner_e}. Falling back to NCA tool.")
            sql_result = ''
          
       
        return {
            "nca_data": sql_result
        }
        
    except Exception as e:
        traceback.logger.info_exc()
        logger.info(f"NCA Error for '{user_question}': {e}")
        return {
            "nca_data": "An error occurred while generating the SQL."
        }



@tool("fetch_nca_call_summary_data")
async def fetch_nca_call_summary_data(user_question: str):
    """
    Async function that performs search on Network Call Analyzer (NCA) database table

    Args:
        query (str): Search query text

    Returns:
        str: Formatted search results

    ────────────────────────────────────────────────────────────────
    Example Questions:
    • "Bottom AOIs interms of NCA device count?"
    • "Top AOIs interms of NCA device count?"
    • "Drop call rate per model per AOI?"
    • "Setup fail rate  per model per AOI?"
    • "Drop call rate per Region?"
    • "Setup fail rate per Region?"

    """

    return await queryDb(user_question,ran_nca_prompt)

@tool("fetch_nca_device_data")
async def fetch_nca_device_data(user_question: str):
    """
    Async function that performs search on device_lifecycle database table

    Args:
        query (str): Search query text

    Returns:
        str: Formatted search results

    ────────────────────────────────────────────────────────────────
    Example Questions:
    • "List of devices currently active on MNO ( device type, manufacturer name, model name) "
    • "List down all the models currently active on all our network"
    • "what the total count for BYO devices currently active on our network, give the count by network"
    • "how may active subscriber are currently active on Samsung S23"
    • "top 5 models with most number of active subscriber"
    """   

    return await queryDb(user_question,ran_nca_device_prompt)


@tool("fetch_customer_order_data")
async def fetch_customer_order_data(user_question: str):
    """
    Async function that performs search on customer_order database table

    Args:
        query (str): Search query text

    Returns:
        str: Formatted search results

    ────────────────────────────────────────────────────────────────
    Example Questions:
    • "How many customers with base type as Device"
    • "How many customers purchased SIM products in year Oct 2025"
    • "Total purchases by order type for the month of January 2025"
    • "Total purchases by base type for the month of Apr 2024"
    • "How many hot sim requests from January to March 2025"
    • "List top 5 products purchased for year 2025"
    • "How many customer orders are in pending activation state"
    """   

    return await queryDb(user_question,ran_customer_order_device_prompt)