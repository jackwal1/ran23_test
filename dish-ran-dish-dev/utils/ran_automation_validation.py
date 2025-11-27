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
import utils.constants as constant
from collections import defaultdict
from collections import OrderedDict
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools
from utils.redis_util import get_redis_client

# Setup the logging configuration
log_level = getattr(logging, constant.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")


def convert_to_serializable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()  # Converts to string in ISO format (e.g., "2024-12-18T03:37:35")
    if isinstance(value, bool):
        val = str(value)
        return val.upper()  # Convert boolean to string
    if isinstance(value, Decimal):
        return str(value)  # Convert decimal to string
    if isinstance(value, Decimal):
        return str(value)  # Convert decimal to string
    if isinstance(value, int):
        return str(value)  # Convert integer to string
    if isinstance(value, float):
        return str(value)  # Convert float to string
    return value

def gnb_filter_out_rows_with_none(data: list[dict]) -> list[dict]:
    """
    Removes any dictionary (row) from the list where any of the specified keys have None values.
    Ignores other keys even if their values are None.
    """
    required_keys = [
        "cell_name",
        "gnodeb_id",
        "cell_identity",
        "cucp_id",
        "du_id",
        "report_config_entry_index",
        "ssb_config_ssb_freq",
        "purpose",
        "band",
        "report_type"
    ]

    return [
        row for row in data
        if all(row.get(key) is not None for key in required_keys)
    ]


def filter_out_rows_with_none(data: list[dict]) -> list[dict]:
    """
    Removes any dictionary (row) from the list where any value is None.
    """
    return [row for row in data if all(value is not None for value in row.values())]


async def get_data_by_cell_name(cell_name: str, hldc_address: str, aldid :str, vendor: str):
    """
    Fetches data from the antenna_data table using a raw SQL query based on the CELL_NAME
    and converts it into JSON format.
    """
    query = ""
    query_params = {"cellname": cell_name}

    if vendor.lower() == 'mavenir':
        table_name = constant.mavenir_table
        cell_column = "cellname"
        hldc_address_column = "hdlc_address"
        query_params["hdlc_address"] = hldc_address  # Add hldc_address only for Mavenir

        query = text(f"""
        SELECT * 
        FROM {table_name}
        WHERE {cell_column} = :cellname
        AND {hldc_address_column} = :hdlc_address;
        """)

    elif vendor.lower() == 'samsung':
        table_name = constant.samsung_table
        cell_column = "cellname"
        aldid_column = "aldid"

        query_params["aldid"] = aldid

        query = text(f"""
        SELECT * 
        FROM {table_name}
        WHERE {cell_column} = :cellname
        AND {aldid_column} = :aldid;
        """)

    if table_name:
        async with snow_db.get_db_session() as session:
            try:
                # Execute the raw SQL query
                logger.info("Executing query: %s", query)
                result = await run_in_threadpool(session.execute, query, query_params)

                rows = result.fetchall()  # Fetch all matching rows

                # Fetch column names
                column_names = result.keys()
                logger.info("Fetched column names: %s", column_names)

                # Convert the rows to a JSON-serializable format, mapping column names with values
                json_results = [
                    {column.lower(): convert_to_serializable(value) for column, value in zip(column_names, row)}
                    for row in rows
                ]

                # Remove rows that contain any None values
                json_results = filter_out_rows_with_none(json_results)

                # Serialize to JSON and log
                json_output = json.dumps(json_results, indent=4)
                logger.info("JSON Output: %s", json_output)

                return json_results  # Return JSON-serializable data
            except Exception as e:
                logger.error("Error occurred while get_data_by_cell_name: %s", e)
                raise


async def get_catalog_data_by_antenna_model(antenna_model: str, vendor: str):
    """

    """
    query = text("""
    SELECT * 
    FROM ran.dish_5g_antenna_catalog
    WHERE antenna_model_name = :antenna_model;
    """)
    async with db.get_session() as session:
        try:
            logger.info("Fetching data for Antenna model: %s", antenna_model)
            # Execute the raw SQL query
            result = await session.execute(query, {"antenna_model": antenna_model})
            rows = result.fetchall()  # Fetch all matching rows

            # Fetch column names
            column_names = result.keys()
            logger.info("Fetched column names: %s", column_names)

            # Convert the rows to a JSON-serializable format, mapping column names with values
            json_results = [
                {column.lower(): convert_to_serializable(value) for column, value in zip(column_names, row)}
                for row in rows
            ]

            # Remove rows that contain any None values
            json_results = filter_out_rows_with_none(json_results)

            # Serialize to JSON and log
            json_output = json.dumps(json_results, indent=4)
            logger.info("JSON Output: %s", json_output)

            return json_results  # Return JSON-serializable data
        except Exception as e:
            logger.error("Error occurred while get_catalog_data_by_antenna_model: %s", e)
            raise


import logging
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple


def determine_band_for_item(item: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """
    Helper function to determine the band type for a single antenna item.
    Args:
        item (Dict[str, Any]): Dictionary containing antenna information
    Returns:
        Tuple[Optional[str], bool]: The determined band ("LB" or "MB") and a flag indicating if any pattern matched
    """
    model_id = item.get('antennamodel')

    # Rule 1: If Antenna Model Number is Missing or Empty
    if not model_id or (isinstance(model_id, str) and not model_id.strip()):
        logging.warning(f"Antenna model ID is missing or empty for item: {item}")
        return None, False

    model_id = model_id.strip().upper()
    pattern_matched = False

    # JMA Antennas (MX08)
    if model_id.startswith("MX08"):
        pattern_matched = True
        if len(model_id) >= 2:
            suffix = model_id[-2:]
            if suffix == "R1":
                return "LB", pattern_matched
            elif suffix == "B1":
                return "MB", pattern_matched
        return None, pattern_matched

    # CCI Antennas (045) - FIXED: Extract from 6th character (index 5)
    if model_id.startswith("045"):
        pattern_matched = True
        if len(model_id) > 5:  # Ensure we have enough characters
            # Extract from 6th character (index 5)
            suffix = model_id[5:]
            if suffix.startswith("R1"):
                return "LB", pattern_matched
            elif suffix.startswith("Y1Y2"):
                return "MB", pattern_matched
        return None, pattern_matched

    # CellMax Antennas (120) - FIXED: Handle both combined and individual patterns
    if model_id.startswith("120"):
        pattern_matched = True
        if "-" in model_id:
            parts = model_id.split("-")
            if len(parts) > 1:
                second_part = parts[1]
                # Handle both combined patterns (R1R2, Y1Y2) and individual (R1, R2, Y1, Y2)
                if second_part in {"R1", "R2", "R1R2"}:
                    return "LB", pattern_matched
                elif second_part in {"Y1", "Y2", "Y1Y2"}:
                    return "MB", pattern_matched
        return None, pattern_matched

    # KMW Antennas (KE)
    if model_id.startswith("KE"):
        pattern_matched = True
        if "_" in model_id:
            suffix = model_id.split("_")[-1]
            if suffix in {"R1", "R2"}:
                return "LB", pattern_matched
            elif suffix in {"B", "Y1"}:
                return "MB", pattern_matched
        return None, pattern_matched

    # CommScope Antennas (FFV or FV) - FIXED: Added model number parsing
    if model_id.startswith("FFV") or model_id.startswith("FV"):
        pattern_matched = True

        # Parse model number structure as mentioned in document
        parts = model_id.split("-")
        if len(parts) >= 3:
            third_part = parts[2]
            logging.info(f"CommScope model_id: {model_id}, third_part: {third_part}")

        max_tilt = item.get('maximumtilt')
        logging.info(f"model_id: {model_id}")
        logging.info(f"maximum tilt value: {max_tilt}")

        if max_tilt is not None:
            try:
                tilt_value = Decimal(str(max_tilt))
                result = "LB" if tilt_value > 120 else "MB"
                logging.info(f'value returned: {result}')
                return result, pattern_matched
            except (ValueError, TypeError):
                logging.warning(f"Invalid maximum-tilt value: {max_tilt}")
                return None, pattern_matched
        else:
            logging.warning(f"Maximum-tilt is missing for CommScope antenna: {model_id}")
            return None, pattern_matched

    # Dengyo Antennas (CPTXW) - CLEANED UP: Focus on primary parameter name
    if model_id.startswith("CPTXW"):
        pattern_matched = True

        # Primary parameter name as per document
        operating_band = item.get('antenna-operating-band')

        # Fallback to common variations if primary not found
        if not operating_band:
            operating_band = (item.get('antennaoperatingband') or
                              item.get('antenna_operating_band'))

        if operating_band:
            operating_band = operating_band.strip()
            if operating_band in {"B5,B12", "B12,B14"}:
                return "LB", pattern_matched
            elif operating_band in {"B10,B40", "B2,B10,B40", "B42,B43"}:
                return "MB", pattern_matched
        else:
            # Fallback: try to extract from model number if parameter is missing
            parts = model_id.split("-")
            if len(parts) > 2:
                potential_band = parts[-1]
                if potential_band in {"B5,B12", "B12,B14"}:
                    return "LB", pattern_matched
                elif potential_band in {"B10,B40", "B2,B10,B40", "B42,B43"}:
                    return "MB", pattern_matched
            logging.warning(f"Operating band information missing for Dengyo antenna: {model_id}")

        return None, pattern_matched

    # No pattern matched
    if not pattern_matched:
        logging.warning(f"Model {model_id} does not match any known pattern categories.")
        return None, False

    # This handles the case where a pattern matched but no band was determined
    return None, pattern_matched


async def extract_band_identifier(filter_band: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters a list of dictionaries based on band type (LB or MB) using multithreading.
    Also includes items where the antenna model doesn't match any defined category.

    Args:
        filter_band (str): The band to filter on ("LB" or "MB")
        data (List[Dict[str, Any]]): List of dictionaries with antenna information

    Returns:
        List[Dict[str, Any]]: Filtered list containing dictionaries that match the specified band
                              and those that don't match any defined category
    """
    if not data:
        return []

    # Process items in parallel using ThreadPoolExecutor
    loop = asyncio.get_event_loop()

    # Define a filtering function that combines determination and filtering
    async def process_batch(batch):
        filtered_batch = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Map the determination function across all items
            band_futures = [
                loop.run_in_executor(executor, determine_band_for_item, item)
                for item in batch
            ]

            # Wait for all results
            results = await asyncio.gather(*band_futures)

            # Filter based on results
            for item, (band, pattern_matched) in zip(batch, results):
                # Include items that match the specified band or don't match any defined category
                if band == filter_band or not pattern_matched:
                    filtered_batch.append(item)

        return filtered_batch

    # Batch size for processing (adjust based on your dataset size and machine capabilities)
    batch_size = 1000
    batches = [data[i:i + batch_size] for i in range(0, len(data), batch_size)]

    # Process all batches and combine results
    batch_results = await asyncio.gather(*[process_batch(batch) for batch in batches])
    filtered_data = [item for batch in batch_results for item in batch]
    logger.info(f"fitered data length :{len(filtered_data)}")
    return filtered_data

async def get_data_for_ret(cell_name: str = None, hldc_address: str = None, aldid: str = None, vendor: str = None):
    """
    Fetches data from the antenna_data table using a raw SQL query based on the optional parameters
    and converts it into JSON format.
    """

    if not vendor:
        logger.error("Vendor is required to determine the table name.")
        raise ValueError("Vendor must be specified.")

    query_params = {}
    conditions = []

    if vendor.lower() == 'mavenir':
        table_name = constant.mavenir_table

        if cell_name:
            conditions.append("cellname ILIKE :cellname")
            query_params["cellname"] = f"%{cell_name}%"

        if hldc_address:
            conditions.append("hdlc_address ILIKE :hdlc_address")
            query_params["hdlc_address"] = f"%{hldc_address}%"

    elif vendor.lower() == 'samsung':
        table_name = constant.samsung_table

        if cell_name:
            conditions.append("cellname ILIKE :cellname")
            query_params["cellname"] = f"%{cell_name}%"

        if aldid:
            conditions.append("aldid ILIKE :aldid")
            query_params["aldid"] = f"%{aldid}%"

    else:
        logger.error("Unsupported vendor: %s", vendor)
        raise ValueError("Unsupported vendor.")

    if not conditions:
        logger.error("At least one filter condition must be provided.")
        raise ValueError("At least one filter parameter must be specified.")

    query = text(f"SELECT * FROM {table_name} WHERE " + " AND ".join(conditions) + " LIMIT 25")

    async with snow_db.get_db_session() as session:
        try:
            # Execute the raw SQL query
            logger.info("Executing query: %s", query)
            result = await run_in_threadpool(session.execute, query, query_params)

            rows = result.fetchall()  # Fetch all matching rows

            # Fetch column names
            column_names = result.keys()
            logger.info("Fetched column names: %s", column_names)

            # Convert the rows to a JSON-serializable format
            json_results = [
                {column.lower(): convert_to_serializable(value) for column, value in zip(column_names, row)}
                for row in rows
            ]

            # Remove rows that contain any None values
            json_results = filter_out_rows_with_none(json_results)

            json_results = [
                OrderedDict([("serial_number", idx + 1)] + list(item.items()))
                for idx, item in enumerate(json_results)
            ]

            # Serialize to JSON and log
            json_output = json.dumps(json_results, indent=4)
            logger.info("JSON Output: %s", json_output)

            return json_results  # Return JSON-serializable data
        except Exception as e:
            logger.error("Error occurred while fetching data: %s", e)
            raise


async def get_data_for_ret_aoi_usmip(cell_name: str = None, hldc_address: str = None, aldid: str = None, vendor: str = None):
    """
    Fetches data from the antenna_data table using a raw SQL query based on the optional parameters
    and converts it into JSON format.
    """

    if not vendor:
        logger.error("Vendor is required to determine the table name.")
        raise ValueError("Vendor must be specified.")

    query_params = {}
    conditions = []

    if vendor.lower() == 'samsung':
        table_name = constant.samsung_table

        if cell_name:
            conditions.append("cellname ILIKE :cellname")
            query_params["cellname"] = f"%{cell_name}%"

        if aldid:
            conditions.append("aldid ILIKE :aldid")
            query_params["aldid"] = f"%{aldid}%"

    else:
        logger.error("Unsupported vendor: %s", vendor)
        raise ValueError("Unsupported vendor.")

    if not conditions:
        logger.error("At least one filter condition must be provided.")
        raise ValueError("At least one filter parameter must be specified.")

    query = text(f"SELECT * FROM {table_name} WHERE " + " AND ".join(conditions) + " LIMIT 5")

    async with snow_db.get_db_session() as session:
        try:
            # Execute the raw SQL query
            logger.info("Executing query: %s", query)
            result = await run_in_threadpool(session.execute, query, query_params)

            rows = result.fetchall()  # Fetch all matching rows

            # Fetch column names
            column_names = result.keys()
            logger.info("Fetched column names: %s", column_names)

            # Convert the rows to a JSON-serializable format
            json_results = [
                {column.lower(): convert_to_serializable(value) for column, value in zip(column_names, row)}
                for row in rows
            ]

            json_results = [
                OrderedDict([("serial_number", idx + 1)] + list(item.items()))
                for idx, item in enumerate(json_results)
            ]

            # Serialize to JSON and log
            json_output = json.dumps(json_results, indent=4)
            logger.info("JSON Output: %s", json_output)

            return json_results  # Return JSON-serializable data
        except Exception as e:
            logger.error("Error occurred while fetching data: %s", e)
            raise

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
                logger.info("Falling back to vendor tables for: %s", search_key)
                result = await run_in_threadpool(session.execute, fallback_query, params_fallback)
                row = result.fetchone()
                if row:
                    vendor = row[0].capitalize()
                    logger.info("Found in fallback vendor table: %s", vendor)
                    await redis.set(cache_key, json.dumps(vendor))  # 7 days = 604800 seconds
                    return vendor

    except Exception as e:
        logger.error("Error executing vendor lookup for cell_name %s: %s", search_key, e)

    logger.info("cell_name not found in any vendor table.")
    return "Not Found"





from sqlalchemy import text
from collections import OrderedDict
import json

async def get_data_for_ret_revalidate(cell_name: str = None, hldc_address: str = None, aldid: str = None,
                                      usmip: str = None, duid: str = None, ruid: str = None,
                                      antennaid: str = None, antennamodel: str = None, vendor: str = None):
    """
    Fetches data from the antenna_data table using a raw SQL query based on the optional parameters
    and converts it into JSON format.
    """

    if not vendor:
        logger.error("Vendor is required to determine the table name.")
        raise ValueError("Vendor must be specified.")

    query_params = {}
    conditions = []

    if vendor.lower() == 'mavenir':
        table_name = constant.mavenir_table

        if cell_name is not None:
            conditions.append("cellname ILIKE :cell_name")
            query_params["cell_name"] = cell_name
        else:
            conditions.append("cellname IS NULL")

        if hldc_address is not None:
            conditions.append("hdlc_address ILIKE :hdlc_address")
            query_params["hdlc_address"] = hldc_address
        else:
            conditions.append("hdlc_address IS NULL")

    elif vendor.lower() == 'samsung':
        table_name = constant.samsung_table

        if cell_name is not None:
            conditions.append("cellname ILIKE :cell_name")
            query_params["cell_name"] = cell_name
        else:
            conditions.append("cellname IS NULL")

        if aldid is not None:
            conditions.append("aldid ILIKE :aldid")
            query_params["aldid"] = aldid
        else:
            conditions.append("aldid IS NULL")

        if usmip is not None:
            conditions.append("usmip ILIKE :usmip")
            query_params["usmip"] = usmip
        else:
            conditions.append("usmip IS NULL")

        if duid is not None:
            conditions.append("duid ILIKE :duid")
            query_params["duid"] = duid
        else:
            conditions.append("duid IS NULL")

        if ruid is not None:
            conditions.append("ruid ILIKE :ruid")
            query_params["ruid"] = ruid
        else:
            conditions.append("ruid IS NULL")

        if antennaid is not None:
            conditions.append("antennaid ILIKE :antennaid")
            query_params["antennaid"] = antennaid
        else:
            conditions.append("antennaid IS NULL")

        if antennamodel is not None:
            conditions.append("antennamodel ILIKE :antennamodel")
            query_params["antennamodel"] = antennamodel
        else:
            conditions.append("antennamodel IS NULL")

    else:
        logger.error("Unsupported vendor: %s", vendor)
        raise ValueError("Unsupported vendor.")

    if not conditions:
        logger.error("At least one filter condition must be provided.")
        raise ValueError("At least one filter parameter must be specified.")

    query = text(f"SELECT * FROM {table_name} WHERE " + " AND ".join(conditions) + " LIMIT 25")

    async with snow_db.get_db_session() as session:
        try:
            logger.info("Executing query: %s", query)
            result = await run_in_threadpool(session.execute, query, query_params)
            rows = result.fetchall()
            column_names = result.keys()
            logger.info("Fetched column names: %s", column_names)

            json_results = [
                {column.lower(): convert_to_serializable(value) for column, value in zip(column_names, row)}
                for row in rows
            ]

            # Remove rows that contain any None values
            json_results = filter_out_rows_with_none(json_results)

            json_results = [
                OrderedDict([("serial_number", idx + 1)] + list(item.items()))
                for idx, item in enumerate(json_results)
            ]

            json_output = json.dumps(json_results, indent=4)
            logger.info("JSON Output: %s", json_output)

            return json_results
        except Exception as e:
            logger.error("Error occurred while fetching data: %s", e)
            raise
