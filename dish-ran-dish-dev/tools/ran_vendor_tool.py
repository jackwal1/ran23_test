from typing import Literal, List, Dict, Annotated
from langchain_core.tools import tool
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict, List
import json
from datetime import datetime, date
import inspect
from decimal import Decimal
import utils.postgres_util.dbutil as db
import utils.snow_utils.snowflake_util as snow_db
from utils.snow_utils.snowflake_util import run_in_threadpool
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools
from utils.redis_util import get_redis_client
from utils.log_init import logger
from utils import constants as constant

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

@tool("search_vendor_by_cellname")
async def search_vendor_by_cellname(cell_name: Annotated[str, "Cell Name / Site identifier"],) -> str:
    """
    This tool finds vendor for a site identifier like BOBOS01075F, DEN0A1667d_2_n71_F-G
    Returns 'Mavenir', 'Samsung', or 'Not Found' without raising errors.
    Args:
        query: Cell Name / Site identifier

    Returns:
        Returns 'Mavenir', 'Samsung', or 'Not Found' without raising errors.

    Examples:
        1. search_vendor_by_cellname("BOBOS01075F")
    """
    try:
        results = await get_vendor_by_cellname(cell_name)
        return results
    except Exception as e:
        logger.error(f"error occurred in RAN docs search tool: {e}")
        return "Vendor Not Found, Please ask user for vendor"


async def get_vendor_by_cellname(cell_name: str) -> str:
    """
    Check which vendor table contains the given cell_name (ILIKE search).
    Priority lookup in 'nexus_table'; if not found, fall back to Mavenir/Samsung union.
    Uses Redis cache to speed up repeat lookups.
    Returns 'Mavenir', 'Samsung', or 'Not Found' without raising errors.
    """
    if not cell_name:
        logger.warning("cell_name was not provided.")
        return "Not Found"

    search_key = cell_name.split("_")[0]
    ilike_pattern = f"%{search_key}%"
    cache_key = f"vendor_lookup:{search_key.lower()}"

    redis = get_redis_client()

    # 1. Try Redis cache
    try:
        cached_data = await redis.get(cache_key)
        if cached_data:
            vendor = json.loads(cached_data)
            logger.info("Cache hit for cell_name: %s -> %s", search_key, vendor)
            return vendor
        else:
            logger.info("Cache miss for cell_name: %s", search_key)
    except Exception as e:
        logger.warning("Redis lookup failed for key %s: %s", cache_key, e)

    # Define queries
    priority_query = text(f"""
        SELECT ran_vendor
        FROM {constant.nexus_table}
        WHERE site_id ILIKE :site_id
        LIMIT 1
    """)

    fallback_query = text(f"""
        SELECT vendor
        FROM (
            SELECT 'mavenir' AS vendor
            FROM {constant.mavenir_table}
            WHERE cellname ILIKE :cellname
            UNION ALL
            SELECT 'samsung' AS vendor
            FROM {constant.samsung_table}
            WHERE cellname ILIKE :cellname
        ) AS subquery
        LIMIT 1
    """)

    params_priority = {"site_id": ilike_pattern}
    params_fallback = {"cellname": ilike_pattern}

    try:
        async with snow_db.get_db_session() as session:
            async with asyncio.timeout(90):
                # Try priority (nexus) table
                logger.info("Checking nexus table %s for cell_name: %s", constant.nexus_table, search_key)
                result = await run_in_threadpool(session.execute, priority_query, params_priority)
                row = result.fetchone()
                if row and row[0]:
                    vendor = row[0].capitalize()
                    logger.info("Found in nexus table: %s", vendor)
                    await redis.set(cache_key, json.dumps(vendor))  # 7 days = 604800 seconds
                    return vendor

                # Fallback to Mavenir/Samsung
                # logger.info("Falling back to vendor tables for: %s", search_key)
                # result = await run_in_threadpool(session.execute, fallback_query, params_fallback)
                # row = result.fetchone()
                # if row:
                #     vendor = row[0].capitalize()
                #     logger.info("Found in fallback vendor table: %s", vendor)
                #     await redis.set(cache_key, json.dumps(vendor))  # No expiry
                #     return vendor

    except Exception as e:
        logger.error("Error executing vendor lookup for cell_name %s: %s", search_key, e)

    logger.info("cell_name not found in any vendor table.")
    return "Vendor Not Found, Please ask user for vendor"

tools = [search_vendor_by_cellname]
