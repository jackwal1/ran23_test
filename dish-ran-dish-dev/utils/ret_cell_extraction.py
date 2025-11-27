import json
import uuid
from typing import Optional, List, Dict, Tuple

import utils.ran_automation_validation as validate
import utils.gnb_validate_gpl_parameters_util as gnb_validate_util
from utils.logger import logger
from utils.redis_util import  get_redis_client
from utils.filtering_gnb_report_config_index import process_event
import utils.constants as CONST
import logging

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

async def extract_ret_data(
        gnb_request,
        cell_id: str = None,
        band_sector: str = None,
        vendor: str = None,
        hldc_address: str = None,
        antennamodel: str = None,
        aldid: str = None,
        usmip: str = None,
        duid: str = None,
        ruid: str = None,
        antennaid: str = None,
        port: str = None,
        cache_key: str = None,
):
    """Extract RET/GNB data with extensive debug‐level logging.

    Args:
        gnb_request: Incoming request object.
        cell_id: Cell ID from the request (optional).
        band_sector: Band sector information (optional).
        vendor: Vendor name (optional).
        hldc_address: HDLC address (optional).
        antennamodel: Antenna model (optional).
        aldid: ALD ID (optional).
        usmip: USM IP (optional).
        duid: DUID (optional).
        ruid: RUID (optional).
        antennaid: Antenna ID (optional).
        port: Port number (optional).
        cache_key: Key used to cache intermediate DB lookups (optional).

    Returns:
        A JSON‑serialisable dict describing success / failure and data payload.
    """
    logger.info("Entered extract_ret_data with args: %s", {
        "cell_id": cell_id,
        "band_sector": band_sector,
        "vendor": vendor,
        "hldc_address": hldc_address,
        "antennamodel": antennamodel,
        "aldid": aldid,
        "usmip": usmip,
        "duid": duid,
        "ruid": ruid,
        "antennaid": antennaid,
        "port": port,
        "cache_key": cache_key,
    })

    try:
        cell_name = generate_cell_name(
            gnb_request.table_type, cell_id, gnb_request.cell_name, band_sector
        )
        logger.info("Derived cell_name: %s", cell_name)

        # Capture all incoming locals for later filtering operations
        request = locals()
        logger.info("Request locals snapshot (filtered): %s", {
            k: v for k, v in request.items() if k not in {"gnb_request"}
        })

        cache_key, existing_data = await get_or_fetch_ret_data(
            gnb_request=gnb_request,
            cache_key=cache_key,
            cell_name=cell_name,
            band_sector=band_sector,
            vendor=vendor,
            request=request,
        )
        logger.info("Cache key after fetch: %s", cache_key)
        logger.info("Existing data records retrieved: %d", len(existing_data))

        # ------------------------------------------------------------------
        # Validate retrieved data
        # ------------------------------------------------------------------
        if not existing_data:
            response = {
                "status": "fail",
                "message": "Cell ID not available in the database.",
                "error_code": "VP-103",
            }
            logger.info("Validation failed – cell ID not present: %s", response)
            return response

        if len(existing_data) > 1:
            logger.info("Multiple DB rows found (%d) – applying priority checks", len(existing_data))
            response = await check_priority_fields(
                existing_data,
                gnb_request,
                hldc_address,
                antennamodel,
                aldid,
                usmip,
                duid,
                ruid,
                antennaid,
                port,
                cache_key,
            )
            if response:
                return response

        if len(existing_data) == 1:
            response = {
                "status": "Success",
                "message": "Unique data found",
                "existing_params": existing_data[0],
                "cache_key": cache_key,
            }
            logger.info("Unique record returned : %s", response)
            return response

        # Fallback – no unique match found
        response = {
            "status": "fail",
            "message": "No matching data found after filtering.",
            "error_code": "VP-104",
        }
        logger.info("Filtering produced no matches: %s", response)
        return response

    except Exception as exc:
        logger.exception("Unexpected error during RET data extraction")
        return {
            "status": "fail",
            "message": "An unexpected error occurred during RET data extraction.",
            "error_code": "VP-500",
            "details": str(exc),
        }

# -----------------------------------------------------------------------------
# Helper functions (unchanged business logic, enhanced logging only)
# -----------------------------------------------------------------------------

def generate_cell_name(table_type: str, cell_id: str, gnb_cell_name: str, band_sector: str = "") -> str:
    """Generate the canonical cell name depending on table type and band sector."""
    if table_type.lower() == "gnb" and gnb_cell_name is not None:
        cell_id = gnb_cell_name

    if cell_id and ("_" in cell_id):
        cell_name = cell_id
    else:
        logger.info("band_sector: %s", band_sector)
        if band_sector and table_type.lower() == "ret":
            parts = band_sector.split("_")
            if len(parts) > 1:
                band_suffix = band_sector.split("_")[1]
                cell_name = f"{cell_id}_{band_suffix}"
                #cell_name = f"{cell_id}_{band_sector}"
        elif band_sector and table_type.lower() == "gnb":
            cell_name = f"{cell_id}_{band_sector}"
        else:
            cell_name = cell_id
    return cell_name


async def get_or_fetch_ret_data(
    gnb_request,
    cache_key: Optional[str],
    cell_name: str,
    band_sector: str,
    vendor: str,
    request: Dict
) -> Tuple[str, List[Dict]]:

    logger.info(f"redis client Initialised")
    redis = get_redis_client()
    existing_data= []

    if cache_key is None or cache_key== '' :
        cache_key = str(uuid.uuid4())
        logger.info(f"cache_key :{cache_key}")
        
        if gnb_request.table_type.lower()=="ret":
            existing_data = await validate.get_data_for_ret(cell_name=cell_name, vendor=vendor)
        elif gnb_request.table_type.lower()=="gnb":
            existing_data = await gnb_validate_util.get_data_by_cell_id_node_id(cell_id=None,cell_name=cell_name, node_id= None,band=None, purpose=None, frequency=None,index=None, report_type=gnb_request.event,vendor=vendor)

        logger.info(f"Data retrieved from DB : {existing_data},{len(existing_data)},{type(existing_data)}")
        if existing_data:
            if len(existing_data) > 1 and band_sector and gnb_request.table_type.lower()=="ret" :
                existing_data = await validate.extract_band_identifier(
                    band_sector.split("_")[0], existing_data
                )
                logger.info(f"Data after filtering based on band : {existing_data},{len(existing_data)}")
            await redis.set(cache_key, json.dumps(existing_data),expire_seconds=86400)
    else:
        cached_data = await redis.get(cache_key)
        logger.info(f"cached data: {cached_data}")
        if cached_data:
            existing_data = json.loads(cached_data)
            existing_data = filter_data_by_request_columns(
                existing_data,
                gnb_request,
                request.get("cell_id"),
                request.get("hldc_address"),
                request.get("antennamodel"),
                request.get("aldid"),
                request.get("usmip"),
                request.get("duid"),
                request.get("ruid"),
                request.get("antennaid"),
                request.get("port")         
            )
          
    return cache_key, existing_data


def filter_data_by_request_columns(
        existing_data,
        gnb_request,
        cell_id=None,
        hldc_address=None,
        antennamodel=None,
        aldid=None,
        usmip=None,
        duid=None,
        ruid=None,
        antennaid=None,
        port=None
):
    # prepare criteria dict
    if gnb_request.table_type.lower()=="ret":
        criteria = {
            "cellname": cell_id,
            "hdlc_address": hldc_address,
            "antennamodel": antennamodel,
            "aldid": aldid,
            "usmip": usmip,
            "duid": duid,
            "ruid": ruid,
            "antennaid": antennaid,
            "port": port,
        }
    elif gnb_request.table_type.lower()=="gnb":
        criteria={
            "cell_name": gnb_request.cell_name,
            "report_config_entry_index": gnb_request.index,
            "ssb_config_ssb_freq": gnb_request.frequency,
            "band": gnb_request.band,
            "cucp_id": gnb_request.cucp_id,
            "du_id": gnb_request.du_id,
            "purpose": gnb_request.purpose,
            "cell_identity": gnb_request.cell_id,
            "gnodeb_id": gnb_request.gnb,
            "report_type": gnb_request.event.upper() if gnb_request.event else None
        }

    # Remove criteria that are common across all records
    if existing_data:
        filtered_criteria = {}
        for field, val in criteria.items():
            if val is not None:
                # Get all unique values for this field in existing_data
                field_values = {rec.get(field) for rec in existing_data if field in rec}
                # Only keep this criteria if there are multiple different values
                # (i.e., filtering by this field would actually reduce the dataset)
                if len(field_values) > 1:
                    filtered_criteria[field] = val
                else:
                    logger.info(f"Ignoring criteria '{field}' as it has the same value across all records: {field_values}")
        criteria = filtered_criteria

    # log inputs
    logger.info(json.dumps({
        "event": "filter_request",
        "input_count": len(existing_data),
        "criteria": {k: v for k, v in criteria.items() if v is not None},
        "sample_input_records": existing_data[:5]  # limit to first 5 to keep logs small
    }))

    # if no filters specified, return all
    if not any(criteria.values()):
        result = existing_data
    else:
        def matches(rec):
            return all(val is None or rec.get(field) == val
                       for field, val in criteria.items())
        result = [rec for rec in existing_data if matches(rec)]

    # log outputs
    logger.info(json.dumps({
        "event": "filter_result",
        "output_count": len(result),
        "sample_output_records": result[:5]
    }))
    return result


async def check_priority_fields(
    existing_data,
    gnb_request,
    hldc_address: str = None,
    antennamodel: str = None,
    aldid: str = None,
    usmip: str = None,
    duid: str = None,
    ruid: str = None,
    antennaid: str = None,
    port: str = None,
    cache_key: str = None
):
    """Identify unique records by checking priority fields; extensive logging added."""
    logger.info("Executing check_priority_fields for %d records", len(existing_data))

    # ----------------------------------------------------------------------
    # RET logic
    # ----------------------------------------------------------------------
    if gnb_request.table_type.lower() == "ret":
        priority_fields = [
            "cellname",
            "antennamodel",
            "port",
            "aldid",
            "duid",
            "ruid",
            "usmip",
            "hdlc_address",
        ]
        request_values = locals()

        for column in priority_fields:
            request_value = request_values.get(column)
            logger.info("Checking priority field '%s' (request=%s)", column, request_value)

            column_values = [record.get(column) for record in existing_data if column in record]
            unique_values = list(set(column_values))
            logger.info("Unique values for '%s': %s", column, unique_values)

            if len(unique_values) > 1:
                allowed_keys = {"serial_number", column}
                existing_param = await get_unique_records(existing_data, allowed_keys, column)

                response = {
                    "status": "fail",
                    "message": f"Multiple {'hdlc address' if column == 'hldc_address' else column} found for the input request. Please select from the below",
                    #"message": f"Multiple {column} found for the input request. Please select from the below",
                    "error_code": "VP-" + column,
                    "cache_key": cache_key,
                    "ret_existing_params": existing_param,
                    "existing_param_table": await gnb_validate_util.generate_html_table(existing_param),
                }
                logger.info("Priority conflict on '%s' – prompting user", column)
                return response
        return None

    # ----------------------------------------------------------------------
    # GNB logic
    # ----------------------------------------------------------------------
    elif gnb_request.table_type.lower() == "gnb":
        priority_fields = ["cell_name","cell_identity","gnodeb_id", "band", "report_config_entry_index"]
        request_values = {
            "cell_name": gnb_request.cell_name,
            "report_config_entry_index": gnb_request.index,
            "cell_identity": gnb_request.cell_id,
            "gnodeb_id": gnb_request.gnb,
            "band": gnb_request.band,
        }

        for column in priority_fields:
            request_value = request_values.get(column)
            logger.info("Checking priority field '%s' (request=%s)", column, request_value)

            column_values = [record.get(column) for record in existing_data if column in record]
            unique_values = list(set(column_values))
            logger.info("Unique values for '%s': %s", column, unique_values)

            if len(unique_values) > 1:
                current_data = existing_data

                if (column == "report_config_entry_index"
                        and gnb_request.event
                        and gnb_request.cell_name):
                    logger.info("Applying intelligent mapping for '%s'", column)
                    filtered_data = await process_event(
                        gnb_request.event,
                        gnb_request.band,
                        existing_data
                    )

                    if len(filtered_data) == 1:
                        logger.info("Unique record found using intelligent mapping")
                        return {
                            "status": "Success",
                            "message": "Unique data found",
                            "existing_params": filtered_data[0],
                            "cache_key": cache_key,
                        }
                    elif len(filtered_data) > 1:
                        current_data = filtered_data

                allowed_keys = {"serial_number", column}
                existing_param = await get_unique_records(current_data, allowed_keys, column)

                logger.info("Priority conflict on '%s' – prompting user", column)

                return {
                    "status": "fail",
                    "message": f"Multiple {'target ' if column == 'band' else ''}{column} found for the input request. Please select from the below",
                    "error_code": "VP-" + column,
                    "cache_key": cache_key,
                    "ret_existing_params": existing_param,
                    "existing_param_table": await gnb_validate_util.generate_html_table(existing_param),
                }

        # No conflicts
        logger.info("No priority conflicts – unique GNB record")
        return {
            "status": "Success",
            "message": "Unique data found",
            "existing_params": existing_data[0],
            "cache_key": cache_key,
        }


async def get_unique_records(existing_data, allowed_keys, column):
    """Return unique record slices for user selection (unchanged logic, new logging)."""
    logger.info("Computing unique records for column '%s'", column)

    seen_cells = set()
    filtered_unique = []
    for item in existing_data:
        entry = {k: item[k] for k in item if k in allowed_keys}
        cell = entry.get(column)
        if cell and cell not in seen_cells:
            filtered_unique.append(entry)
            seen_cells.add(cell)

    for idx, item in enumerate(filtered_unique, start=1):
        item["serial_number"] = idx

    logger.info("Unique records generated: %d", len(filtered_unique))
    return filtered_unique

import json
import re
from typing import Any, Union, Optional

def extract_json_from_string(input_str: str) -> Optional[Union[dict, list]]:
    """
    Extract and normalize JSON from a string.
    """
    try:
        return recursively_clean_json(json.loads(input_str))
    except json.JSONDecodeError:
        try:
            match = re.search(r'({.*}|\[.*\])', input_str, re.DOTALL)
            if match:
                return recursively_clean_json(json.loads(match.group(1)))
        except Exception as e:
            print(f"Failed to parse JSON: {e}")
    return None

def recursively_clean_json(data: Any) -> Any:
    """
    Recursively processes a JSON object or list,
    decoding nested JSON strings and normalizing primitives.
    """
    if isinstance(data, dict):
        return {k: recursively_clean_json(_try_parse_json(v)) for k, v in data.items()}
    elif isinstance(data, list):
        return [recursively_clean_json(_try_parse_json(item)) for item in data]
    return _normalize_primitive(data)

def _try_parse_json(value: Any) -> Any:
    """
    Tries to parse a value as JSON if it's a string.
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
