from sqlalchemy import text
from typing import Dict, List, Optional
import datetime
import traceback
from decimal import Decimal
import utils.postgres_util.dbutil as db
from utils import constants as CONST
import logging
import utils.snow_utils.snowflake_util  as snow_db
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")


class QueryTimeoutException(Exception):
    """Raised when a Snowflake query exceeds the timeout limit."""
    pass

class QueryExecutionException(Exception):
    """Raised when a Snowflake query fails due to an unexpected error."""
    pass


async def run_in_threadpool(func, *args, **kwargs):
    """
    Run a synchronous function in a thread pool to make it async-compatible.

    Args:
        func: The synchronous function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the function execution
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, functools.partial(func, *args, **kwargs))


async def query_snow_db(query: str) -> Optional[List[Dict[str, str]]]:
    """
    Execute an async Snowflake query using SQLAlchemy session with a 90-second timeout.

    Args:
        query (str): SQL query to execute

    Returns:
        Optional[List[Dict[str, str]]]: Query results or None if error/no query/timeout
    """
    if query in ['NA', None, '']:
        logger.info('No valid query provided :: - query_snow_db')
        return None

    try:
        async with snow_db.get_db_session() as session:
            async with asyncio.timeout(90):
                # Execute the query in a thread pool to avoid blocking the event loop
                logger.info(f"Executing query: {query}")
                result = await run_in_threadpool(session.execute, text(query))

                # Fetch rows and column names
                rows = result.fetchall()
                column_names = result.keys()

                sql_result = []
                for row in rows:
                    row_dict = dict(zip(column_names, row))
                    for key, value in row_dict.items():
                        if isinstance(value, (datetime.date, datetime.datetime)):
                            row_dict[key] = value.isoformat()
                        elif isinstance(value, Decimal):
                            row_dict[key] = int(round(value, 2))
                    sql_result.append(row_dict)

                logger.info(f'query:{query} :: sql_results:{sql_result} :: - query_snow_db')
                return sql_result

    except asyncio.TimeoutError:
        error_msg = (
            f"Query execution timed out after 90 seconds. "
            f"Query: {query}"
        )
        logger.error(error_msg)
        raise QueryTimeoutException(error_msg)

    except Exception as e:
        error_msg = (
            f"Unexpected error during query execution.\n"
            f"Query: {query}\n"
            f"Error: {str(e)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        logger.error(error_msg)
        raise QueryExecutionException(error_msg)