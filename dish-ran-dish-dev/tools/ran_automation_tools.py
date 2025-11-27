from langchain_core.tools import tool
import utils.snow_utils.snowflake_util as snow_db
from sqlalchemy import text
import asyncio
from typing import List, Dict, Any, Optional, Annotated
import json
import aiohttp
import os
from dotenv import load_dotenv
import datetime
from utils.ran_automation_validation import extract_band_identifier
import utils.gnb_validate_gpl_parameters_util as gnb_validate_util
import re
from utils import constants as CONST
from routers.ran_automation import UploadRETParamsRequest, process_csv, ValidateParamsRequest, validate_params
from utils.user_id_injection import get_user_from_thread
from utils.gnb_validate_gpl_parameters_util import json_to_dynamic_markdown, json_to_dynamic_markdown_header_collection
from langchain_core.runnables import RunnableConfig
import traceback

load_dotenv()


# Now import AgentState after the monkey patch
from agent.base_agent_asset import AgentState

ACTUAL_NETWORK_CALL_FLAG = CONST.ACTUAL_NETWORK_CALL_FLAG.strip().lower() == "true"

# --- Configuration-Driven Vendor Details ---

# Global band mapping (vendor agnostic)
BAND_MAPPING = {
    "n29": "LB", "n71": "LB",
    "n66": "MB", "n70": "MB"
}

VENDOR_CONFIGS = {
    "mavenir": {
        "ret_update": {
            "table_name": "DISH_MNO_OUTBOUND.GENAI_APP.MCMS_CM_RET_STATE",
            "cell_col": "CELLNAME",
            "unique_combo_cols": ["CELLNAME", "HDLC_ADDRESS","TILT"],
            "display_cols": ["CELLNAME", "TILT", "HDLC_ADDRESS","MINIMUMTILT", "MAXIMUMTILT",  "ANTENNAMODEL", "AOI", "LAST_FILE_RECEIVED_TIMESTAMP"],
            "timestamp_col": "LAST_FILE_RECEIVED_TIMESTAMP",
            "param_to_col_map": {
                "hdlc_address": "HDLC_ADDRESS", "port": "PORT", "ruid": "RUID",
                "antenna_unit": "ANTENNA_UNIT", "ip": "IP", "antennamodel": "ANTENNAMODEL",
                "aoi": "AOI", "minimumtilt":"MINIMUMTILT", "maximumtilt":"MAXIMUMTILT"
            }
        }
    },
    "samsung": {
        "ret_update": {
            "table_name": "DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_RET_STATE",
            "cell_col": "CELLNAME",
            "unique_combo_cols": ["CELLNAME", "ALDID","TILT"],
            "display_cols": ["CELLNAME", "TILT", "ALDID", "MINIMUMTILT", "MAXIMUMTILT","ANTENNAMODEL", "AOI", "LAST_FILE_RECEIVED_TIMESTAMP"],
            "timestamp_col": "LAST_FILE_RECEIVED_TIMESTAMP",
            "param_to_col_map": {
                "usmip": "USMIP", "duid": "DUID", "aldid": "ALDID", "ruid": "RUID",
                "antennaid": "ANTENNAID", "antennamodel": "ANTENNAMODEL", "aoi": "AOI",
                "minimumtilt":"MINIMUMTILT", "maximumtilt":"MAXIMUMTILT"
            }
        },
        "classc_update": {
            "table_name": "DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_CONFIG_CUCP_PARAMETERS",
            "cell_col": "CELL_NAME",
            "unique_combo_cols": ["CELL_NAME", "GNODEB_ID", "CELL_IDENTITY", "BAND", "REPORT_CONFIG_ENTRY_INDEX"],
            # Defines parameters that can be used to filter the dataset
            "filterable_params": [
                "gnodeb_id", "cell_identity", "cucp_id", "du_id", 
                "report_config_entry_index", "ssb_config_ssb_freq", "purpose", "band"
            ],
            "display_cols": ["CELL_NAME", "REPORT_TYPE", "GNODEB_ID", "REPORT_CONFIG_ENTRY_INDEX", "PURPOSE", "DL_LOAD_TIME"],
            "timestamp_col": "DL_LOAD_TIME",
            "param_to_col_map": {
                # Filtering parameters
                "gnodeb_id": "GNODEB_ID", "cell_identity": "CELL_IDENTITY", "cucp_id": "CUCP_ID",
                "du_id": "DU_ID", "report_config_entry_index": "REPORT_CONFIG_ENTRY_INDEX",
                "ssb_config_ssb_freq": "SSB_CONFIG_SSB_FREQ", "purpose": "PURPOSE","band":"BAND",
                # Event-specific parameters
                "trigger_quantity": "THRESHOLD_SELECTION_TRIGGER_QUANTITY",
                "threshold_rsrp": "THRESHOLD_RSRP",
                "hysteresis": "HYSTERESIS",
                "time_to_trigger": "TIME_TO_TRIGGER",
                "offset_rsrp": "A3_OFFSET_RSRP",
                "threshold1_rsrp": "THRESHOLD1_RSRP",
                "threshold2_rsrp": "THRESHOLD2_RSRP",
                "report_type": "REPORT_TYPE"
            }
        }
    }
}

EVENT_TYPE_CONFIGS = {
    "a1": ["trigger_quantity", "threshold_rsrp", "hysteresis", "time_to_trigger"],
    "a2": ["trigger_quantity", "threshold_rsrp", "hysteresis", "time_to_trigger"],
    "a3": ["trigger_quantity", "offset_rsrp", "hysteresis", "time_to_trigger"],
    "a4": ["trigger_quantity", "threshold_rsrp", "hysteresis", "time_to_trigger"],
    "a5": ["trigger_quantity", "threshold1_rsrp", "threshold2_rsrp", "hysteresis", "time_to_trigger"],
}

# --- Internal Helper Functions ---

def _parse_cellname(cellname: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parses a cell name using regex to reliably extract site, sector, and band."""
    if not cellname: return None, None, None
    # Regex to capture site (alphanumeric), sector (numeric), and band (starts with 'n' followed by numbers)
    match = re.match(r"^(?P<site>[A-Z0-9]+)_(?P<sector>\d+)_(?P<band>n\d+)", cellname)
    if match:
        parts = match.groupdict()
        return parts.get("site"), parts.get("sector"), parts.get("band")
    # Fallback for other formats
    parts = cellname.split("_")
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    return None, None, None

def _get_column_value(row: Dict[str, Any], column_name: str) -> Any:
    """Gets a value from a row, trying various case formats for the key."""
    for key in [column_name, column_name.upper(), column_name.lower(), column_name.title()]:
        if key in row: return row[key]
    return None

def _compare_values(val1: Any, val2: Any) -> bool:
    """Compares two values for equality, handling potential type mismatches (e.g., "3" == 3.0)."""
    if val1 is None and val2 is None:
        return True
    if val1 is None or val2 is None:
        return False
    try:
        # Attempt numeric comparison first
        if float(val1) == float(val2):
            return True
    except (ValueError, TypeError):
        # Fallback to case-insensitive string comparison if numeric conversion fails
        pass
    return str(val1).lower() == str(val2).lower()

# def _validate_ret_params(target_tilt: Optional[str], current_tilt: Any, min_tilt: Any, max_tilt: Any) -> tuple[bool, Optional[str]]:
#     """Validates the target tilt."""
#     if not target_tilt: return True, "Validation skipped: no target_tilt provided."
#     try:
#         target_f, current_f = float(target_tilt), float(current_tilt)
#         min_f, max_f = float(min_tilt), float(max_tilt)
#         if abs(target_f - current_f) < 0.001:
#             return True, f"Informational: Target tilt ({target_tilt}) is the same as the current value ({current_tilt}) in the database."
#         if not (min_f <= target_f <= max_f): return False, f"Target tilt ({target_tilt}) outside allowed range ({min_tilt} to {max_tilt})."
#         return True, None
#     except (ValueError, TypeError, AttributeError):
#         return False, "Invalid tilt value provided. Ensure target, current, min, and max tilts are valid numbers."
def adjust_tilt(value: float) -> float:
    """
    Adjust tilt value for Samsung vendor.
    If value is in EMS format (-9.999... to 9.999...), convert to degrees by multiplying by 10.
    If value is already in degrees (<= -10 or >= 10), return as is.
    """
    if -10 < value < 10:
        return value * 10  # Convert EMS to degrees
    return value  # Already in degrees

def _validate_ret_params(vendor: Optional[str], target_tilt: Optional[str], current_tilt: Any, min_tilt: Any, max_tilt: Any) -> tuple[bool, Optional[str]]:
    """
    Validates the target tilt against current/min/max values.
    Handles negative values, swapped min/max ranges, and floating-point precision.
    Args:
        target_tilt: Desired tilt value to validate (string or None)
        current_tilt: Current tilt value in the system
        min_tilt: Minimum allowed tilt value (can be greater than max_tilt)
        max_tilt: Maximum allowed tilt value (can be less than min_tilt)
    Returns:
        Tuple of (is_valid: bool, message: Optional[str])
    """
    if not target_tilt:
        return True, "Validation skipped: no target_tilt provided."

    conversion_note = ""  # Will store conversion information if needed
    try:
        if vendor == 'samsung':
            # Convert to float first to check if it's in EMS format
            target_orig = float(target_tilt)
            current_orig = float(current_tilt)
            min_orig = float(min_tilt)
            max_orig = float(max_tilt)

            # Adjust values to degrees
            target_f = adjust_tilt(target_orig)
            current_f = adjust_tilt(current_orig)
            min_f = adjust_tilt(min_orig)
            max_f = adjust_tilt(max_orig)

            # Check if target was in EMS format
            if -10 < target_orig < 10:
                conversion_note = " *(converted from Degrees to EMS)*"
        else:
            # For non-Samsung vendors, convert all values to float without adjustment
            target_f = float(target_tilt)
            current_f = float(current_tilt)
            min_f = float(min_tilt)
            max_f = float(max_tilt)

        # Check if target matches current value (within floating-point tolerance)
        if abs(target_f - current_f) < 0.001:
            return True, (
                f"Informational: Target tilt {target_tilt}{conversion_note} is the same as the current value ({current_tilt}) in the database."
            )

        # Determine true bounds (handles swapped min/max and negative values)
        low_bound = min(min_f, max_f)  # True minimum allowed value
        high_bound = max(min_f, max_f)  # True maximum allowed value

        # Validate target is within the calculated bounds
        if not (low_bound <= target_f <= high_bound):
            return False, (
                f"Target tilt ({target_tilt}){conversion_note} outside allowed range "
                f"({low_bound} to {high_bound})"
            )
        return True, None
    except (ValueError, TypeError, AttributeError):
        return False, (
            "Invalid tilt value. Ensure target, current, min, and max tilts "
            "are valid numbers (including negatives)."
        )
async def _validate_classc_params(provided_config_params: Dict[str, Any], row: Dict[str, Any], param_map: Dict[str, str]) -> tuple[bool, Optional[str], Optional[dict]]:
    """Validates that target Class C parameters are not the same as current values and calls external validation only for changed parameters."""

    # First, check which parameters are different from current values
    changed_params = {}
    unchanged_params = {}
    info_messages = []
    validation_result = {}

    for param, target_value in provided_config_params.items():
        column_name = param_map.get(param, param)
        db_value = _get_column_value(row, column_name)

        if _compare_values(db_value, target_value):
            # Parameter is the same as current value
            unchanged_params[param] = target_value
            info_messages.append(f"Parameter '{param}' target value ('{target_value}') is the same as the current value ('{db_value}').")
        else:
            # Parameter is different from current value
            changed_params[param] = target_value

    # Only call validate_params if there are parameters to validate
    if changed_params:
        logger.info("Change params detected....")
        info_messages = None
        # Prepare parameters for the external validation call
        # Only include parameters that are changing
        validation_request = ValidateParamsRequest(
            table_type="GNB",
            vendor="samsung",
            transaction_id="validation",  # Using a placeholder since no transaction_id is available
            gnb=row.get('gnodeb_id'),
            threshold_rsrp=changed_params.get('threshold_rsrp'),
            hysteresis=changed_params.get('hysteresis'),
            time_to_trigger=changed_params.get('time_to_trigger'),
            index=row.get('report_config_entry_index'),
            event=row.get('report_type'),  # Using report_type as event
            cell_name=row.get('cell_name'),
            cell_id = row.get('cell_identity'),
            trigger_quantity=changed_params.get('trigger_quantity'),
            band=row.get('band'),
            threshold2_rsrp=changed_params.get('threshold2_rsrp'),
            threshold1_rsrp=changed_params.get('threshold1_rsrp'),
            offset=changed_params.get('offset_rsrp'),  # Map offset_rsrp to offset
            purpose=row.get('purpose'),
            frequency=row.get('ssb_config_ssb_freq'),
            re_validate="Y"
        )

        try:
            validation_result = await validate_params(validation_request)

            # Check if validation failed
            if validation_result.get('status') == "fail":
                # Format the error message
                error_message = validation_result.get('message', 'Validation failed')

                # Add dish_recommendation_table if present
                if validation_result.get('dish_recommendation_table'):
                    error_message += f"\n\nRecommendation Table:\n{validation_result['dish_recommendation_table']}"

                return False, error_message, None

            # If validation passed, continue to check for unchanged parameters
        except Exception as e:
            return False, f"Error during external validation: {str(e)}", None

    # If we have informational messages about unchanged parameters, include them
    if info_messages:
        full_info_message = "Informational: " + " ".join(info_messages) + " Please review and confirm if you want to proceed with the operation."
        # Add dish_recommendation_table if present
        if validation_result.get('dish_recommendation_table'):
            return True, full_info_message, validation_result.get('dish_recommendation_table')
        return True, full_info_message, None

    return True, None, validation_result.get('dish_recommendation_table')

async def _fetch_ran_vendor(node_type: str, node_identifier: str) -> Dict[str, Any]:
    """Internal function to identify the RAN vendor."""
    vendor_url = CONST.RAN_MCP_API_VENDOR_URL
    if not vendor_url: return {"error": "RAN_MCP_API_VENDOR_URL environment variable not set."}
    if not vendor_url.startswith("http"): vendor_url = "https://" + vendor_url
    
    payload = {"node_type": node_type, "node_identifier": node_identifier}
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(vendor_url, json=payload, headers=headers, ssl=False) as resp:
                if resp.status != 200: return {"error": f"API request failed with status {resp.status}: {await resp.text()}"}
                return await resp.json()
    except Exception as e:
        return {"error": f"An unexpected error occurred during vendor fetch: {str(e)}"}

async def _filter_by_band(data: List[Dict[str, Any]], band: Optional[str], cell_col_name: str) -> List[Dict[str, Any]]:
    """Filters data based on band, extracted from a cell name column."""
    if not data:
        return data
    
    # If no band is provided, extract band from cell names and apply mapping
    if not band:
        # Extract bands from all cell names and determine the mapped band category
        extracted_bands = set()
        for row in data:
            cell_name = str(_get_column_value(row, cell_col_name) or "")
            _, _, parsed_band = _parse_cellname(cell_name)
            if parsed_band:
                mapped_band = BAND_MAPPING.get(parsed_band.lower())
                if mapped_band:
                    extracted_bands.add(mapped_band)
        
        # If we found multiple different mapped bands (LB and MB), return all data
        if len(extracted_bands) > 1:
            return data
        
        # If we found exactly one mapped band category, use it for filtering
        if len(extracted_bands) == 1:
            band = list(extracted_bands)[0]
        else:
            # No recognizable bands found, return data as-is
            return data
    
    band_upper = band.upper()
    if band_upper in ("LB", "MB"):
        return await extract_band_identifier(band_upper, data)
    else:
        # For specific bands (n29, n66, etc.), use direct filtering
        allowed_bands = [band_upper.lower()]
        
        # If this is a mapped band, get all bands that map to it
        allowed_bands = [b for b, mapped in BAND_MAPPING.items() if mapped.upper() == band_upper]
        if not allowed_bands:
            allowed_bands = [band_upper.lower()]
        
        filtered_data = []
        for row in data:
            cell_name = str(_get_column_value(row, cell_col_name) or "")
            _, _, parsed_band = _parse_cellname(cell_name)
            if parsed_band and parsed_band.lower() in allowed_bands:
                filtered_data.append(row)
        return filtered_data

async def _filter_by_sector(data: List[Dict[str, Any]], sector: Optional[str], cell_col_name: str) -> List[Dict[str, Any]]:
    """Filters data based on sector, extracted from a cell name column."""
    logger.info(f"Sector From Input ::{sector}")
    if not sector:
        return data

    filtered_data = []
    for row in data:
        cell_name = str(_get_column_value(row, cell_col_name) or "")
        _, parsed_sector, _ = _parse_cellname(cell_name)
        # Use the typesafe compare function to handle potential type mismatches (e.g., '3' vs 3)
        if parsed_sector and _compare_values(parsed_sector, sector):
            filtered_data.append(row)
    return filtered_data

def group_and_sort_cells(data, cell_name_key):
    """
    Sorts cells by sector only if all sectors are 1, 2, or 3.
    Otherwise returns the original data unchanged.

    Args:
        data: List of dictionaries containing cell information
        cell_name_key: The key in the dictionaries that contains the cell name

    Returns:
        List of dictionaries sorted by sector (1, 2, 3) or original data if any sector is invalid
    """
    if not data:
        return []

    valid_sectors = {'1', '2', '3'}
    all_valid = True

    # First pass: check if all sectors are valid
    for item in data:
        cell_name = item.get(cell_name_key, "")
        parts = cell_name.split('_')

        # Need at least 2 parts to have a sector
        if len(parts) < 2:
            all_valid = False
            break

        sector_str = parts[1]
        if sector_str not in valid_sectors:
            all_valid = False
            break

    # If any sector is invalid, return original data
    if not all_valid:
        return data

    # All sectors are valid - sort by sector numerically
    return sorted(data, key=lambda x: int(x[cell_name_key].split('_')[1]))

class NonIntegerTiltError(ValueError):
    """Custom exception for non-integer tilt values."""
    pass

def adjust_tilt_samsung(value: float) -> int:
    """
    Adjust tilt value for Samsung vendor.
    If value is in EMS format (-9.999... to 9.999...), convert to degrees by multiplying by 10.
    If value is already in degrees (<= -10 or >= 10), return as integer.
    Raises ValueError if the value cannot be converted to an integer.
    """
    if -10 < value < 10:  # EMS format range
        converted_value = value * 10  # Convert to degrees
        if converted_value.is_integer():
            return int(converted_value)
        raise NonIntegerTiltError(f"EMS value {value} converts to non-integer degrees: {converted_value}. Note for Samsung Degrees must be an internet value")
    else:  # Already in degrees
        if value.is_integer():
            return int(value)
        raise NonIntegerTiltError(f"Degrees value {value} is not an integer. Note for Samsung Degrees must be an internet value")

import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def _update_ret_value(thread_id: str,**kwargs: Any) -> Dict[str, Any]:
    """Internal function to update RET values on the network."""
    logger.info("Starting RET value update process")
    logger.info(f"Received kwargs for RET update: {kwargs}")

    # Extract common parameters
    vendor = kwargs.get("vendor")
    cell_name = kwargs.get("cellname") or kwargs.get("cell_name")
    target_tilt = kwargs.get("target_tilt")

    # Validate vendor
    if not vendor:
        logger.error("Vendor is missing")
        return {"status": "error", "message": "Vendor is a mandatory parameter for update."}

    # Get vendor configuration
    config = VENDOR_CONFIGS.get(str(vendor).lower(), {}).get("ret_update")
    if not config:
        logger.error(f"No configuration found for vendor: {vendor}")
        return {"status": "error", "message": f"No update configuration found for vendor: {vendor}"}

    # Validate cell name
    if not cell_name:
        logger.error("Cell name is missing")
        return {"status": "error", "message": f"Missing required parameter for {vendor} update: cell_name."}

    # Validate required parameters
    required_params = config["unique_combo_cols"]
    missing_params = [p for p in required_params if kwargs.get(p.lower()) is None]
    if missing_params:
        logger.error(f"Missing required parameters: {missing_params}")
        return {"status": "error", "message": f"Missing required parameters for {vendor} update: {', '.join(missing_params)}."}

    if vendor.lower() == 'samsung':
        target_tilt = adjust_tilt_samsung(float(target_tilt))

    logger.info(f"Processing RET update for vendor: {vendor}, cell: {cell_name}, target_tilt: {target_tilt}")

    if ACTUAL_NETWORK_CALL_FLAG:
        logger.info("Executing actual network call")
        try:
            # Get user ID
            user_id = await get_user_from_thread(thread_id)
            if not user_id:
                logger.error("User ID is missing")
                return {"status": "error", "message": "User Id is mandatory"}

            # Prepare request parameters
            request_params = {
                "table_type": "RET",
                "vendor": vendor,
                "transaction_id": thread_id,
                "user_id": user_id,
                "token": None,
                "cell_id": cell_name,
                "tilt_value": target_tilt
            }

            # Add vendor-specific parameters
            vendor_param_map = {
                "mavenir": {
                    "antenna_model": "antennamodel",
                    "hldc_address": "hdlc_address"
                },
                "samsung": {
                    "antenna_model": "antennamodel",
                    "aldid": "aldid"
                }
            }

            vendor_params = vendor_param_map.get(vendor.lower(), {})
            for param_name, kwarg_name in vendor_params.items():
                if kwarg_name in kwargs and kwargs[kwarg_name] is not None:
                    request_params[param_name] = kwargs[kwarg_name]
                    logger.info(f"Added vendor parameter: {param_name} = {kwargs[kwarg_name]}")

            # Convert all non-None values to strings (preserve None values)
            request_params = {
                key: str(value) if value is not None else None
                for key, value in request_params.items()
            }

            logger.info(f"Sending update request to network with following parameters : {request_params} ")
            # Create and process request
            request_model = UploadRETParamsRequest(**request_params)
            response = await process_csv(request_model)

            logger.info("Successfully received response from network")
            return {"status": "success", "data": response}

        except Exception as e:
            logger.error(f"Error during network call: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    else:
        logger.info("Executing simulated update")
        # Simulate the update
        print(f"SIMULATION: Updating RET tilt for {vendor} cell {cell_name} to {target_tilt}")
        response = {
            "status": "success",
            "message": f"Successfully simulated RET tilt update for cell {cell_name} to {target_tilt}.",
            "cell_name": cell_name,
            "vendor": vendor,
            "target_tilt": target_tilt,
        }

        # Include the unique identifiers in the response
        for param in required_params:
            response[param.lower()] = kwargs.get(param.lower())

        logger.info("Simulation completed successfully")
        return response

async def _update_classc_params(thread_id, **kwargs: Any) -> Dict[str, Any]:
    """Internal function to update Class C parameters on the network."""
    logger.info("Starting Class C parameters update process")
    logger.info(f"Received kwargs for Class C update: {kwargs}")
    # Extract common parameters
    cell_name = kwargs.get("cell_name") or kwargs.get("cellname")
    event_type = kwargs.get("event_type")
    vendor = kwargs.get("vendor")
    # Validate required parameters
    if not cell_name:
        logger.error("Cell name is missing")
        return {"error": "cell_name is mandatory for update."}
    if not event_type:
        logger.error("Event type is missing")
        return {"error": "event_type is mandatory for update."}
    logger.info(f"Processing Class C update for cell: {cell_name}, event: {event_type}, default vendor: Samsung")
    if ACTUAL_NETWORK_CALL_FLAG:
        logger.info("Executing actual network call")
        try:
            # Get user ID
            user_id = await get_user_from_thread(thread_id)
            if not user_id:
                logger.error("User ID is missing")
                return {"status": "error", "message": "User Id is mandatory"}
            # Define parameters that need change detection
            # These are the parameters from UploadRETParamsRequest that need change detection
            change_detection_params = {
                "threshold_rsrp": "threshold_rsrp",
                "hysteresis": "hysteresis",
                "trigger_quantity": "threshold_selection_trigger_quantity",  # kwargs key -> db column
                "time_to_trigger": "time_to_trigger",
                "threshold1_rsrp": "threshold1_rsrp",
                "threshold2_rsrp": "threshold2_rsrp",
                "offset": "a3_offset_rsrp"  # Changed to match actual database column
            }
            # Fetch current data from database
            current_records = await gnb_validate_util.get_data_by_cell_id_node_id_revalidate(
                kwargs.get("cell_identity"),  # cell_id
                cell_name,                    # cell_name
                kwargs.get("gnodeb_id"),      # gnb
                kwargs.get("band"),           # band
                kwargs.get("purpose"),        # purpose
                kwargs.get("ssb_config_ssb_freq"),      # frequency
                kwargs.get("report_config_entry_index"),  # index
                "samsung"                     # vendor
            )
            if not current_records:
                logger.error("No current record found for the given identifiers")
                return {"status": "error", "message": "No current record found"}
            if len(current_records) > 1:
                logger.warning(f"Multiple records found ({len(current_records)}), using the first one")
            current_record = current_records[0]
            logger.info(f"Current record data: {current_record}")
            # Prepare base parameters for the request model
            request_params = {
                "table_type": "GNB",
                "vendor": "samsung",
                "transaction_id": thread_id,
                "user_id": user_id,
                "token": None,
                "event": event_type,
                "cell_name": cell_name,
                "cell_id": kwargs.get("cell_identity")
            }
            # Check for changes and add only changed parameters to request
            params_changed = False
            updated_params = {}
            for request_field, db_column_pattern in change_detection_params.items():
                # Check if this parameter is provided in kwargs
                if request_field in kwargs and kwargs[request_field] is not None:
                    new_value = kwargs[request_field]
                    # Handle contains pattern for flexible column matching
                    if db_column_pattern.startswith("contains:"):
                        search_pattern = db_column_pattern.replace("contains:", "")
                        # Find the actual column name that contains the pattern
                        db_column = None
                        current_value = None
                        for col_name, col_value in current_record.items():
                            if search_pattern.lower() in col_name.lower():
                                db_column = col_name
                                current_value = col_value
                                logger.info(f"Found matching column for {request_field}: {col_name}")
                                break
                        if db_column is None:
                            logger.warning(f"No column found containing '{search_pattern}' for parameter {request_field}")
                            continue
                    else:
                        # Direct column name mapping
                        db_column = db_column_pattern
                        current_value = current_record.get(db_column)
                    # Normalize values for comparison
                    current_normalized = normalize_value_for_comparison(current_value)
                    new_normalized = normalize_value_for_comparison(new_value)
                    # Only add to request if value has changed
                    if current_normalized != new_normalized:
                        request_params[request_field] = str(new_value)
                        updated_params[request_field] = str(new_value)
                        params_changed = True
                        logger.info(f"Parameter {request_field} (column: {db_column}) changed: {current_normalized} -> {new_normalized}")
                    else:
                        logger.info(f"Parameter {request_field} (column: {db_column}) unchanged: {current_normalized}")
                # Special handling for trigger_quantity - check if it's provided as threshold_selection_trigger_quantity
                elif request_field == "trigger_quantity" and "threshold_selection_trigger_quantity" in kwargs:
                    new_value = kwargs["threshold_selection_trigger_quantity"]
                    if new_value is not None:
                        db_column = db_column_pattern
                        current_value = current_record.get(db_column)
                        current_normalized = normalize_value_for_comparison(current_value)
                        new_normalized = normalize_value_for_comparison(new_value)
                        if current_normalized != new_normalized:
                            request_params[request_field] = str(new_value)
                            updated_params[request_field] = str(new_value)
                            params_changed = True
                            logger.info(f"Parameter {request_field} (from threshold_selection_trigger_quantity, column: {db_column}) changed: {current_normalized} -> {new_normalized}")
                        else:
                            logger.info(f"Parameter {request_field} (from threshold_selection_trigger_quantity, column: {db_column}) unchanged: {current_normalized}")
                # Special handling for offset - check if it's provided as offset_rsrp
                elif request_field == "offset" and "offset_rsrp" in kwargs:
                    new_value = kwargs["offset_rsrp"]
                    if new_value is not None:
                        # Use the actual database column name from the mapping
                        db_column = db_column_pattern  # This is now "a3_offset_rsrp"
                        current_value = current_record.get(db_column)
                        current_normalized = normalize_value_for_comparison(current_value)
                        new_normalized = normalize_value_for_comparison(new_value)
                        if current_normalized != new_normalized:
                            request_params[request_field] = str(new_value)
                            updated_params[request_field] = str(new_value)
                            params_changed = True
                            logger.info(f"Parameter {request_field} (from offset_rsrp, column: {db_column}) changed: {current_normalized} -> {new_normalized}")
                        else:
                            logger.info(f"Parameter {request_field} (from offset_rsrp, column: {db_column}) unchanged: {current_normalized}")

            # Special case: If no parameters changed, include all provided parameters
            if not params_changed:
                logger.info("No parameters changed, including all provided parameters for the network call")
                for request_field, db_column_pattern in change_detection_params.items():
                    # Check if this parameter is provided in kwargs
                    if request_field in kwargs and kwargs[request_field] is not None:
                        new_value = kwargs[request_field]
                        request_params[request_field] = str(new_value)
                        updated_params[request_field] = str(new_value)
                        logger.info(f"Parameter {request_field} (no change detected, but provided) included: {new_value}")
                    # Special handling for trigger_quantity
                    elif request_field == "trigger_quantity" and "threshold_selection_trigger_quantity" in kwargs:
                        new_value = kwargs["threshold_selection_trigger_quantity"]
                        if new_value is not None:
                            request_params[request_field] = str(new_value)
                            updated_params[request_field] = str(new_value)
                            logger.info(f"Parameter {request_field} (from threshold_selection_trigger_quantity, no change detected) included: {new_value}")
                    # Special handling for offset
                    elif request_field == "offset" and "offset_rsrp" in kwargs:
                        new_value = kwargs["offset_rsrp"]
                        if new_value is not None:
                            request_params[request_field] = str(new_value)
                            updated_params[request_field] = str(new_value)
                            logger.info(f"Parameter {request_field} (from offset_rsrp, no change detected) included: {new_value}")

            # Map additional parameters (no change detection needed - these are identifiers/metadata)
            additional_param_mapping = {
                "gnodeb_id": "gnb",
                "cucp_id": "cucp_id",
                "du_id": "du_id",
                "report_config_entry_index": "index",
                "ssb_config_ssb_freq": "frequency",
                "purpose": "purpose",
                "band": "band",
                "aoi": "aoi",
                "ip": "ip",
                "frequency": "frequency"
            }
            for param, field_name in additional_param_mapping.items():
                if param in kwargs and kwargs[param] is not None:
                    request_params[field_name] = str(kwargs[param])
                    logger.debug(f"Mapped additional parameter: {param} -> {field_name} = {kwargs[param]}")
            logger.info(f"Final request parameters: {request_params}")
            logger.info(f"Parameters being updated: {updated_params}")
            # Create and process request
            request_model = UploadRETParamsRequest(**request_params)
            response = await process_csv(request_model)
            logger.info("Successfully received response from network")
            return {
                "status": "success",
                "data": response
            }
        except Exception as e:
            logger.error(f"Error during network call: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
    else:
        logger.info("Executing simulated update")
        # Extract event-specific parameters
        event_params = EVENT_TYPE_CONFIGS.get(str(event_type).lower(), [])
        # Create mappings between parameter names and database column names
        param_map = VENDOR_CONFIGS["samsung"]["classc_update"]["param_to_col_map"]
        # Extract parameters to change using database column names
        params_to_change = {}
        for param in event_params:
            # Get the database column name for this parameter
            db_column = param_map.get(param, "").lower()
            if db_column in kwargs and kwargs[db_column] is not None:
                params_to_change[db_column] = kwargs[db_column]
            # Also check if the parameter name itself is in kwargs
            elif param in kwargs and kwargs[param] is not None:
                params_to_change[param] = kwargs[param]
        if not params_to_change:
            logger.error("No parameters to update in simulation")
            return {"error": "No valid parameters provided for update."}
        logger.info(f"Simulating update with parameters: {params_to_change}")
        # Create simulation response
        response = {
            "status": "success",
            "message": f"Successfully simulated Class C update for cell {cell_name}.",
            "updated_params": params_to_change
        }
        # Include all original parameters for context
        response.update({k.lower(): v for k, v in kwargs.items()})
        logger.info("Simulation completed successfully")
        return response


def normalize_value_for_comparison(value):
    """Normalize a value for proper comparison across different data types"""
    if value is None:
        return None

    # Handle boolean values
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower_val = value.lower()
        if lower_val in ('true', 'yes', '1'):
            return True
        elif lower_val in ('false', 'no', '0'):
            return False

    # Handle numeric values
    try:
        # Try integer first
        return int(value)
    except (ValueError, TypeError):
        try:
            # Try float if integer fails
            return float(value)
        except (ValueError, TypeError):
            pass

    # Handle datetime objects
    if isinstance(value, datetime.datetime):
        return value.isoformat()

    # Return as string for everything else
    return str(value).strip()

async def _filter_null_data(data, columns_to_check=None):
    """
    Filter rows that contain null values in specified columns.

    Args:
        data: List of dictionaries representing data rows
        columns_to_check: List of column names to check for null values.
                         If None, check all columns.

    Returns:
        Tuple of (filtered_data, columns_with_nulls)
        where filtered_data is the data with rows containing nulls removed,
        and columns_with_nulls is a list of columns that had null values
    """
    if not data:
        return data, []

    # If no specific columns to check, use all columns from first row
    if columns_to_check is None:
        columns_to_check = list(data[0].keys())

    filtered_data = []
    columns_with_nulls = set()

    for row in data:
        has_null = False
        for col in columns_to_check:
            value = _get_column_value(row, col)
            if value is None:
                columns_with_nulls.add(col)
                has_null = True
                break  # Found a null in this row, no need to check other columns

        if not has_null:
            filtered_data.append(row)

    return filtered_data, list(columns_with_nulls)


# --- Main Agent Tools ---

@tool
async def handle_ret_update(
        operation: str,
        site_name: Optional[str] = None, cell_name: Optional[str] = None, vendor: Optional[str] = None,
        band: Optional[str] = None, sector: Optional[str] = None, target_tilt: Optional[str] = None,
        # Vendor-specific optional params
        hdlc_address: Optional[str] = None, port: Optional[str] = None, ip: Optional[str] = None,
        usmip: Optional[str] = None, duid: Optional[str] = None, aldid: Optional[str] = None,
        ruid: Optional[str] = None, antennaid: Optional[str] = None, antennamodel: Optional[str] = None,
        aoi: Optional[str] = None,
        config: RunnableConfig = None,
) -> List[Dict[str, Any]]:
    """
    Use this tool to validate or update the Remote Electrical Tilt (RET) value for a cell.
    Mandatory args: 'operation' and either 'site_name' Example:(BOBOS01075F)/(BOBOS01075F_1) or 'cell_name' (BOBOS01075F_1_n71_F-G).
    'operation' must be 'validate' or 'update'.
    'band' argument will Contain `LB` or `MB` for Low band or Mid band respectively if user has mentioned.
    Use 'validate' to find and check a unique cell and validate the parameters.
    Use 'update' to perform the change once the validation is done and the user confirms the parameters.
    All other parameters are optional and used to filter for a unique cell.
    """
    try:
        #Fetching thread Id
        thread_id = None
        if config and config.get("metadata") and config.get("metadata").get("thread_id"):
            logger.info(f"Thread identified: {config.get('metadata').get('thread_id')}")
            thread_id = config.get("metadata").get("thread_id")
            user_id = await get_user_from_thread(thread_id)
            logger.info(f"User ID: {user_id}")

        # 1. Initial Validation
        operation = operation.lower()
        if operation not in ['validate', 'update']:
            return [{"error": f"Invalid operation '{operation}'. Must be 'validate' or 'update'."}]
        if not site_name and not cell_name:
            return [{"error": "Either site_name or cell_name must be provided."}]

        # 2. Determine Vendor and Configuration
        vendor_lookup_result = None
        exact_vendor = None
        try:
            if not vendor:
                node_type = "CELL" if cell_name else "SITE"
                node_identifier = cell_name or site_name
                vendor_lookup_result = await _fetch_ran_vendor(node_type, node_identifier)
                if vendor_lookup_result.get("error"):
                    return [{"error": f"Vendor lookup failed: {vendor_lookup_result['error']}"}]

                if vendor_lookup_result and vendor_lookup_result.get("vendor") and len(vendor_lookup_result.get("vendor")):
                    exact_vendor =  vendor_lookup_result.get("vendor")[0]

                vendor = exact_vendor or vendor_lookup_result.get("nearest_match_vendor")
                if not vendor:
                    return [{"error": f"Vendor lookup failed: {vendor_lookup_result.get('tool_message') or 'Could not identify vendor.'}"}]
                logger.info(f"Dynamically identified vendor: {vendor}")
            else:
                # User provided a vendor, validate it against the lookup
                node_type = "CELL" if cell_name else "SITE"
                node_identifier = cell_name or site_name
                vendor_lookup_result = await _fetch_ran_vendor(node_type, node_identifier)

                if vendor_lookup_result.get("error"):
                    # If lookup fails, use the provided vendor
                    logger.warning(f"Vendor lookup failed, using provided vendor: {vendor}")
                else:
                    if vendor_lookup_result and vendor_lookup_result.get("vendor") and len(vendor_lookup_result.get("vendor")):
                        exact_vendor =  vendor_lookup_result.get("vendor")[0]

                    looked_up_vendor = exact_vendor or vendor_lookup_result.get("nearest_match_vendor")
                    if looked_up_vendor and looked_up_vendor.lower() != vendor.lower():
                        return [{"tool_message": f"Vendor mismatch. You specified '{vendor}' but the system identified '{looked_up_vendor}' for this cell/site. Please provide correct vendor or dont specify and let the system identify the vendor."}]

                    logger.info(f"Vendor validation successful: {vendor}")
        except Exception as vendor_error:
            logger.error(f"Vendor determination error: {str(vendor_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to determine vendor configuration. Please try again later."}]

        try:
            config = VENDOR_CONFIGS.get(vendor.lower(), {}).get("ret_update")
            if not config:
                return [{"error": f"Vendor '{vendor}' is not supported for RET updates. Supported vendors are: {list(VENDOR_CONFIGS.keys())}"}]
        except Exception as config_error:
            logger.error(f"Configuration error: {str(config_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to load vendor configuration. Please contact support."}]

        # 3. Database Query
        table_name = config["table_name"]
        query_val = (cell_name or site_name or '').upper() + '%'
        query = text(f"SELECT * FROM {table_name} WHERE CELLNAME ILIKE :val")
        try:
            async with snow_db.get_db_session() as session:
                try:
                    result = await asyncio.to_thread(session.execute, query, {"val": query_val})
                    data = [dict(zip(result.keys(), row)) for row in result.fetchall()]
                    print(data)
                    if data:
                        # Apply grouping and sorting55
                        data = group_and_sort_cells(data, "cellname")

                except Exception as db_error:
                    logger.error(f"Database execution error: {str(db_error)}")
                    logger.error(traceback.format_exc())
                    return [{"error": "Database query failed. Please try again later."}]
        except Exception as session_error:
            logger.error(f"Database session error: {str(session_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to establish database connection. Please try again later."}]

        if not data:
            return [{"tool_message": "No matching record found in the database."}]

        # 4. Dynamic Filtering
        try:
            all_params = locals()
            # Direct column filters from config
            for param_name, col_name in config["param_to_col_map"].items():
                if all_params.get(param_name) is not None:
                    param_value = all_params[param_name]
                    # Filter data in place using the robust, centralized comparison function
                    data = [
                        row for row in data
                        if _compare_values(_get_column_value(row, col_name), param_value)
                    ]

            # Filter rows containing null values
            data, columns_with_nulls = await _filter_null_data(data)
            logger.info(f"Data extracted from snow :: {data}")

            # Special filters parsed from cellname
            data = await _filter_by_band(data, band, config["cell_col"])
            if not data:
                return [{"tool_message": "No matching records found after band filtering."}]

            # Filter by sector
            data = await _filter_by_sector(data, sector, config["cell_col"])
            if not data:
                return [{"tool_message": "No matching records found after sector filtering."}]
        except Exception as filter_error:
            logger.error(f"Data filtering error: {str(filter_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to filter data. Please check your parameters and try again."}]

        # 5. Process Results
        try:
            if not data:
                return [{"tool_message": "No matching entry found after applying all criteria."}]

            # Handle Multiple Results
            if len(data) > 1:
                unique_combo_cols = config["unique_combo_cols"]
                # De-duplicate based on the unique combination of columns
                unique_combinations_map = {
                    "_".join(str(_get_column_value(r, col) or '') for col in unique_combo_cols): r
                    for r in data
                }
                unique_rows = list(unique_combinations_map.values())
                # Create a list of dictionaries for the unique options
                unique_options = []
                timestamp_col = config.get("timestamp_col")
                for i, row in enumerate(unique_rows, 1):
                    option = {"option_#": i}
                    for col in unique_combo_cols:
                        option[col.lower()] = _get_column_value(row, col)
                    if timestamp_col:
                        option[timestamp_col.lower()] = _get_column_value(row, timestamp_col)
                    unique_options.append(option)

                instruction = f"Refine your search or specify which option you want to proceed with."
                if len(unique_options) > 20:
                    info_message = f"Informational: Showing top 20 of {len(unique_options)} unique combinations found."
                    return [{"tool_message": instruction, "info_to_user": info_message, "unique_options":  await json_to_dynamic_markdown(unique_options[:20])}]
                else:
                    info_message = f"Informational: Found {len(unique_options)} unique combinations."
                    return [{"tool_message": instruction, "info_to_user": info_message, "unique_options": await json_to_dynamic_markdown(unique_options)}]

            # Handle Single Result
            elif len(data) == 1:
                row = data[0]
                current_tilt = _get_column_value(row, "TILT")
                min_tilt = _get_column_value(row, "MINIMUMTILT")
                max_tilt = _get_column_value(row, "MAXIMUMTILT")
                is_valid, validation_message = _validate_ret_params(vendor.lower(),target_tilt, current_tilt, min_tilt, max_tilt)
                if not is_valid and vendor.lower() == 'samsung':
                    return [{"tool_message": f"Validation failed: {validation_message}", "Agent to provide this information to user": ">Note: Tilt Values are Converted from degrees to EMS"}]
                elif not is_valid and vendor.lower() == 'mavenir':
                    return [{"tool_message": f"Validation failed: {validation_message}"}]

                if operation == 'validate':
                    # Build a clean parameter list for confirmation based on display_cols in config
                    confirmed_params = []  # Changed to a list of dictionaries
                    display_cols = config.get("display_cols", [])
                    # Create a reverse map for convenience: {column_name: param_name}
                    col_to_param_map = {v: k for k, v in config["param_to_col_map"].items()}

                    for col_name in display_cols:
                        param_name = col_to_param_map.get(col_name, col_name.lower())

                        if col_name.upper() == "TILT" and target_tilt is not None:
                            # For Samsung vendor, check if target_tilt needs conversion note
                            display_target = target_tilt
                            if vendor.lower() == 'samsung':
                                try:
                                    current_tilt = f"{current_tilt} (EMS)"
                                    target_tilt_float = float(target_tilt)
                                    if -10 < target_tilt_float < 10:  # EMS format range
                                        converted_value = target_tilt_float * 10  # Convert to degrees
                                        if converted_value.is_integer():
                                            converted_value = int(converted_value)  # Convert to int if original was integer
                                        display_target = f"{target_tilt} (converted {target_tilt} degrees to {converted_value} EMS)"
                                except (ValueError, TypeError):
                                    # If conversion fails, keep original value
                                    pass

                            # Add TILT as a dictionary with all three keys
                            confirmed_params.append({
                                "Parameter Name": param_name,
                                "Current": current_tilt,
                                "Target": display_target
                            })
                        else:
                            value = _get_column_value(row, col_name)
                            if value is not None:
                                # Add other parameters as dictionaries with all three keys
                                confirmed_params.append({
                                    "Parameter Name": param_name,
                                    "Current": value,
                                    "Target": value
                                })

                    if confirmed_params:
                        confirmed_params = await json_to_dynamic_markdown(confirmed_params)

                    tool_message = "Successfully identified the target cell and performed validation successfully. Please review the complete parameter list below and confirm if you want to proceed with the operation."
                    if vendor.lower() == 'samsung':
                        response = {"tool_message": tool_message, "confirmed_parameters": confirmed_params,"Note_to_user" : ">Note: Values are Converted degrees to EMS"}
                    else:
                        response = {"tool_message": tool_message, "confirmed_parameters": confirmed_params}
                    if validation_message: # Append informational message if one exists
                        response["info_to_user"] = validation_message
                    return [response]

                if operation == 'update':
                    # Create a flat dictionary for the update function
                    update_params = {k.lower(): v for k, v in row.items()}
                    update_params['target_tilt'] = target_tilt
                    update_params['vendor'] = vendor
                    update_params['user_id'] = user_id
                    try:
                        update_result = await _update_ret_value(thread_id, **update_params)
                        return [update_result]
                    except NonIntegerTiltError as e:
                        logger.error(f"RET update error: {str(e)}")
                        logger.error(traceback.format_exc())
                        return [{"error": f"Failed to update RET value. {e}"}]
                    except Exception as update_error:
                        logger.error(f"RET update error: {str(update_error)}")
                        logger.error(traceback.format_exc())
                        return [{"error": "Failed to update RET value. Please try again later."}]

            return [{"error": "Reached an unexpected state."}]
        except Exception as process_error:
            logger.error(f"Result processing error: {str(process_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to process results. Please try again later."}]

    except Exception as e:
        logger.error(f"Unexpected error in handle_ret_update: {str(e)}")
        logger.error(traceback.format_exc())
        return [{"error": "An unexpected error occurred while processing your request. Please try again later."}]


@tool
async def handle_classc_update(
        operation: str,
        event_type: str,
        site_name: Optional[str] = None, cell_name: Optional[str] = None,
        vendor: Optional[str] = None,
        # Configurable parameters, mapped from event_type
        trigger_quantity: Optional[str] = None, threshold_rsrp: Optional[str] = None,
        hysteresis: Optional[str] = None, time_to_trigger: Optional[str] = None,
        offset_rsrp: Optional[str] = None, threshold1_rsrp: Optional[str] = None,
        threshold2_rsrp: Optional[str] = None,
        # Additional filterable parameters from the table
        gnodeb_id: Optional[str] = None, cell_identity: Optional[str] = None,
        cucp_id: Optional[str] = None, du_id: Optional[str] = None,
        report_config_entry_index: Optional[str] = None,
        ssb_config_ssb_freq: Optional[str] = None, purpose: Optional[str] = None,
        band: Optional[str] = None,
        sector: Optional[str] = None,
        config: RunnableConfig = None,
) -> List[Dict[str, Any]]:
    """
    Use this tool to validate or update Class C parameters (e.g., A1-A5 events) for a cell.
    Mandatory args: 'operation', 'event_type', and either 'site_name' or 'cell_name'.
    At least one configurable parameter for the specified event_type must be provided.
    For args: 'band' Don't extract band from cell name , only provide band if it is explicitly provided by user.
    This tool currently only supports the 'samsung' vendor.
    Use operation: 'validate' to find and check a unique cell and validate the parameters. Use operation: 'update' to perform the change once the validation is done and the user confirms the parameters.
    All other parameters are optional and used to filter for a unique cell.
    """
    try:
        # Fetching thread Id
        thread_id = None
        data = None
        if config and config.get("metadata") and config.get("metadata").get("thread_id"):
            logger.info(f"Thread identified: {config.get('metadata').get('thread_id')}")
            thread_id = config.get("metadata").get("thread_id")
            user_id = await get_user_from_thread(thread_id)
            logger.info(f"User ID: {user_id}")

        # 1. Initial Validation
        try:
            operation = operation.lower()
            event_type = event_type.lower()
            if operation not in ['validate', 'update']:
                return [{"error": f"Invalid operation '{operation}'. Must be 'validate' or 'update'."}]
            if not site_name and not cell_name:
                return [{"error": "Either site_name or cell_name must be provided."}]
            if event_type not in EVENT_TYPE_CONFIGS:
                return [{"error": f"Invalid event_type '{event_type}'. Must be one of {list(EVENT_TYPE_CONFIGS.keys())}."}]

            # Validate that at least one relevant config param is being updated
            all_params = locals()
            valid_config_params = EVENT_TYPE_CONFIGS[event_type]
            provided_config_params = {p: all_params[p] for p in valid_config_params if all_params.get(p) is not None}
            if not provided_config_params:
                return [{"error": f"At least one of the following parameters must be provided for event_type '{event_type}': {', '.join(valid_config_params)}."}]
        except Exception as validation_error:
            logger.error(f"Validation error: {str(validation_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to validate input parameters. Please check your input and try again."}]

        # 2. Determine Vendor and Configuration
        try:
            exact_vendor = None
            vendor_lookup_result = await _fetch_ran_vendor("CELL" if cell_name else "SITE", cell_name or site_name)
            logger.info(f"vendor_lookup_result ::: {vendor_lookup_result}")

            if vendor_lookup_result.get("error"):
                return [{"error": f"Vendor lookup failed: {vendor_lookup_result['error']}"}]

            if vendor_lookup_result and vendor_lookup_result.get("vendor") and len(vendor_lookup_result.get("vendor")):
                exact_vendor =  vendor_lookup_result.get("vendor")[0]

            looked_up_vendor = (exact_vendor or vendor_lookup_result.get("nearest_match_vendor") or "").lower()

            # If user provided a vendor, validate it
            if vendor and vendor.lower() != looked_up_vendor:
                return [{"error": f"Vendor mismatch. You specified '{vendor}' but the system identified '{looked_up_vendor}' for this cell/site."}]

            # Use looked-up vendor or fallback to provided vendor
            vendor = looked_up_vendor or vendor
            if not vendor:
                return [{"error": f"Vendor lookup failed: {vendor_lookup_result.get('tool_message') or 'Could not identify vendor.'}"}]

            if vendor != "samsung":
                return [{"error": f"Class C changes are currently only supported for Samsung. The identified vendor was '{vendor}'."}]

            config = VENDOR_CONFIGS[vendor]["classc_update"]
        except Exception as vendor_error:
            logger.error(f"Vendor determination error: {str(vendor_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to determine vendor configuration. Please try again later."}]

        # 3. Database Query
        try:
            query = text(f"SELECT * FROM {config['table_name']} WHERE {config['cell_col']} ILIKE :cell_val AND UPPER(REPORT_TYPE) = :event_type")
            params = {"cell_val": (cell_name or site_name or '').upper() + '%', "event_type": event_type.upper()}

            async with snow_db.get_db_session() as session:
                try:
                    result = await asyncio.to_thread(session.execute, query, params)
                    data = [dict(zip(result.keys(), row)) for row in result.fetchall()]
                    print(data)
                except Exception as db_error:
                    logger.error(f"Database execution error: {str(db_error)}")
                    logger.error(traceback.format_exc())
                    return [{"error": "Database query failed. Please try again later."}]
        except Exception as session_error:
            logger.error(f"Database session error: {str(session_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to establish database connection. Please try again later."}]

        if not data:
            return [{"tool_message": "No matching record found for the specified cell and event_type."}]

        # 4. Dynamic Filtering - Only use designated filterable parameters
        try:
            filterable_params = config.get("filterable_params", [])
            param_map = config["param_to_col_map"]
            for param_name in filterable_params:
                if all_params.get(param_name) is not None:
                    param_value = all_params[param_name]
                    col_name = param_map.get(param_name)
                    if col_name:
                        data = [
                            row for row in data
                            if _compare_values(_get_column_value(row, col_name), param_value)
                        ]

            # Special filter for band, parsed from cell_name for consistency with RET tool
            #data = await _filter_by_band(data, band, config["cell_col"])
            #if not data:
                #return [{"tool_message": "No matching records found after band filtering."}]

            # Filter by sector
            print("data ::", data)
            data = await _filter_by_sector(data, sector, config["cell_col"])
            print("data ::", data)
            if not data:
                return [{"tool_message": "No matching records found after sector filtering."}]

            if data:
                # Apply grouping and sorting
                data = group_and_sort_cells(data, "cell_name")

            if not data:
                return [{"tool_message": "No matching records found after sector sorting."}]
        except Exception as filter_error:
            logger.error(f"Data filtering error: {str(filter_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to filter data. Please check your parameters and try again."}]

        # 5. Process Results
        try:
            if not data:
                return [{"tool_message": "No matching entry found after applying all criteria."}]

            if len(data) > 1:
                unique_combo_cols = config["unique_combo_cols"]
                param_map = config["param_to_col_map"]
                event_params = EVENT_TYPE_CONFIGS.get(event_type.lower(), [])
                # De-duplicate the results to get unique rows
                unique_combinations_map = {
                    "_".join(str(_get_column_value(r, col) or '') for col in unique_combo_cols): r
                    for r in data
                }
                unique_rows = list(unique_combinations_map.values())
                # Build the options list for the user
                unique_options = []
                timestamp_col = config.get("timestamp_col")
                for i, row in enumerate(unique_rows, 1):
                    option = {"option_#": i}
                    # Add the unique identifier columns
                    for col in unique_combo_cols:
                        option[col.lower()] = _get_column_value(row, col)
                    # Add the current values of event-specific parameters for context
                    for param in event_params:
                        col_name = param_map.get(param, param)
                        option[param] = _get_column_value(row, col_name)
                    if timestamp_col:
                        option[timestamp_col.lower()] = _get_column_value(row, timestamp_col)
                    unique_options.append(option)

                info_message = f"Informational: Multiple entries match ({len(unique_rows)} found). Showing top 20."
                tool_message = "Refine your search or specify which option you want to proceed with."
                return [{"tool_message": tool_message, "info_to_user": info_message, "unique_options": await json_to_dynamic_markdown(unique_options[:20])}]

            # Single unique row found
            row = data[0]

            # 6. Perform validation on parameters
            try:
                is_valid, validation_message, dish_recommendation = await _validate_classc_params(provided_config_params, row, config["param_to_col_map"])
                if not is_valid:
                    return [{"tool_message": f"Validation failed: {validation_message}"}]
            except Exception as param_validation_error:
                logger.error(f"Parameter validation error: {str(param_validation_error)}")
                logger.error(traceback.format_exc())
                return [{"error": "Failed to validate parameters. Please check your input and try again."}]

            # 7. Execute Operation
            try:
                if operation == 'validate':
                    # For display, only show unique identifiers and event-specific parameters from config
                    param_map = config["param_to_col_map"]
                    base_display_cols = config.get("display_cols", [])
                    event_params = EVENT_TYPE_CONFIGS.get(event_type.lower(), [])

                    # Create reverse map for looking up param names from column names
                    col_to_param_map = {v: k for k, v in param_map.items()}
                    confirmed_params_for_display = []
                    # Combine base display columns and event-specific parameters for display
                    all_display_params = set(base_display_cols)
                    for p in event_params:
                        all_display_params.add(param_map.get(p, p))

                    for col_name in all_display_params:
                        param_name = col_to_param_map.get(col_name, col_name.lower())

                        # If param is being changed, show current/target
                        if param_name in provided_config_params:
                            current_value = _get_column_value(row, col_name)
                            target_value = provided_config_params[param_name]

                            # Always include parameters being changed (even if current is None)
                            param_entry = {
                                "Parameter Name": param_name,
                                "Current": current_value,
                                "Target": target_value
                            }
                            if dish_recommendation:
                                dish_value = dish_recommendation.get(param_name)
                                if dish_value is not None:
                                    param_entry["Dish_Recommended"] = dish_value[0]

                            confirmed_params_for_display.append(param_entry)

                        else: # Otherwise, just show its current value
                            value = _get_column_value(row, col_name)
                            if value is not None:
                                confirmed_params_for_display.append({
                                    "Parameter Name": param_name,
                                    "Current": value,
                                    "Target": value
                                })

                    if confirmed_params_for_display:
                        confirmed_params_for_display = await json_to_dynamic_markdown_header_collection(confirmed_params_for_display)
                    tool_message = "Successfully validated the target cell and parameters. To proceed, call this tool again with operation='update' and the same criteria."
                    response = {"tool_message": tool_message, "confirmed_parameters": confirmed_params_for_display, "Agent to provide this Note to user for supported operation" : ">Note: The bot can currently Support only 5QI9 changes and not 5QI1(SBHO)"}
                    if validation_message: # Append informational message if one exists
                        response["info_to_user"] = validation_message
                    return [response]

                if operation == 'update':
                    # For execution, use a flat structure with all data
                    confirmed_params_for_update = {**row, **provided_config_params, "event_type": event_type}
                    try:
                        update_result = await _update_classc_params(thread_id, **confirmed_params_for_update)
                        return [update_result]
                    except Exception as update_error:
                        logger.error(f"Class C update error: {str(update_error)}")
                        logger.error(traceback.format_exc())
                        return [{"error": "Failed to update Class C parameters. Please try again later."}]
            except Exception as operation_error:
                logger.error(f"Operation execution error: {str(operation_error)}")
                logger.error(traceback.format_exc())
                return [{"error": "Failed to execute operation. Please try again later."}]

            return [{"error": "Reached an unexpected state."}]
        except Exception as process_error:
            logger.error(f"Result processing error: {str(process_error)}")
            logger.error(traceback.format_exc())
            return [{"error": "Failed to process results. Please try again later."}]

    except Exception as e:
        logger.error(f"Unexpected error in handle_classc_update: {str(e)}")
        logger.error(traceback.format_exc())
        return [{"error": "An unexpected error occurred while processing your request. Please try again later."}]

# --- Tool Registration ---
ran_automation_tools = [handle_ret_update, handle_classc_update]

# --- Test Block ---
if __name__ == "__main__":
    import sys

    async def run_tests():
        # --- Test 1: Mavenir Full Flow (Validate -> Update) ---
        print("--- [1/2] Testing Mavenir Full Flow ---")
        print("\n--- Mavenir Validation Step ---")
        mavenir_validate_args = {
            "operation": "validate",
            "cell_name": "HOHOU00562A_1_n29_E_DL",
            "hdlc_address": "2",
            "target_tilt": "5.0"
        }
        mavenir_validate_result = await handle_ret_update.ainvoke(mavenir_validate_args)
        print(json.dumps(mavenir_validate_result, indent=2, default=str))

        print("\n--- Mavenir Update Step ---")
        if mavenir_validate_result and mavenir_validate_result[0].get("confirmed_parameters"):
            mavenir_update_args = {
                "operation": "update",
                **{k: v for k, v in mavenir_validate_args.items() if k != "operation"}
            }
            mavenir_update_result = await handle_ret_update.ainvoke(mavenir_update_args)
            print(json.dumps(mavenir_update_result, indent=2, default=str))
        else:
            print("Skipping Mavenir update test as validation did not return a unique result.")
            
        # --- Test 2: Samsung Full Flow (Validate -> Update) ---
        print("\n\n--- [2/2] Testing Samsung Full Flow ---")
        print("\n--- Samsung Validation Step ---")
        samsung_validate_args = {
            "operation": "validate",
            "cell_name": "DNDEN00048B_1_n71_A",
            "target_tilt": "8.0"
        }
        samsung_validate_result = await handle_ret_update.ainvoke(samsung_validate_args)
        print(json.dumps(samsung_validate_result, indent=2, default=str))

        print("\n--- Samsung Update Step ---")
        if samsung_validate_result and samsung_validate_result[0].get("confirmed_parameters"):
            samsung_update_args = {
                "operation": "update",
                **{k: v for k, v in samsung_validate_args.items() if k != "operation"}
            }
            samsung_update_result = await handle_ret_update.ainvoke(samsung_update_args)
            print(json.dumps(samsung_update_result, indent=2, default=str))
        else:
            print("Skipping Samsung update test as validation did not return a unique result.")

        # --- Test 3: Samsung Band Filtering (Multiple Results) ---
        print("\n\n--- [3/3] Testing Samsung Band Filtering ---")
        samsung_band_args = {
            "operation": "validate",
            "site_name": "DNDEN00048B",
            "band": "n71"
        }
        samsung_band_result = await handle_ret_update.ainvoke(samsung_band_args)
        print(json.dumps(samsung_band_result, indent=2, default=str))

        # --- Test 4: Samsung Numeric Filtering Fix ---
        print("\n\n--- [4/4] Testing Samsung Numeric Filtering Fix ---")
        samsung_numeric_args = {
            "operation": "validate",
            "cell_name": "DNDEN00048B_3_n70_AWS-4_UL15",
            "aldid": "0",
            "target_tilt": "6.0"
        }
        samsung_numeric_result = await handle_ret_update.ainvoke(samsung_numeric_args)
        print(json.dumps(samsung_numeric_result, indent=2, default=str))

    if len(sys.argv) > 1 and sys.argv[1] == "test_all":
        asyncio.run(run_tests())
    elif len(sys.argv) > 1 and sys.argv[1] == "test_classc":
        async def run_classc_test():
            print("--- Testing Class C Validation: Multiple Matches ---")
            classc_args = {
                "operation": "validate",
                "event_type": "a2",
                "cell_name": "MNMSP00004A_1",
                "hysteresis": "10"
            }
            result = await handle_classc_update.ainvoke(classc_args)
            print(json.dumps(result, indent=2, default=str))
        asyncio.run(run_classc_test())
    elif len(sys.argv) > 1 and sys.argv[1] == "test_classc_update":
        async def run_classc_update_test():
            print("--- Testing Class C Full Flow (Validate -> Update) ---")
            
            # Use specific criteria to find a unique row
            test_args = {
                "operation": "validate",
                "event_type": "a2",
                "cell_name": "MNMSP00004A_1_n71_F-G",
                "hysteresis": "6",
                "report_config_entry_index": "7"
            }
            
            print("\n--- Class C Validation Step ---")
            validate_result = await handle_classc_update.ainvoke(test_args)
            print(json.dumps(validate_result, indent=2, default=str))

            print("\n--- Class C Update Step ---")
            if validate_result and validate_result[0].get("confirmed_parameters"):
                # For the update, use the same filtering criteria
                update_args = {**test_args, "operation": "update"}
                update_result = await handle_classc_update.ainvoke(update_args)
                print(json.dumps(update_result, indent=2, default=str))
            else:
                print("Skipping Class C update test as validation did not return a unique result.")
        
        asyncio.run(run_classc_update_test())
    else:
        print("To run tests, please use the argument 'test_all' or 'test_classc' or 'test_classc_update'")
