import logging
from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam
from typing import Optional, Dict, List
import json
from datetime import datetime, date
import inspect
from decimal import Decimal
import utils.postgres_util.dbutil as db
from utils.ran_automation_validation import filter_out_rows_with_none,gnb_filter_out_rows_with_none
import utils.snow_utils.snowflake_util as snow_db
from utils.snow_utils.snowflake_util import run_in_threadpool
import utils.constants as constant
import re
from decimal import Decimal, InvalidOperation
import json
from collections import defaultdict
from collections import OrderedDict
from utils import constants as CONST

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

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


async def get_data_by_cell_id_node_id(cell_id: str,cell_name:str, node_id: str,band: str, purpose: str, frequency: str,index: str, report_type:str, vendor: str):
    """
    Fetches data from DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_CONFIG_CUCP_PARAMETERS table
    based on GNODEB_ID, CELL_IDENTITY, or CELL_NAME with case-insensitive filtering using ILIKE.
    """

    if vendor.lower() == 'samsung':
        table_name = "DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_CONFIG_CUCP_PARAMETERS"
        query_params = {}
        conditions = []

        if node_id:
            conditions.append("gnodeb_id ILIKE :node_id")
            query_params["node_id"] = f"%{node_id}%"
        if cell_id:
            conditions.append("cell_identity ILIKE :cell_id")
            query_params["cell_id"] = f"%{cell_id}%"
        if cell_name:
            conditions.append("cell_name ILIKE :cell_name")
            query_params["cell_name"] = f"%{cell_name}%"
        if band:
            conditions.append("band ILIKE :band")
            query_params["band"] = f"%{band}%"
        if purpose:
            conditions.append("purpose ILIKE :purpose")
            query_params["purpose"] = f"%{purpose}%"
        if index:
            conditions.append("report_config_entry_index::TEXT ILIKE :index")
            query_params["index"] = f"%{index}%"
        if frequency:
            conditions.append("ssb_config_ssb_freq::TEXT ILIKE :frequency")
            query_params["frequency"] = f"%{frequency}%"
        if report_type:
            conditions.append("report_type ILIKE :report_type")
            query_params["report_type"] = f"%{report_type.upper()}%"

        if not conditions:
            raise ValueError("At least one of node_id, band, cell_id, or cell_name must be provided.")

        query = text(f"""
            SELECT *
            FROM {table_name}
            WHERE { ' AND '.join(conditions) }
            ORDER BY cell_identity ASC
            LIMIT 25;
        """)

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
                
                json_results = gnb_filter_out_rows_with_none(json_results)

                # Add serial number as the first key in each record
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
                return []

async def get_gpl_parameters_by_param_name(vendor: str, event: str):
    """
    Fetches GPL parameters by param_name for the given vendor and event.
    The result will be returned as a dictionary with param_name as the key and range as the value.

    :param vendor: Vendor name (e.g., 'Samsung')
    :param event: Event name (e.g., 'event1')
    :return: Dictionary of parameter names as keys and their range as values
    """
    if vendor.lower() == 'samsung':
        query = text("""
        SELECT DISTINCT ON (param_name) param_name, range
        FROM ran.samsung_gpl_params
        WHERE param_name IN :param_names_list
        ORDER BY param_name, version DESC
    """).bindparams(bindparam("param_names_list", expanding=True))


    param_names_list = ["threshold-rsrp","threshold2-rsrp","threshold1-rsrp","hysteresis","time-to-trigger","trigger-quantity"]
    logger.info("Parameters List :: %s", param_names_list)


    # Append event as a prefix to each parameter name
    updated_param_names = [
        param if param == "trigger-quantity" else f"{event}-{param}"
        for param in param_names_list
    ]

    logger.info("Updated Parameters List :: %s", updated_param_names)

    async with db.get_session() as session:
        try:
            logger.info("Fetching data for vendor: %s with params: %s", vendor, updated_param_names)

            # Execute the query with a tuple for parameter binding
            result = await session.execute(query, {"param_names_list": updated_param_names})
            rows = result.fetchall()  # Fetch all matching rows

            # Fetch column names
            column_names = result.keys()
            logger.info("Fetched column names: %s", column_names)

            # Initialize an empty dictionary for the result
            param_dict = {}

            for row in rows:
                # Convert to dictionary where key is param_name and value is range
                row_dict = {column.lower(): convert_to_serializable(value) for column, value in zip(column_names, row)}

                # Add to the result dictionary
                # Retrieve the parameter name and replace '-' with '_'
                param_name = row_dict.get('param_name')
                if param_name:
                    param_name = param_name.replace('-', '_')
                param_dict[param_name] = row_dict.get('range')

            return param_dict  # Return dictionary with param_name as key and range as value

        except Exception as e:
            logger.error("Error occurred while fetching GPL parameters: %s", e)
            raise


async def get_dish_recommended_gpl_parameters(event: str, vendor: str, cell_num: Optional[str] = None,
                                              target_band: Optional[str] = None) -> List[Dict]:
    """
    Fetch recommended GPL parameters for a given event, vendor, and optionally, a cell number.
    Returns the latest version (ordered by version descending) limited to 1 result.
    """
    # Base query
    query = """
    SELECT criteria_type, threshold_rsrp, threshold_rsrp1 as threshold1_rsrp, threshold_rsrp2 as threshold2_rsrp, hysteresis, time_to_trigger, trigger_quantity , offset_value as offset, cell_num, target_band
    FROM ran.connected_mobility
    WHERE criteria_type = :criteria_type
    AND vendor = :vendor
    """

    params = {"criteria_type": event, "vendor": vendor}

    # Add cell_num conditionally using ILIKE for case-insensitive matching
    # if cell_num and cell_num != 'null':
    #     query += " AND cell_num ILIKE :cell_num"
    #     params["cell_num"] = f"%{cell_num}%"  # Add wildcards for partial matching
    #
    # # Add target_band conditionally using ILIKE for case-insensitive matching
    # if target_band and target_band != 'null':
    #     query += " AND target_band ILIKE :target_band"
    #     params["target_band"] = f"%{target_band}%"  # Add wildcards for partial matching

    # Add ordering by version descending and limit to 1
    query += " ORDER BY version DESC LIMIT 1"

    async with db.get_session() as session:
        try:
            logger.info("Fetching data for event: %s, vendor: %s, cell_num: %s, target_band: %s", event, vendor,
                        cell_num, target_band)
            # Execute the query with dynamically built parameters
            result = await session.execute(text(query), params)
            rows = result.fetchall()

            # Fetch column names
            column_names = result.keys()
            logger.info("Fetched column names: %s", column_names)

            # Convert to JSON-serializable format
            json_results = [
                {column.lower(): convert_to_serializable(value) for column, value in zip(column_names, row)}
                for row in rows
            ]

            # Serialize to JSON and log
            json_output = json.dumps(json_results, indent=4)
            logger.info("JSON Output: %s", json_output)

            return json_results  # Return JSON-serializable data
        except Exception as e:
            logger.error("Error occurred while fetching dish recommended GPL parameters: %s", e)
            raise


def parse_range(range_str: str):
    """Parses a range string like '0..127' and returns (min, max) as Decimal values.

    Raises:
        ValueError: If the input string does not match the expected range format.
    """
    logger.info("Checking range for: %s", range_str)
    match = re.match(r"(\d+(\.\d+)?)\.\.(\d+(\.\d+)?)", range_str)
    if match:
        return Decimal(match.group(1)), Decimal(match.group(3))
    raise ValueError(f"Invalid range format: {range_str}")


async def json_to_dynamic_markdown(json_data):
    """
    Converts a JSON object into a Markdown table with dynamic column widths.

    :param json_data: dict or list of dicts representing the JSON data
    :return: str containing the Markdown table
    """
    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    # Ensure data is a list of dictionaries
    if isinstance(json_data, dict):
        json_data = [json_data]

    # Get the headers from the keys of the first dictionary
    headers = list(json_data[0].keys())

    # Calculate the maximum width for each column
    column_widths = {header: len(header) for header in headers}
    for item in json_data:
        for header in headers:
            column_widths[header] = max(column_widths[header], len(str(item.get(header, ""))))

    # Generate the header row and divider row
    header_row = "| " + " | ".join(f"{header:{column_widths[header]}}" for header in headers) + " |"
    divider_row = "| " + " | ".join("-" * column_widths[header] for header in headers) + " |"

    # Generate the data rows
    data_rows = []
    for item in json_data:
        row = "| " + " | ".join(
            f"{str(item.get(header, '')).ljust(column_widths[header])}" for header in headers) + " |"
        data_rows.append(row)

    # Combine rows into a Markdown table
    markdown_table = "\n".join([header_row, divider_row] + data_rows)

    return markdown_table


async def json_to_dynamic_markdown_header_collection(json_data):
    """
    Converts a JSON object into a Markdown table with dynamic column widths.
    Automatically arranges columns in a logical order: Parameter Name, Current, Target, Dish_Recommended, then others alphabetically.
    :param json_data: dict or list of dicts representing the JSON data
    :return: str containing the Markdown table
    """
    if isinstance(json_data, str):
        json_data = json.loads(json_data)
    # Ensure data is a list of dictionaries
    if isinstance(json_data, dict):
        json_data = [json_data]

    # Collect all possible keys from all dictionaries
    all_keys = set()
    for item in json_data:
        all_keys.update(item.keys())

    # Define the priority order for columns
    priority_columns = ['Parameter Name', 'Current', 'Target', 'Dish_Recommended']

    # Separate the keys into priority columns and others
    priority_keys = [key for key in priority_columns if key in all_keys]
    other_keys = sorted([key for key in all_keys if key not in priority_columns])

    # Combine the keys: first priority columns in order, then other columns alphabetically
    headers = priority_keys + other_keys

    # Calculate the maximum width for each column
    column_widths = {header: len(header) for header in headers}
    for item in json_data:
        for header in headers:
            column_widths[header] = max(column_widths[header], len(str(item.get(header, ""))))

    # Generate the header row and divider row
    header_row = "| " + " | ".join(f"{header:{column_widths[header]}}" for header in headers) + " |"
    divider_row = "| " + " | ".join("-" * column_widths[header] for header in headers) + " |"

    # Generate the data rows
    data_rows = []
    for item in json_data:
        row = "| " + " | ".join(
            f"{str(item.get(header, '')).ljust(column_widths[header])}" for header in headers) + " |"
        data_rows.append(row)

    # Combine rows into a Markdown table
    markdown_table = "\n".join([header_row, divider_row] + data_rows)
    return markdown_table

async def extract_numbers(input_str: str):
    return [part.split('(')[0].strip().replace('ms', '') for part in input_str.split('|')]

from decimal import Decimal
from typing import Dict, Any

async def validate_request(request: Any, event: str, parameters_range_resp: Dict[str, Any]):
    """
    Validate each parameter in the request individually if it exists.

    :param request: The incoming request object.
    :param event: The event name (e.g., 'event1').
    :param parameters_range_resp: A dictionary with valid ranges for parameters.
    :return: A dictionary with the result of validation for each parameter.
    """
    validation_results = []
    error_code_series_start = 600  # Start the error code series from 300

    # Define all the parameters to validate
    parameters = ['threshold_rsrp','threshold1_rsrp', 'threshold2_rsrp','hysteresis', 'time_to_trigger', 'trigger_quantity','offset_rsrp']

    for param_name in parameters:
        param_value = getattr(request, param_name, None)
        updated_param_name = f"{event.lower()}_{param_name}"

        # Validate if parameter exists and is not "null"
        if param_value and param_value != "null" and updated_param_name in parameters_range_resp:
            try:
                if param_name == 'time_to_trigger':
                    # Special validation for time_to_trigger - it should be in the valid range list
                    valid_range_list = await extract_numbers(parameters_range_resp[updated_param_name])
                    if param_value not in valid_range_list:
                        error_message = f"The value provided for '{updated_param_name}' is {param_value} ms, which is outside the expected range of {valid_range_list} ms. Please enter a value within the specified range"
                        validation_results.append({
                            "status": "fail",
                            "message": error_message,
                            "error_code": f"VP-{error_code_series_start}"
                        })
                        break  # Exit the loop on failure
                else:
                    valid_range = parameters_range_resp[updated_param_name]
                    min_val, max_val = parse_range(valid_range)
                    param_value = Decimal(param_value)

                    # Check if the parameter value is within the valid range
                    if not (min_val <= param_value <= max_val):
                        error_message = f"The value provided for '{updated_param_name}' is {param_value}, which is outside the expected range of {min_val} to {max_val}. Please enter a value within this range."
                        validation_results.append({
                            "status": "fail",
                            "message": error_message,
                            "error_code": f"VP-{error_code_series_start}"
                        })
                        break  # Exit the loop on failure

            except ValueError as ve:
                error_message = f"{updated_param_name} : Invalid range format: {valid_range} ({ve})"
                validation_results.append({
                    "status": "fail",
                    "message": error_message,
                    "error_code": f"VP-{error_code_series_start}"
                })
                break  # Exit the loop on failure
            except InvalidOperation:
                error_message = f"{updated_param_name} : Invalid numeric value: {param_value}"
                validation_results.append({
                    "status": "fail",
                    "message": error_message,
                    "error_code": f"VP-{error_code_series_start}"
                })
                break  # Exit the loop on failure

        error_code_series_start += 1    # Increment error code for the next parameter

    # If there were no validation errors, return success
    if not validation_results:
        return {"status": "success"}

    return {"status": "fail", "validation_errors": validation_results}


from typing import Dict, Any

from typing import Any, Dict, List

async def extract_valid_dish_params(request: Any, response: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    """
    Extract valid parameters and their valid values from the response based on the request.

    :param request: The incoming request object that contains parameter values to validate.
    :param response: A list of dictionaries containing valid values for each parameter.
    :return: A dictionary with parameter names as keys and their valid values as lists.
    """
    valid_params = {}
    parameters = ['threshold_rsrp', 'hysteresis', 'time_to_trigger', 'threshold2_rsrp', 'threshold1_rsrp', 'trigger_quantity']

    for param_name in parameters:
        param_value = getattr(request, param_name, None)

        # Check if the parameter exists and is valid (not None and not "null")
        if param_value and param_value != "null":
            # Handle cases where the request value is formatted (e.g., "46 (-110 dBm)")
            if isinstance(param_value, str) and '(' in param_value:
                param_value = param_value.split(" ")[-1].strip("()")  # Extract numeric part

            # Search for the parameter in the response list
            param_dict = next((item for item in response if param_name in item), None)

            if param_dict:
                valid_values = param_dict.get(param_name, [])

                # Ensure valid_values is always a list
                if not isinstance(valid_values, list):
                    valid_values = [valid_values]

                if valid_values:
                    valid_params[param_name] = valid_values

    return valid_params



from typing import Dict, Any

async def validate_request_params(request: Any, valid_params: Dict[str, Any], parameters: list) -> bool:
    """
    Validate request parameters based on the dish-recommended parameters.

    :param request: The incoming request object containing parameter values.
    :param valid_params: A dictionary containing the valid values for each parameter.
    :param parameters: A list of parameters to check in the request.
    :return: A boolean value indicating whether all parameters in the request are valid.
    """
    for param_name in parameters:
        param_value = getattr(request, param_name, None)

        # Check if the parameter value in the request is not null
        if param_value and param_value != "null":
            # Check if the parameter exists in the valid_params dictionary
            if param_name in valid_params:
                valid_values = valid_params[param_name]

                # Check if the value in the request is in the valid values list
                if param_value not in valid_values:
                    return False  # Return False immediately if any validation fails

    return True  # Return True if all validations pass



async def dict_to_markdown_table(data: dict) -> str:
    """
    Converts a dictionary into a Markdown table.

    :param data: Dictionary where keys are column headers, and values are lists of values.
    :return: A Markdown table as a string.
    """
    markdown = "| Parameter | Dish Recommended Values |\n|---|---|\n"
    for key, values in data.items():
        values_str = ", ".join(values)  # Join values into a comma-separated string
        markdown += f"| {key} | {values_str} |\n"
    return markdown


async def filter_dicts_by_keys(data: List[Dict]) -> List[Dict]:
    """
    Filters a list of dictionaries, keeping only the keys that are present in the allowed_keys list.

    :param data: List of dictionaries to be filtered.
    :return: A new list of dictionaries with only the allowed keys.
    """
    return [{key: d[key] for key in d if key in constant.allowed_keys} for d in data]


async def validate_existing_param_values(current_gnb_params: dict, request) -> dict:
    """
    Validate the existing gNB parameters against the update request.

    Args:
        current_gnb_params (dict): Current parameters from the database.
        request: Request object (or dict) containing update values. It should have an attribute 'event'
                 and be convertible to a dict (e.g., via request.dict()).

    Returns:
        dict: A dictionary with a 'status' key ('success' or 'fail'), an 'error_code' in case of failure,
              and a 'message' (or data) key.
    """
    logger.info("Starting parameter validation.")

    # 1. Check if current parameters are provided.
    if current_gnb_params is None:
        logger.info("No current parameters provided. Error code: %s", "VP-409")
        return {
            "status": "fail",
            "error_code": "VP-409",
            "message": "No current parameters provided."
        }

    # 2a. Validate the 'report_type' exists in the current parameters.
    current_report_type = current_gnb_params.get("report_type")
    if current_report_type is None:
        logger.info("Report type is missing in current parameters: %s. Error code: %s", current_gnb_params, "VP-409")
        return {
            "status": "fail",
            "error_code": "VP-409",
            "message": "Report type is missing in current parameters."
        }

    # 2b. Validate that the report_type matches the request's event.
    request_event = getattr(request, "event", None)
    if current_report_type.lower() != request_event:
        logger.info(
            "Report type mismatch: current report type '%s' does not match request event '%s'. Error code: %s",
            current_report_type,
            request_event,
            "VP-409",
        )
        return {
            "status": "fail",
            "error_code": "VP-409",
            "message": "Report type does not match the request event."
        }
    logger.info("Report type validated: %s", current_report_type)

    # 3. Create a new dictionary with key replacement based on the mapping.
    CUCP_parameters_mapping = {
        "threshold_rsrp": "threshold_rsrp",
        "trigger_quantity": "trigger_quantity",
        "threshold1_rsrp": "threshold1_rsrp",
        "threshold2_rsrp": "threshold2_rsrp",
        "hysteresis": "hysteresis",
        "time_to_trigger": "time_to_trigger",
        "a3_offset_rsrp": "offset"
    }

    transformed_params = {}
    for original_key, new_key in CUCP_parameters_mapping.items():
        if original_key in current_gnb_params:
            transformed_params[new_key] = current_gnb_params[original_key]
            logger.info("Mapping '%s' to '%s' with value: %s", original_key, new_key, current_gnb_params[original_key])
    logger.info("Transformed parameters: %s", transformed_params)

    # 4. Compare each key from the request against the transformed parameters.
    # Convert request to a dict (works for pydantic models).
    request_dict = request.dict() if hasattr(request, "dict") else request
    logger.info("Request parameters: %s", request_dict)

    # 5. Iterate over the mapping to validate each parameter:
    #    a) If the request provides a value for a given parameter (i.e. non-None),
    #       then ensure that the corresponding transformed parameter exists and is not None.
    #    b) Then compare the current value with the requested value.
    for original_key, new_key in CUCP_parameters_mapping.items():
        req_value = request_dict.get(original_key)
        if req_value is not None:
            # If the parameter is provided in the request but missing in current parameters or is None.
            if new_key not in transformed_params or transformed_params[new_key] is None:
                logger.error("Parameter '%s' is provided in request but missing in current GNB parameters. Error code: %s",
                             original_key, "VP-409")
                return {
                    "status": "fail",
                    "error_code": "VP-409",
                    "message": f"Parameter '{original_key}' is provided in request but missing in current GNB parameters."
                }
            # If the parameter exists but is unchanged.
            if transformed_params[new_key] == req_value:
                logger.warning("Parameter '%s' is unchanged (value: %s). Error code: %s",
                               original_key, req_value, "VP-409")
                return {
                    "status": "fail",
                    #"error_code": "VP-410",
                    "error_code": "VP-409",
                    "message": f"Parameter '{original_key}' value is unchanged."
                }
            else:
                logger.debug("Parameter '%s' changed from %s to %s.", original_key, transformed_params[new_key], req_value)

    logger.info("Parameter validation successful. Updated parameters: %s", transformed_params)
    return {"status": "success", "data": transformed_params}


import json
import math

async def json_to_dynamic_html_table(json_data, page: int = 1, rows_per_page: int = 10):
    """
    Converts a JSON object or list of dictionaries into an HTML table with a scrollable container and pagination links.

    :param json_data: dict, list of dicts, or a JSON string representing the data.
    :param page: int - current page number (default is 1)
    :param rows_per_page: int - number of rows to display per page (default is 10)
    :return: str containing the complete HTML with the table and pagination
    """
    # Parse json_data if it's a JSON string
    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    # Ensure data is a list of dictionaries
    if isinstance(json_data, dict):
        json_data = [json_data]

    # Total items and total pages
    total_items = len(json_data)
    total_pages = math.ceil(total_items / rows_per_page)

    # Ensure the page number is within valid range
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    # Compute start and end indices for the current page
    start_index = (page - 1) * rows_per_page
    end_index = start_index + rows_per_page
    paginated_data = json_data[start_index:end_index]

    # Get the headers from the keys of the first dictionary
    headers = list(json_data[0].keys()) if json_data else []

    # Build the HTML table header row
    header_cells = "".join(f"<th>{header}</th>" for header in headers)
    header_row = f"<tr>{header_cells}</tr>"

    # Build the HTML table data rows
    data_rows = ""
    for item in paginated_data:
        row_cells = "".join(f"<td>{item.get(header, '')}</td>" for header in headers)
        data_rows += f"<tr>{row_cells}</tr>\n"

    # Assemble the complete table HTML
    table_html = f"""
    <table border="1" cellspacing="0" cellpadding="5" style="width:100%; border-collapse: collapse;">
        <thead>
            {header_row}
        </thead>
        <tbody>
            {data_rows}
        </tbody>
    </table>
    """

    # Create pagination links
    pagination_links = ""

    if page > 1:
        pagination_links += f'<a href="?page={page - 1}">Previous</a> '

    for p in range(1, total_pages + 1):
        if p == page:
            pagination_links += f'<strong>{p}</strong> '
        else:
            pagination_links += f'<a href="?page={p}">{p}</a> '

    if page < total_pages:
        pagination_links += f'<a href="?page={page + 1}">Next</a>'

    # Wrap the table in a scrollable container and add the pagination links below
    html_output = f"""
    <html>
    <head>
        <style>
            .scrollable-table-container {{
                max-height: 300px;
                overflow-y: auto;
                border: 1px solid #ccc;
                padding: 5px;
            }}
            .pagination {{
                margin-top: 10px;
                font-size: 14px;
            }}
            .pagination a {{
                margin: 0 5px;
                text-decoration: none;
                color: blue;
            }}
            .pagination strong {{
                margin: 0 5px;
            }}
        </style>
    </head>
    <body>
        <div class="scrollable-table-container">
            {table_html}
        </div>
        <div class="pagination">
            {pagination_links}
        </div>
    </body>
    </html>
    """
    return html_output


async def get_data_by_cell_id_node_id_revalidate(
        cell_id: str = None, cell_name: str = None, node_id: str = None,
        band: str = None, purpose: str = None, frequency: str = None,
        index: str = None, vendor: str = None
):
    """
    Fetches data from DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_CONFIG_CUCP_PARAMETERS table
    with dynamic filtering. Supports NULL values by using IS NULL when needed.
    """

    if vendor and vendor.lower() == 'samsung':
        table_name = "DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_CONFIG_CUCP_PARAMETERS"

        query_params = {}
        conditions = []

        # Dynamically build conditions based on provided values
        if node_id is not None:
            conditions.append("gnodeb_id = :node_id")
            query_params["node_id"] = node_id
        else:
            conditions.append("gnodeb_id IS NULL")

        if cell_id is not None:
            conditions.append("cell_identity = :cell_id")
            query_params["cell_id"] = cell_id
        else:
            conditions.append("cell_identity IS NULL")

        if cell_name is not None:
            conditions.append("cell_name = :cell_name")
            query_params["cell_name"] = cell_name
        else:
            conditions.append("cell_name IS NULL")

        if band is not None:
            conditions.append("band = :band")
            query_params["band"] = band
        else:
            conditions.append("band IS NULL")

        if purpose is not None:
            conditions.append("purpose = :purpose")
            query_params["purpose"] = purpose
        else:
            conditions.append("purpose IS NULL")

        if index is not None:
            conditions.append("report_config_entry_index = :index")
            query_params["index"] = index
        else:
            conditions.append("report_config_entry_index IS NULL")

        if frequency is not None:
            conditions.append("ssb_config_ssb_freq = :frequency")
            query_params["frequency"] = frequency
        else:
            conditions.append("ssb_config_ssb_freq IS NULL")

        # Construct final query dynamically
        query_text = f"""
            SELECT * 
            FROM {table_name}
            WHERE {' AND '.join(conditions)}
            ORDER BY cell_identity ASC
            LIMIT 25;
        """

        query = text(query_text)

        # Debugging: Generate a final query string with actual values
        def format_value(val):
            if val is None:
                return "NULL"
            if isinstance(val, str):
                return f"'{val}'"
            return str(val)

        final_query_debug = query_text
        for key, value in query_params.items():
            final_query_debug = final_query_debug.replace(f":{key}", format_value(value))

        logger.info("Final Query (debug): %s", final_query_debug)

        async with snow_db.get_db_session() as session:
            try:
                logger.info("Executing query...")
                result = await run_in_threadpool(session.execute, query, query_params)

                rows = result.fetchall()
                column_names = result.keys()
                logger.info("Fetched column names: %s", column_names)

                json_results = [
                    {column.lower(): convert_to_serializable(value) for column, value in zip(column_names, row)}
                    for row in rows
                ]

                json_results = [
                    OrderedDict([("serial_number", idx + 1)] + list(item.items()))
                    for idx, item in enumerate(json_results)
                ]

                json_output = json.dumps(json_results, indent=4)
                logger.info("JSON Output: %s", json_output)

                return json_results
            except Exception as e:
                logger.error("Error occurred while fetching data: %s", e)
                return []


async def generate_html_table(data: list[dict]) -> str:
    """Generates an HTML table with a fixed first column and scrollable content."""
    if not data:
        return "<p>No data available</p>"

    columns = list(data[0].keys())

    html_parts = [
        '<div style="max-height: 250px; overflow-x: auto; overflow-y: auto; border: 1px solid #ddd; '
        'border-radius: 8px; width: 100%; max-width: 100%; white-space: nowrap; position: relative;">'
        '<table style="border-collapse: collapse; min-width: 800px; width: 100%; font-size: 14px; text-align: left;">'
        '<thead style="position: sticky; top: 0; background-color: #f1f1f1; z-index: 2;">'
        '<tr>'
    ]

    # Add table headers with sticky first column
    for index, col in enumerate(columns):
        sticky_style = "left: 0; z-index: 3; background-color: white;" if index == 0 else ""
        html_parts.append(f'<th style="border: 1px solid #ddd; padding: 8px; position: sticky; {sticky_style}">{col}</th>')

    html_parts.append("</tr></thead><tbody>")

    # Add table rows with sticky first column
    for row in data:
        html_parts.append("<tr>")
        for index, col in enumerate(columns):
            sticky_style = "left: 0; z-index: 1; background-color: white;" if index == 0 else ""
            html_parts.append(f'<td style="border: 1px solid #ddd; padding: 8px; position: sticky; {sticky_style}">{row[col]}</td>')
        html_parts.append("</tr>")

    html_parts.append("</tbody></table></div>")

    return "".join(html_parts)

async def extract_change_number(snow_log):
    """
    Extracts the change number from the 'snow_log' field of the given item.

    Args:
        item (dict): A dictionary that contains a 'snow_log' key.

    Returns:
        str or None: The extracted change number if found, otherwise None.
    """
    # Regex pattern to match a change number starting with "CHG"
    pattern = r"(CHG[A-Z0-9]+)"
    log = snow_log

    # Search the log string for the change number
    match = re.search(pattern, log)
    if match:
        return match.group(1)
    return snow_log


def find_snow_log(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "snow_log":
                return value
            result = find_snow_log(value)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_snow_log(item)
            if result is not None:
                return result
    return None
