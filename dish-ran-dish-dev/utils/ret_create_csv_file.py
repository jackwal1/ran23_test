import pandas as pd
import asyncio
from io import BytesIO
from datetime import datetime
from typing import List, Optional
import utils.constants as constant
from typing import List
import httpx
import logging
from datetime import datetime
from utils import constants as CONST
import aiofiles
import os

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

samsung_mapping = {
    "usmip": "usmip",
    "duid": "duid",
    "ruid": "ruid",
    "aldid": "aldid",
    "antennaid": "antennaid",
}

mavenir_mapping = {
    "ip": "ip",
    "ruid": "ruid",
    "port": "port",
    "hdlc_address": "hdlc_address",
    "antenna_unit": "antenna_unit",
}


a1_mapping = {
    "gnb": "gnodeb-id",
    "cell_id": "cell-identity",
    "index": "index",
    "trigger_quantity": "trigger-quantity",
    "threshold_rsrp": "a1-threshold-rsrp",
    "hysteresis": "a1-hysteresis",
    "time_to_trigger": "a1-time-to-trigger"
}

a2_mapping = {
    "gnb": "gnodeb-id",
    "cell_id": "cell-identity",
    "index": "index",
    "trigger_quantity": "trigger-quantity",
    "threshold_rsrp": "a2-threshold-rsrp",
    "hysteresis": "a2-hysteresis",
    "time_to_trigger": "a2-time-to-trigger"
}

a3_mapping = {
    "gnb": "gnodeb-id",
    "cell_id": "cell-identity",
    "index": "index",
    "trigger_quantity": "trigger-quantity",
    "offset": "a3-offset-rsrp",
    "hysteresis": "a3-hysteresis",
    "time_to_trigger": "a3-time-to-trigger"
}

a4_mapping = {
    "gnb": "gnodeb-id",
    "cell_id": "cell-identity",
    "index": "index",
    "trigger_quantity": "trigger-quantity",
    "threshold_rsrp": "a4-threshold-rsrp",
    "hysteresis": "a4-hysteresis",
    "time_to_trigger": "a4-time-to-trigger"
}

a5_mapping = {
    "gnb": "gnodeb-id",
    "cell_id": "cell-identity",
    "index": "index",
    "trigger_quantity": "trigger-quantity",
    "threshold1_rsrp": "a5-threshold1-rsrp",
    "threshold2_rsrp": "a5-threshold2-rsrp",
    "hysteresis": "a5-hysteresis",
    "time_to_trigger": "a5-time-to-trigger"
}



async def create_csv_async(data: List[dict], input_request) -> BytesIO:
    """
    Asynchronously create a CSV file from the data while maintaining the order of headers.
    """
    if input_request.vendor.lower() == 'samsung':
        key_mapping = samsung_mapping
    elif input_request.vendor.lower() == 'mavenir':
        key_mapping = mavenir_mapping
    else:
        raise ValueError("Unsupported vendor")

    # Define column order explicitly
    column_order = list(key_mapping.values()) + ["tilt"]

    # Filter and rename keys while maintaining order
    filtered_data = []
    for item in data:
        new_item = {key_mapping[k]: item[k] for k in key_mapping if k in item}
        new_item["tilt"] = input_request.tilt_value
        filtered_data.append(new_item)

    # Create DataFrame with column order
    df = pd.DataFrame(filtered_data, columns=column_order)

    # Log DataFrame
    logging.info("DataFrame created with columns: %s\n%s", column_order, df.to_string(index=False))

    # Create CSV file in memory
    csv_buffer = BytesIO()
    loop = asyncio.get_running_loop()
    csv_str = await loop.run_in_executor(None, lambda: df.to_csv(index=False, sep=','))

    # Write to buffer
    csv_buffer.write(csv_str.encode('utf-8'))
    csv_buffer.seek(0)

    # Save CSV to disk asynchronously
    #root_path = os.path.join(os.getcwd(), "file.csv")
    #async with aiofiles.open(root_path, 'wb') as f:
        #await f.write(csv_buffer.getvalue())

    return csv_buffer


async def create_excel_async_for_threshold(data: List[dict], input_request) -> BytesIO:
    """
    Asynchronously create an Excel file from the data while maintaining the order of headers and saving it locally.
    """
    # Define event mappings
    event_mappings = {
        'a1': a1_mapping,
        'a2': a2_mapping,
        'a3': a3_mapping,
        'a4': a4_mapping,
        'a5': a5_mapping
    }

    # Validate input event
    event_key = input_request.event.lower()
    if event_key not in event_mappings:
        raise ValueError("Unsupported Event")

    key_mapping = event_mappings[event_key]

    # Define column order explicitly
    column_order = list(key_mapping.values())

    # Convert model instance to dictionary and filter relevant fields
    request_data = input_request.dict(exclude_none=True)

    # Correct iteration: filter & rename keys while maintaining order
    filtered_data = {key_mapping[k]: request_data[k] for k in request_data if k in key_mapping}

    # Create DataFrame (Ensure it's a list of dicts)
    df = pd.DataFrame([filtered_data], columns=column_order)

    # Replace NaN values with empty strings
    df = df.fillna("")

    # Log DataFrame
    logging.info("DataFrame created with columns: %s\n%s", column_order, df.to_string(index=False))

    # Convert to Markdown
    markdown_table = df.to_markdown(index=False)

    logging.info("DataFrame created with columns:\n%s", markdown_table)

    # Determine the sheet name dynamically (e.g., "a1-report-config")
    sheet_name = f"{event_key}-report-config"

    # Create Excel file in memory
    excel_buffer = BytesIO()
    loop = asyncio.get_running_loop()

    # Run Excel writing operation in an executor to avoid blocking
    await loop.run_in_executor(None, lambda: df.to_excel(excel_buffer, index=False, sheet_name=sheet_name, engine="openpyxl"))

    excel_buffer.seek(0)  # Reset buffer position

    # Save to local file asynchronously
    '''timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(os.getcwd(), f"threshold_data_{timestamp}.xlsx")

    async with asyncio.Lock():  # Ensure thread safety in async environments
        await loop.run_in_executor(None, lambda: df.to_excel(file_path, index=False, sheet_name=sheet_name, engine="openpyxl"))

    logging.info("Excel file saved at: %s", file_path)'''

    return excel_buffer


async def post_csv_to_endpoint(
        csv_data: BytesIO, transaction_id: str, vendor: str, cell_data: dict, user: str,auth_token: Optional[str] = None
) -> dict:
    """
    Posts CSV data to the configured endpoint.
    """
    # Validate vendor
    vendor = vendor.lower()
    if vendor == "samsung":
        UPLOAD_ENDPOINT = constant.ret_samsung_csv_endpoint
    elif vendor == "mavenir":
        UPLOAD_ENDPOINT = constant.ret_mavenir_csv_endpoint
    else:
        raise ValueError(f"Unsupported vendor: {vendor}")

    # Ensure "aoi" is present in cell_data
    if "aoi" not in cell_data:
        raise ValueError("Missing required field: 'aoi' in cell_data")

    user = user.split("@")[0]
    logging.info(f"Transaction initiated for user: {user}")

    # Set headers
    #headers = {"Transaction-ID": transaction_id}
    #if auth_token:
        #headers["Authorization"] = f"Bearer {auth_token}"

    # Prepare file & form data
    files = {"reference": ("refile.csv", csv_data, "text/csv")}
    data = {"aoi": cell_data["aoi"], "user" : user,  "Authorization": auth_token}

    logging.info(f"data:: {data}")

    logging.info(f"Sending CSV data to {UPLOAD_ENDPOINT}")

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            UPLOAD_ENDPOINT,
            #headers=headers,
            files=files,
            data=data,
            timeout=60.0
        )
        logging.info(f"CSV uploaded successfully to {UPLOAD_ENDPOINT}, Status Code: {response.status_code}")
        response_json = response.json()
        logging.info(f"Response JSON: {response_json}")

        return response_json


async def post_excel_to_threshold_endpoint(data,
        excel_data: BytesIO, transaction_id: str, input_request,auth_token: Optional[str] = None, ret_data: Optional[dict] = None
) -> dict:
    """
    Posts CSV data to the configured endpoint.
    """
    # Validate vendor
    vendor = input_request.vendor.lower()
    if vendor == "samsung":
        UPLOAD_ENDPOINT = constant.threshold_samsung_csv_endpoint
    #elif input_request.vendor.lower() == "mavenir":
        #UPLOAD_ENDPOINT = constant.threshold_mavenir_csv_endpoint
    else:
        raise ValueError(f"Unsupported vendor: {vendor}")

    # Ensure "aoi" is present in input_request
    if not ret_data or not ret_data.get("aoi"):
        raise ValueError("Missing required field: 'aoi' in input_request")

    if not ret_data or not ret_data.get("usmip"):
        raise ValueError("Missing required field: 'ip' in input_request")

    user = input_request.user_id.split("@")[0]
    logging.info(f"Transaction initiated for user: {user}")


    # Set headers
    #headers = {"Transaction-ID": transaction_id}
    #if auth_token:
        #["Authorization"] = f"Bearer {auth_token}"

    # Prepare file & form data
    files = {
        "reference": (
            "upload.xlsx",  # File name with .xlsx extension
            excel_data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    }
    data = {"user" :user,"aoi":  ret_data.get("aoi"), "Authorization": auth_token, "ip": ret_data.get("usmip")}

    logging.info(f"data:: {data}")

    logging.info(f"Sending Excel data to {UPLOAD_ENDPOINT}")

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            UPLOAD_ENDPOINT,
            #headers=headers,
            files=files,
            data=data,
            timeout=60.0
        )
        logging.info(f"Excel uploaded successfully to {UPLOAD_ENDPOINT}, Status Code: {response.status_code}")
        response_json = response.json()
        logging.info(f"Response JSON: {response_json}")

        return response_json


async def validate_params(event_obj, event_type):
    event_mappings = {
        'a1': a1_mapping,
        'a2': a2_mapping,
        'a3': a3_mapping,
        'a4': a4_mapping,
        'a5': a5_mapping
    }

    if event_type not in event_mappings:
        return False, "Invalid event type"

    mapping = event_mappings[event_type]

    # Mandatory fields
    mandatory_fields = ["gnb", "cell_id", "index"]
    if not all(getattr(event_obj, field, None) for field in mandatory_fields):
        return False, "Mandatory params ar missing"

    # At least one optional field must exist
    optional_fields = set(mapping.keys()) - set(mandatory_fields)

    # At least one optional field must exist
    if event_obj is None:
        return False, "Event object is None"

    for field in optional_fields:
        if getattr(event_obj, field, None) is not None:
            return True, "Valid parameters"

    logging.info("No Parameters found to update")
    return False, "No Parameters found to update"



