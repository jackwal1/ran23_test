import os
from dotenv import load_dotenv
import boto3
import time
import re
import traceback
import datetime
from decimal import Decimal
from typing import Annotated, Dict, List,Optional
import asyncio
import aioboto3
import logging
from utils import constants as CONST

log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")  # Replace 'RAN' with your app/module name



try:
    # STEP-1: Read the env variables
    ATHENA_REGION = os.environ["ATHENA_REGION"]
    ATHENA_WORKGROUP = os.environ["ATHENA_WORKGROUP"]
except Exception as e:
    print(e)
    print("Loading Environmment Variables from local .env file")
    load_dotenv()
    ATHENA_REGION = os.environ["ATHENA_REGION"]
    ATHENA_WORKGROUP = os.environ["ATHENA_WORKGROUP"]

# Initialize Athena client
athena_client = boto3.client('athena', region_name=ATHENA_REGION)  # Replace 'your-region'

def extract_database_from_query(query):
    """Extract the database from the query using regex."""
    try:
        match = re.search(r'FROM\s+(\w+)\.\w+', query, re.IGNORECASE)
        if match:
            return match.group(1)
        else:
            raise ValueError("Unable to extract database from query.")
    except Exception as e:
        traceback.print_exc()
        return "NA"


def run_query_and_get_results_from_athena(query):
    try:
        logger.info(f'run_query_and_get_results_from_athena :: Started')
        # Extract the database from the query
        database = extract_database_from_query(query)
        print(f"Using database: {database}")

        # Start query execution
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={
                'Database': database
            },
            WorkGroup=ATHENA_WORKGROUP
        )
        query_execution_id = response['QueryExecutionId']
        print(f"Query Execution ID: {query_execution_id}")
        
        # Wait for the query to complete
        while True:
            status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            state = status['QueryExecution']['Status']['State']
            if state == 'SUCCEEDED':
                print("Query succeeded.")
                break
            elif state in ['FAILED', 'CANCELLED']:
                print(f"Query {state.lower()}. Reason: {status['QueryExecution']['Status']['StateChangeReason']}")
                return None
            else:
                print("Waiting for query to complete...")
                time.sleep(2)

        # Fetch query results
        results = athena_client.get_query_results(QueryExecutionId=query_execution_id)
        rows = results['ResultSet']['Rows']
        headers = [col.get('VarCharValue', '') for col in rows[0]['Data']]

        # Convert to JSON format
        json_results = []
        for row in rows[1:]:
            json_results.append({headers[i]: col.get('VarCharValue', '') for i, col in enumerate(row['Data'])})

        logger.info(f'run_query_and_get_results_from_athena :: Completed')
        return json_results
    except Exception as e:
        logger.error(f'run_query_and_get_results_from_athena :: ERROR - {e}')
        traceback.print_exc()
        return []

def query_athena_db(query: str) -> Dict[str,str]:
    try:
        if query not in ['NA']:
            # call the athena query util
            sql_result = run_query_and_get_results_from_athena(query)
            return sql_result
        return None
    except Exception as e:
        print(e)
        logger.error(f'ERROR:{e} :: - query_athena_db')
        return None


async def run_query_and_get_results_from_athena_async(query: str) -> Optional[List[Dict[str, str]]]:
    """
    Asynchronously run an Athena query and return results.

    Args:
        query (str): The SQL query to execute

    Returns:
        Optional[List[Dict[str, str]]]: Query results as list of dictionaries, or None if failed
    """
    try:
        logger.info(f'run_query_and_get_results_from_athena_async :: Started')

        # Extract the database from the query
        database = extract_database_from_query(query)
        logger.info(f"Using database: {database}")

        # Create async session
        session = aioboto3.Session()

        async with session.client('athena', region_name=ATHENA_REGION) as athena_client:
            # Start query execution
            response = await athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={
                    'Database': database
                },
                WorkGroup=ATHENA_WORKGROUP
            )
            query_execution_id = response['QueryExecutionId']
            logger.info(f"Query Execution ID: {query_execution_id}")

            # Wait for the query to complete with async polling
            while True:
                status = await athena_client.get_query_execution(QueryExecutionId=query_execution_id)
                state = status['QueryExecution']['Status']['State']

                if state == 'SUCCEEDED':
                    logger.info("Query succeeded.")
                    break
                elif state in ['FAILED', 'CANCELLED']:
                    error_reason = status['QueryExecution']['Status']['StateChangeReason']
                    logger.info(f"Query {state.lower()}. Reason: {error_reason}")
                    logger.info(f'run_query_and_get_results_from_athena_async :: Query {state.lower()} - {error_reason}')
                    return None
                else:
                    logger.info("Waiting for query to complete...")
                    await asyncio.sleep(2)  # Non-blocking sleep

            # Fetch query results
            results = await athena_client.get_query_results(QueryExecutionId=query_execution_id)
            rows = results['ResultSet']['Rows']

            if not rows:
                logger.info(f'run_query_and_get_results_from_athena_async :: No results returned')
                return []

            headers = [col.get('VarCharValue', '') for col in rows[0]['Data']]

            # Convert to JSON format
            json_results = []
            for row in rows[1:]:
                row_dict = {}
                for i, col in enumerate(row['Data']):
                    if i < len(headers):
                        row_dict[headers[i]] = col.get('VarCharValue', '')
                json_results.append(row_dict)

            logger.info(f'run_query_and_get_results_from_athena_async :: Completed successfully with {len(json_results)} rows')
            return json_results

    except Exception as e:
        logger.error(f'run_query_and_get_results_from_athena_async :: ERROR - {e}')
        traceback.print_exc()
        return []


async def query_athena_db_async(query: str) -> Optional[List[Dict[str, str]]]:
    """
    Asynchronously query Athena database.

    Args:
        query (str): The SQL query to execute

    Returns:
        Optional[List[Dict[str, str]]]: Query results or None if failed/invalid
    """
    try:
        if query and query != 'NA':
            # Call the async athena query util
            sql_result = await run_query_and_get_results_from_athena_async(query)
            return sql_result
        return None
    except Exception as e:
        logger.error(e)
        logger.error(f'ERROR:{e} :: - query_athena_db_async')
        return None