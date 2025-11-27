from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from llms.llms import chatmodel_ran_automation, llama_chatmodel_react
from langchain_core.prompts import ChatPromptTemplate
import traceback
import utils.ran_automation_validation as validate
from utils.ret_cell_extraction import extract_ret_data
import utils.ret_transaction_logging as execute_params
import utils.user_authorization_wrapper as validate_email
import utils.ret_create_csv_file as csv_util
import utils.ret_transaction_logging as log_transaction
import utils.gnb_validate_gpl_parameters_util as gnb_validate_util
import time
from langchain_core.exceptions import OutputParserException
from prompts.ran_automation_prompt import GNB_PARAMETERS_EXTRACT_PROMPT_TEMPLATE_2
import httpx
from decimal import Decimal
from decimal import Decimal, InvalidOperation
import re
from fastapi.responses import JSONResponse
from routers.pydantic_model import ChatRequest,AutomationChatResponse
from uuid import uuid4
import utils.constants as constant
import json
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from graph.ran_automation_agent_graph_nodes import initialize_agent
from utils.ret_cell_extraction import extract_json_from_string
import logging

log_level = getattr(logging, constant.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

# Define API Router
ran_automation_router = APIRouter(prefix="/watsonx/ran/automation", tags=["RAN Part - 2 : Automation"])

# Response Model
class ExtractParamsResponse(BaseModel):
    is_valid: bool
    query_type: Optional[str] = None
    table_type: Optional[str] = None
    params: Optional[Dict[str, Optional[str]]] = None
    message: str
    error_code: Optional[str] = None

class ExtractParamsRequest(BaseModel):
    query: str
    transaction_id: str
    user_id:Optional[str] = None
    token:Optional[str] = None

# Request Parsing Models
class TiltModel(BaseModel):
    vendor: Optional[str] = Field(None, description="Name of the vendor, e.g., Samsung or Mavenir")
    tilt_value: Optional[str] = Field(None, description="tilt value which needs to be updated in given in input it must be a number, if not present then None")
    cell_id: Optional[str] = Field(None, description="Cell name or ID provided in the input")
    hldc_add: Optional[str] = Field(None, description=" HLDC (High-Level Data Link Control) addresses provided in the input")
    aldid: Optional[str] = Field(None, description="Active Logical Device ID used to identify logical devices within the RAN.")
    band_sector:Optional[str] = Field(None, description="valid values LB / MB")

# Request Parsing Models
class GNBModel(BaseModel):
    vendor: Optional[str] = Field(None, description="Name of the vendor provided in input")
    gnb: Optional[str] = Field(None, description="The gNB provided in the input")
    cell_id: Optional[str] = Field(None, description="Cell name or ID provided in the input")
    threshold_rsrp: Optional[str] = Field(None, description="a2-threshold-rsrp value in the input")
    threshold2_rsrp: Optional[str] = Field(None, description="a5-threshold2-rsrp value in the input")
    threshold1_rsrp: Optional[str] = Field(None, description="a5-threshold1-rsrp value in the input")
    hysteresis: Optional[str] = Field(None, description="Hysteresis value (if provided)")
    time_to_trigger: Optional[str] = Field(None, description="Time-to-trigger value (if provided)")
    index: Optional[str] = Field(None, description="ReportConfig index (if provided)")
    trigger_quantity: Optional[str] = Field(None, description="Trigger Quantity mentioned (if provided)")
    event: Optional[str] = Field(None, description="Event value provided")
    band: Optional[str] = Field(None, description="Band value provided")
    offset_rsrp: Optional[str] = Field(None, description="a3-offset-rsrp value in the input")
    cell_name: Optional[str] = Field(None, description="Cell name (if provided)")
    purpose: Optional[str] = Field(None, description="purpose of change (if provided)")
    band_sector:Optional[str] = Field(None, description="Sector provided in the input (if provided)")

class TableTypeModel(BaseModel):
    table_type: Optional[str] = Field(None, description="Table type: 'RET', 'GNB', or None")

class QueryTypeModel(BaseModel):
    query_type: Optional[str] = Field(None, description="Query type: 'Update' or 'Fallback'")

# Utility Functions
async def extract_query_type(query: str) -> Optional[str]:
    """
    Extracts the query type from the given input.
    Identifies if the query is related to 'Update' or 'Fallback' for RAN automation.
    """
    prompt = ChatPromptTemplate.from_template(
        "Analyze the input query to determine its type. The query can belong to one of the following categories:\n\n"
        "- **Update the RET table**: The RET table stores antenna tilt configurations for optimizing signal performance.\n"
        "- **Update the GNB table**: The GNB table contains configurations for managing 5G base stations.\n"
        "- **Fallback**: If the query doesn't match either category, classify it as 'Fallback'.\n\n"
        "Only valid actions are 'Update/Modify/Change'. Insertion of data or any other action type is not allowed.\n"
        "If action is insert or query then it is a `Fallback`."
        "Valid query types are 'Update' or 'Fallback'. Input query: {query}"
    )
    chain = prompt | chatmodel_ran_automation.with_structured_output(QueryTypeModel)
    response = await chain.ainvoke({"query": query})
    return response.query_type

async def extract_table_type(query: str) -> Optional[str]:
    """
    Extracts the table type from the given input.
    Identifies if the query is related to the 'RET' or 'GNB' table.
    """
    prompt = ChatPromptTemplate.from_template(
        "Determine the table type referenced in the input query. Valid table types include:\n\n"
        "- **RET (Remote Electrical Tilt)**: Used for remote adjustments of antenna tilt to optimize network coverage and quality.\n"
        "- **GNB (gNodeB)**: Represents 5G base station configurations and management details. User query will contain threshold, offset, hysteresis, index, event etc.\n"
        "Valid table types are 'RET', 'GNB', or None. Input query: {query}"
    )
    chain = prompt | chatmodel_ran_automation.with_structured_output(TableTypeModel)
    response = await chain.ainvoke({"query": query})
    return response.table_type

async def extract_tilt_params(query: str) -> TiltModel:
    """
    Extracts tilt-related parameters like vendor, tilt_value, and cell_id from the given input.
    """
    prompt = ChatPromptTemplate.from_template(
        """Act as a RAN engineer and extract the following parameters from the input query:
    - Vendor: Name of the vendor
    - Tilt Value: The specified tilt adjustment value to be updated (must be a number)
    - Cell ID: The name or identifier of the cell
    - HDLC Address: High-Level Data Link Control (HDLC) address
    - ALDID: Active Logical Device ID
    - band_sector: Low Band(LB)/ Mid Band(MB)
    
    Here are some examples:
    
    Example 1:
    Input: "Change tilt value to 3 for CVCLE00375A_2_n29_E_DL"
    Output:
    - Vendor: null
    - Tilt Value: 3
    - Cell ID: CVCLE00375A_2_n29_E_DL
    - HDLC Address: null
    - ALDID: null
    - band_sector: null
    
    Example 2:
    Input: "Update tilt value for BOBOS01075F_1 for Mid Band to value 66"
    Output:
    - Vendor: null
    - Tilt Value: 66
    - Cell ID: BOBOS01075F_1
    - HDLC Address: null
    - ALDID: null
    - band_sector: MB
    
    Example 3:
    Input: "I want to update tilt value"
    Output:
    - Vendor: null
    - Tilt Value: null
    - Cell ID: null
    - HDLC Address: null
    - ALDID: null
    - band_sector: null
    
    Example 4:
    Input: "I want to change tilt value"
    Output:
    - Vendor: null
    - Tilt Value: null
    - Cell ID: null
    - HDLC Address: null
    - ALDID: null
    - band_sector: null
    
    Example 5:
    Input: "Update tilt value to 66 for BOBOS01075F_1 for Low Band"
    Output:
    - Vendor: null
    - Tilt Value: 66
    - Cell ID: BOBOS01075F_1
    - HDLC Address: null
    - ALDID: null
    - band_sector: LB
    
    Example 6:
    Input: "Set Samsung cell TESTCELL01_1_n78 tilt to 5 with HDLC 2 and ALDID 5"
    Output:
    - Vendor: Samsung
    - Tilt Value: 5
    - Cell ID: TESTCELL01_1_n78
    - HDLC Address: 2
    - ALDID: 5
    - band_sector: null
    
    Example 7:
    Input: " i want to update tilt value for a cell name"
    Output:
    - Vendor: null
    - Tilt Value: null
    - Cell ID: null
    - HDLC Address: null
    - ALDID: null
    - band_sector: null
    
    Now extract parameters from the following input query:
    
    Input query: {query}
    
    Output:"""
    )
    chain = prompt | chatmodel_ran_automation.with_structured_output(TiltModel)
    try:
        response = await chain.ainvoke({"query": query})
        # Ensure response fields are cleaned up
        cleaned_data = {
            field: None if value in ["", "null"] else value
            for field, value in response.dict().items()
        }

        return TiltModel(**cleaned_data)
    except OutputParserException as e:
        print("Parsing Error:", e)
        return None  # Return None or handle gracefully

class SectorModel(BaseModel):
    sector: Optional[str]

async def extract_sector(query: str) -> TiltModel:
    """
    Extracts sector information from a RAN-related user query.
    """

    prompt = ChatPromptTemplate.from_template(
        "You are a telecom RAN expert. Extract the 'sector' value from the given user query.\n"
        "- The sector typically refers to a number like 1, 2, or 3 associated with a cell site.\n"
        "- Output only the sector value.\n\n"
        "Examples:\n"
        "user query: Change tilt value to 3 for cell name BOBOS01075F for sector 2\n"
        "Sector: 2\n\n"
        "user query: Please update the azimuth of sector 1 for site ID DELHI1234\n"
        "Sector: 1\n\n"
        "user query: Modify electrical tilt for sector 3 of cell MUMBAI_2023\n"
        "Sector: 3\n\n"
        "user query: Perform audit on all sectors of site BOBOS01075F\n"
        "Sector: null\n\n"
        "user query: Sector 2 antenna has physical tilt issues at site HYD456\n"
        "Sector: 2\n\n"
        "Input query: {query}"
    )

    chain = prompt | chatmodel_ran_automation.with_structured_output(SectorModel)

    try:
        response = await chain.ainvoke({"query": query})
        # Clean up any empty/null fields
        cleaned_data = {
            field: None if value in ["", "null"] else value
            for field, value in response.dict().items()
        }
        return SectorModel(**cleaned_data)
    except OutputParserException as e:
        print("Parsing Error:", e)
        return None

async def extract_gnb_params(query: str) -> GNBModel:
    """
    Extracts gnb-related parameters like vendor, gnodeb_id, cell_id, threshold_rsrp, hysteresis, time_to_trigger and index from the given input.
    """
    prompt = ChatPromptTemplate.from_template(GNB_PARAMETERS_EXTRACT_PROMPT_TEMPLATE_2)
    chain = prompt | llama_chatmodel_react.with_structured_output(GNBModel)
    try:
        response = await chain.ainvoke({"query": query})
        # Ensure response fields are cleaned up
        cleaned_data = {
            field: None if value in ["", "null"] else value
            for field, value in response.dict().items()
        }

        return GNBModel(**cleaned_data)

    except OutputParserException as e:
        print("Parsing Error:", e)
        return None  # Return None or handle gracefully


# API Endpoint
@ran_automation_router.post(
    "/extract_params",
    summary="Extract Parameters for RAN Automation",
    response_model=ExtractParamsResponse,
    status_code=status.HTTP_200_OK,
    response_description="Returns extracted query type, table type, and parameters from the user input.",
)
async def query_user_question(request: ExtractParamsRequest):
    """
    Extracts query type, table type, and parameters from the user input for RAN automation.
    """
    logger.info(f"Processing query: {request.query}")
    logger.info(f"Transaction ID: {request.transaction_id}")
    try:

        if  constant.email_validation_required.lower() == 'y':
            # Step 1: Validate email
            logger.info(f"[{request.transaction_id}] Step 1/6: Starting email validation for {request.user_id}")

            email_validation = await validate_email.validate_email_address(
                user_email=request.user_id,
                auth_token=request.token
            )

            data_output = email_validation.get("data")
            logger.info(f"email validation response: {data_output}")
            if not data_output:
                logger.info(f"[{request.transaction_id}] Email validation failed for {request.user_id}")
                return ExtractParamsResponse(
                    is_valid=False,
                    message="Email validation failed",
                    error_code='UP-400'
                )
                return response
            logger.info(f"[{request.transaction_id}] Email validation successful")


        # Extract query type
        query_type = await extract_query_type(request.query)
        logger.info(f"query_type : {query_type}")
        if not query_type or query_type.lower() not in ["update"]:
            return ExtractParamsResponse(
                is_valid=False,
                message="Invalid query type. Supported types are 'Update'.",
                error_code= 'EP-100'
            )

        # Extract table type
        table_type = await extract_table_type(request.query)
        logger.info(f"table_type : {table_type}")
        if not table_type or table_type.upper() not in ["RET", "GNB"]:
            return ExtractParamsResponse(
                is_valid=False,
                message="Invalid table type. Supported types are 'RET' or 'GNB'.",
                error_code= 'EP-101'
            )

        # Extract tilt parameters if table type is RET
        params = {}
        if table_type.upper() == 'RET':
            params = await extract_tilt_params(request.query)
            params = params.dict()
            cell_name = params.get("cell_id")
            logger.info(f"cell name :{cell_name}")
            if cell_name:
                match = re.search(r'_(\d+)', cell_name)
                if match and params.get("band_sector") is None:
                    params["band_sector"] = match.group(1)
                elif match and params.get("band_sector") is not None:
                    params["band_sector"] = params.get("band_sector")+ "_" +match.group(1)
                else:
                    sector_model = await extract_sector(request.query)
                    if sector_model and sector_model.sector and params.get("band_sector") is None:
                        params["band_sector"] = sector_model.sector
                    elif sector_model and sector_model.sector and params.get("band_sector") is not None:
                        params["band_sector"] = params.get("band_sector")+ "_" +sector_model.sector

                vendor = await validate.get_vendor_by_cellname(cell_name)
                if vendor and vendor != "Not Found":
                    params["vendor"] = vendor
                else:
                    logger.info(f"Vendor not found for cell name: {cell_name}")



        if table_type.upper() == 'GNB':
            params = await extract_gnb_params(request.query)
            logger.info(f"params :{params}")
            params = params.dict()
            params["vendor"] = "Samsung"

            # Check and extract sector from cell_name
            cell_name = params.get("cell_name")
            if cell_name:
                match = re.search(r'_(\d+)', cell_name)
                if match:
                    params["band_sector"] = match.group(1)


        # Construct valid response
        response = ExtractParamsResponse(
            is_valid=True,
            query_type=query_type,
            table_type=table_type,
            params=params,
            message="Parameters extracted successfully."
        )
        logger.info(f"Final response: {response.dict()}")
        return response

    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error processing query: {request.query}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the query: {str(e)}"
        )
#================================================================================


class ValidateParamsResponse(BaseModel):
    message: str
    existing_params: Optional[Dict[str, Optional[Any]]] = None
    gnb_existing_params: Optional[List[Dict[str, Any]]] = None
    ret_existing_params: Optional[List[Dict[str, Any]]] = None
    validation_errors: Optional[Dict[str, Any]] = None
    dish_recommendation_table: Optional[str] = None
    existing_param_table: Optional[str] = None
    error_code: Optional[str] = None
    status:str

class ValidateParamsRequest(BaseModel):
    table_type: str
    vendor: str
    transaction_id: str
    user_id:Optional[str] = None
    token:Optional[str] = None
    #RET
    cell_id: Optional[str] = None
    tilt_value: Optional[str] = None
    hldc_address: Optional[str] = None
    aldid : Optional[str] = None


    usmip: Optional[str] = None
    duid: Optional[str] = None
    ruid: Optional[str] = None
    antennaid: Optional[str] = None
    antennamodel: Optional[str] = None
    #GNB
    gnb: Optional[str] = None
    threshold_rsrp: Optional[str] = None
    hysteresis: Optional[str] = None
    time_to_trigger: Optional[str] = None
    index: Optional[str] = None
    event: Optional[str] = None
    cell_name: Optional[str] = None

    trigger_quantity: Optional[str] = None
    band: Optional[str] = None

    threshold2_rsrp: Optional[str] = None
    cell_num: Optional[str] = None
    threshold1_rsrp: Optional[str] = None

    offset: Optional[str] = None
    purpose: Optional[str] = None
    frequency: Optional[str] = None

    re_validate: Optional[str] = None


@ran_automation_router.post(
    "/validate_params",
    summary="Validate Parameters for RAN Automation",
    response_model=ValidateParamsResponse,
    status_code=status.HTTP_200_OK,
    response_description=" Validate parameters for RAN automation.",
)
async def validate_params(request: ValidateParamsRequest):
    """
    Validate parameters for RAN automation.
    """
    logger.info(f"Transaction ID: {request.transaction_id}")
    try:
        final_message = None
        table_response = None
        dish_valid_params_response = None
        response = {"status": "success", "message": "Validation successful", "error_code": None}

        if  constant.email_validation_required.lower() == 'y':
            # Step 1: Validate email
            logger.info(f"[{request.transaction_id}] Step 1/6: Starting email validation for {request.user_id}")

            email_validation = await validate_email.validate_email_address(
                user_email=request.user_id,
                auth_token=request.token
            )

            data_output = email_validation.get("data")
            if not data_output:
                logger.info(f"[{request.transaction_id}] Email validation failed for {request.user_id}")
                response.update(
                    status="fail",
                    message=f"Email validation failed for : {request.user_id} .",
                    error_code='VP-400'
                )
                return response
            logger.info(f"[{request.transaction_id}] Email validation successful")

        if request.table_type.lower() == "ret":
            # Step 1: Extract existing data by cell_id

            if request.re_validate and request.re_validate.lower() == 'y' and request.vendor.lower() == 'samsung':

                existing_data = await validate.get_data_for_ret_revalidate(
                    cell_name=request.cell_id,
                    hldc_address=request.hldc_address,
                    aldid=request.aldid,
                    usmip=request.usmip,
                    duid=request.duid,
                    ruid=request.ruid,
                    antennaid=request.antennaid,
                    antennamodel=request.antennamodel,
                    vendor=request.vendor
                )
            else:
                existing_data = await validate.get_data_for_ret(request.cell_id, request.hldc_address, request.aldid,request.vendor)

            if not existing_data:
                response.update(
                    status="fail",
                    message="Cell ID not available in the database.",
                    error_code='VP-103'
                )
                logger.info(f"Validation failed: {response}")
                return response

            if existing_data and len(existing_data) >1 :
                logger.info(f"Filtering Current RET parameters to only show keys that is required:")
                filtered_current_ret_params = await gnb_validate_util.filter_dicts_by_keys(existing_data)
                logger.info(f"Converting to markdown Table format:")
                #existing_param_table = await gnb_validate_util.json_to_dynamic_markdown(filtered_current_ret_params)
                existing_param_table = await gnb_validate_util.generate_html_table(filtered_current_ret_params)

                response.update(
                    status="fail",
                    message=f"Multiple rows found for the input request.",
                    error_code='VP-311',
                    ret_existing_params = existing_data,
                    existing_param_table = existing_param_table
                )
                logger.info(f"Validation failed: {response}")
                return response

            # Step 2: Validate tilt value

            # Retrieve current tilt based on vendor
            if request.vendor.lower() in ['mavenir', 'samsung']:
                current_tilt = existing_data[0].get("tilt")
            else:
                current_tilt = None

            present_tilt = Decimal(str(request.tilt_value))

            # If current_tilt exists, convert and compare; otherwise, skip equality check
            '''if current_tilt is not None:
                current_tilt = Decimal(str(current_tilt))
                if current_tilt == present_tilt:
                    response.update(
                        status="fail",
                        message="Tilt value already set to the provided value.",
                        error_code='VP-100'
                    )
                    logger.info(f"Validation failed: {response}")
                    return response
            else:
                logger.info("Current tilt not found; skipping equality check.")'''


            min_tilt = existing_data[0].get("minimumtilt")
            logger.info(f"Minimum Tilt Value: {min_tilt}")

            if min_tilt is not None:
                min_tilt = Decimal(str(min_tilt))  # Convert to Decimal for precision

            max_tilt = existing_data[0].get("maximumtilt")
            logger.info(f"Maximum Tilt Value: {max_tilt}")

            if max_tilt is not None:
                max_tilt = Decimal(str(max_tilt))  # Convert to Decimal for precision

            # Validate that both min and max tilt values are present
            if min_tilt is None or max_tilt is None:
                response.update(
                    status="fail",
                    message="Minimum or Maximum tilt value not found.",
                    error_code='VP-118'
                )
                logger.info(f"Validation failed: {response}")
                return response

            if min_tilt is not None and max_tilt is not None:
                if not (min_tilt <= present_tilt <= max_tilt):
                    response.update(
                        status="fail",
                        message=f"Tilt value {request.tilt_value} is out of the allowed range ({min_tilt}-{max_tilt}).",
                        error_code='VP-101'
                    )
                    logger.info(f"Validation failed: {response}")
                    return response

            # If all validations pass
            response.update(
                status="success",
                existing_params=existing_data[0],
                message="Validation successful.",
                error_code='VP-200'
            )
        elif request.table_type.lower() == "gnb":
            logger.info(f"Table Type Found: {request.table_type.lower()}")
            logger.info(f"Logging Parameters:\n"
                        f"request.table_type: {request.table_type if request.table_type else 'None'}\n"
                        f"request.vendor: {request.vendor if request.vendor else 'None'}\n"
                        f"request.transaction_id: {request.transaction_id if request.transaction_id else 'None'}\n"
                        f"request.cell_id: {request.cell_id if request.cell_id else 'None'}\n"
                        f"request.tilt_value: {request.tilt_value if request.tilt_value else 'None'}\n"
                        f"request.hldc_address: {request.hldc_address if request.hldc_address else 'None'}\n"
                        f"request.aldid: {request.aldid if request.aldid else 'None'}\n"
                        f"request.gnb: {request.gnb if request.gnb else 'None'}\n"
                        f"request.threshold_rsrp: {request.threshold_rsrp if request.threshold_rsrp else 'None'}\n"
                        f"request.hysteresis: {request.hysteresis if request.hysteresis else 'None'}\n"
                        f"request.time_to_trigger: {request.time_to_trigger if request.time_to_trigger else 'None'}\n"
                        f"request.index: {request.index if request.index else 'None'}\n"
                        f"request.event: {request.event if request.event else 'None'}\n"
                        f"request.cell_name: {request.cell_name if request.cell_name else 'None'}\n"
                        f"request.trigger_quantity: {request.trigger_quantity if request.trigger_quantity else 'None'}\n"
                        f"request.band: {request.band if request.band else 'None'}\n"
                        f"request.threshold2_rsrp: {request.threshold2_rsrp if request.threshold2_rsrp else 'None'}\n"
                        f"request.cell_num: {request.cell_num if request.cell_num else 'None'}\n"
                        f"request.threshold1_rsrp: {request.threshold1_rsrp if request.threshold1_rsrp else 'None'}\n"
                        f"request.offset: {request.offset if request.offset else 'None'}\n"
                        f"request.purpose: {request.purpose if request.purpose else 'None'}\n"
                        f"request.frequency: {request.frequency if request.frequency else 'None'}")

            if request.re_validate and request.re_validate.lower() == 'y':
                current_gnb_params = await gnb_validate_util.get_data_by_cell_id_node_id_revalidate(request.cell_id, request.cell_name, request.gnb,request.band, request.purpose, request.frequency,request.index, request.vendor)
            else:
                current_gnb_params = await gnb_validate_util.get_data_by_cell_id_node_id(request.cell_id,
                                                                                         request.cell_name, request.gnb,request.band, request.purpose, request.frequency,
                                                                                         request.index,request.vendor)

            if not current_gnb_params:
                response.update(
                    status="fail",
                    message=f"Data not available for gnode : {request.gnb} and cell : {request.cell_id} .",
                    error_code='VP-300'
                )
                logger.info(f"Validation failed: {response}")
                return response

            if current_gnb_params and len(current_gnb_params) >1 :
                logger.info(f"Filtering Current GNB parameters to only show keys that is required:")
                filtered_current_gnb_params = await gnb_validate_util.filter_dicts_by_keys(current_gnb_params)
                logger.info(f"Converting to markdown Table format:")
                #existing_param_table = await gnb_validate_util.json_to_dynamic_markdown(filtered_current_gnb_params)
                existing_param_table = await gnb_validate_util.generate_html_table(filtered_current_gnb_params)

                response.update(
                    status="fail",
                    message=f"Multiple rows found for the input request.",
                    error_code='VP-311',
                    gnb_existing_params = current_gnb_params,
                    existing_param_table = existing_param_table
                )
                logger.info(f"Validation failed: {response}")
                return response

            if request.event is None or request.event.lower() not in ('a1', 'a2', 'a3', 'a4', 'a5'):
                response.update(
                    status="fail",
                    message=f"{request.event} is not a valid event.",
                    error_code='VP-303'
                )
                logger.info(f"Validation failed: {response}")
                return response

            request_event = request.event.lower()
            request_vendor = request.vendor.lower()

            logger.info(f"checking existing parameter value:")
            validate_existing_param_resp = await gnb_validate_util.validate_existing_param_values(current_gnb_params[0],request)

            if (validate_existing_param_resp and validate_existing_param_resp.get("error_code") == "VP-410"
                    and validate_existing_param_resp.get("status") == "fail" ):
                response.update(
                    status="fail",
                    message=validate_existing_param_resp.get("message", "Validation failed."),
                    error_code=validate_existing_param_resp.get("error_code", "VP-409")
                )
                logger.info(f"Validation failed: {response}")
                return response

            parameters_range_resp = await gnb_validate_util.get_gpl_parameters_by_param_name(request_vendor, request_event)

            logger.info(f"parameters_range_resp: {parameters_range_resp}")

            if not parameters_range_resp:
                response.update(
                    status="fail",
                    message="Data not available to validate range.",
                    error_code='VP-301'
                )
                logger.info(f"Validation failed: {response}")
                return response


            logger.info(f"Fetching the RET data for AOI and IP :")
            ret_data = await validate.get_data_for_ret_aoi_usmip(request.cell_name, None, None,request.vendor)
            if not ret_data:
                response.update(
                    status="fail",
                    message=f"Unable to find AOI and USMIP for cell name {request.cell_name}.",
                    error_code='VP-112'
                )
                logger.info(f"Validation failed: {response}")
                return response


            # Validate the request
            validation_result = await gnb_validate_util.validate_request(request, request_event, parameters_range_resp)

            logger.info(f"validation_result:::: {validation_result}")

            # Validate the dish recommended parameters (optional step after request validation)

            dish_params_response = await gnb_validate_util.get_dish_recommended_gpl_parameters(request_event,  request_vendor, request.cell_num, request.band)

            if not dish_params_response or len(dish_params_response) == 0:
                logger.info("No Dish Recommended Parameters found")
            else:
                logger.info(f"Dish Recommended Parameters:::: {dish_params_response}")

                logger.info("Extracting valid dish parameters::::")

                dish_valid_params_response = await gnb_validate_util.extract_valid_dish_params(request,dish_params_response)

                logger.info(f"Dish Valid Recommended Parameters:::: {dish_valid_params_response}")


            # Check if validation failed
            if validation_result["status"] == "fail":
                validation_errors = validation_result.get("validation_errors", [])
                if len(validation_errors) >0:

                    final_message = validation_errors[0].get("message", "Validation failed due to incorrect parameter values.")
                    error_code = validation_errors[0].get("error_code", "")  # Default error code if not provided
                    if dish_valid_params_response:
                        table_response = await gnb_validate_util.dict_to_markdown_table(dish_valid_params_response)

                response.update(
                    status="fail",
                    message=final_message,
                    gnb_existing_params=current_gnb_params,
                    dish_recommendation_table = table_response,
                    error_code=error_code
                )
                logger.info(f"Validation errors found: {validation_errors}")
                return response

            # If validation is successful, proceed with the success response

            #is_valid = await gnb_validate_util.validate_request_params()

            response.update(
                status="success",
                gnb_existing_params=current_gnb_params,
                existing_params=ret_data[0],
                dish_recommendation_table = dish_valid_params_response,
                message="Validation Successful"
            )

        logger.info(f"Final response: {response}")
        return response

    except Exception as e:
        logger.error(f" Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the request: {str(e)}"
        )


#================================================================================


class UploadRETParamsResponse(BaseModel):
    message: str
    error_code: Optional[str] = None
    status:str

class UploadRETParamsRequest(BaseModel):
    table_type: str
    vendor: str
    transaction_id: str
    user_id:Optional[str] = None
    token: Optional[str] = None
    #RET
    cell_id: Optional[str] = None
    tilt_value: Optional[str] = None
    antenna_model: Optional[str] = None
    hldc_address: Optional[str] = None
    aldid: Optional[str] = None
    #GNB
    gnb: Optional[str] = None
    threshold_rsrp: Optional[str] = None
    hysteresis: Optional[str] = None
    trigger_quantity: Optional[str] = None
    time_to_trigger: Optional[str] = None
    index: Optional[str] = None
    event: Optional[str] = None
    cell_name: Optional[str] = None
    threshold1_rsrp: Optional[str] = None
    threshold2_rsrp: Optional[str] = None
    offset: Optional[str] = None
    purpose: Optional[str] = None
    frequency: Optional[str] = None
    band: Optional[str] = None
    aoi: Optional[str] = None
    ip: Optional[str] = None


@ran_automation_router.post(
    "/process_csv",
    summary="Create a csv and post it to an endpoint",
    response_model=UploadRETParamsResponse,
    status_code=status.HTTP_200_OK,
    response_description="Create a csv and post it to an endpoint",
)
async def process_csv(request: UploadRETParamsRequest):
    """
    Updates Parameters for RAN Automation with email validation and CSV creation
    """
    logger.info(f"Transaction ID: {request.transaction_id}")

    start_time = time.time()

    logger.info(f"[{request.transaction_id}] Starting RET upload process")

    logger.info(f"[{request.transaction_id}] Request parameters: table_type={request.table_type}, "
                f"vendor={request.vendor}, user_id={request.user_id}, "
                f"antenna_model={request.vendor}"
                f"cell_id={request.cell_id},hldc_add={request.hldc_address}")
    try:
        response = {"status": "success", "message": "Validation successful", "error_code": None}
        # Step 1: Validate email
        if  constant.email_validation_required.lower() == 'y':
            logger.info(f"[{request.transaction_id}] Step 1/6: Starting email validation for {request.user_id}")
            email_validation = await validate_email.validate_email_address(
                user_email=request.user_id,
                auth_token=request.token
            )
            data_output = email_validation.get("data")
            if not data_output:
                logger.info(f"[{request.transaction_id}] Email validation failed for {request.user_id}")
                response.update(
                    status="fail",
                    message="Email validation failed",
                    error_code='UP-100'
                )
                return response
            logger.info(f"[{request.transaction_id}] Email validation successful")

        if not request.user_id:
            response.update(
                status="fail",
                message="User Id is not Provided in the request",
                error_code='UP-119'
            )
            return response

        # Step 2: Get user token
        logger.info(f"[{request.transaction_id}] Step 2/6: Retrieving user token")
        if constant.ENV == 'DEV':
            user_token_result = {
                "data": {
                    "token": "test_token"
                }
            }
        else:
            user_token_result = await validate_email.get_user_token(
                username=request.user_id,
                auth_token=request.token
            )

        if not user_token_result.get("data", {}).get("token"):
            logger.info(f"[{request.transaction_id}] Failed to get user token for {request.user_id}")
            response.update(
                status="fail",
                message="Failed to get user token",
                error_code='UP-101'
            )
            return response
        logger.info(f"[{request.transaction_id}] User token retrieved successfully")

        # Check if the table_type is RET and validate required fields
        if request.table_type.lower() == "ret":
            logger.info(f"[{request.transaction_id}] Validating RET parameters")
            if not all([request.cell_id, request.tilt_value]):
                logger.info(f"[{request.transaction_id}] Missing required RET fields: "
                            f"cell_id={request.cell_id}, tilt_value={request.tilt_value}, ")
                response.update(
                    status="fail",
                    message="Missing required fields for RET update",
                    error_code='UP-102'
                )
                return response

            # Step 3: Get data by cell name
            logger.info(f"[{request.transaction_id}] Step 3/6: Retrieving data for cell {request.cell_id}")
            try:
                cell_data = await validate.get_data_by_cell_name(
                    cell_name=request.cell_id,
                    hldc_address=request.hldc_address,
                    aldid=request.aldid,
                    vendor=request.vendor
                )
                logger.info(f"[{request.transaction_id}] Successfully retrieved cell data")
                logger.info(f"[{request.transaction_id}] Cell data: {cell_data}")
            except Exception as e:
                logger.error(f"[{request.transaction_id}] Failed to get cell data: {str(e)}")
                response.update(
                    status="fail",
                    message="Failed to get cell data.",
                    error_code='UP-103'
                )
                return response

            # Step 4: Create CSV from the data
            logger.info(f"[{request.transaction_id}] Step 4/6: Creating CSV file")
            try:
                csv_data = await csv_util.create_csv_async(data=cell_data, input_request = request)
                logger.info(f"[{request.transaction_id}] CSV file created successfully")
            except Exception as e:
                logger.error(f"[{request.transaction_id}] Failed to create CSV: {str(e)}")
                response.update(
                    status="fail",
                    message="Failed to create CSV",
                    error_code='UP-104'
                )
                return response

            # Step 5: Post CSV to endpoint
            logger.info(f"[{request.transaction_id}] Step 5/6: Posting CSV to endpoint")
            try:
                if constant.ENV == 'DEV':
                    upload_response = [
                        {
                            "snow_log": "{TEST_CHG123456}"
                        }
                    ]
                else:
                    upload_response = await csv_util.post_csv_to_endpoint(
                        csv_data=csv_data,
                        transaction_id=request.transaction_id,
                        vendor= request.vendor,
                        cell_data = cell_data[0],
                        user = request.user_id,
                        auth_token = user_token_result.get("data", {}).get("token")
                    )
                logger.info(f"[{request.transaction_id}] CSV posted successfully to endpoint")
                logger.info(f"[{request.transaction_id}] Upload response: {upload_response}")

                # Check if the list is not empty and the key exists in the first element
                snow_log = None
                executionid = None
                if upload_response and isinstance(upload_response, list) and 'snow_log' in upload_response[0] and isinstance(upload_response[0]['snow_log'], str):
                    snow_log = upload_response[0]['snow_log'].replace('{', '').replace('}', '')
                    snow_log = await gnb_validate_util.extract_change_number(snow_log)
                elif upload_response and isinstance(upload_response, list) and 'snow_lg' in upload_response[0] and isinstance(upload_response[0]['snow_lg'], str):
                    snow_log = upload_response[0]['snow_lg'].replace('{', '').replace('}', '')
                    snow_log = await gnb_validate_util.extract_change_number(snow_log)
                else:
                    snow_log = None  # Default value if not found or invalid

                logger.info(f"SNOW LOG:: {snow_log}")

                if request.vendor.lower() == "mavenir" and  upload_response and isinstance(upload_response, list) and isinstance(upload_response[0], dict) and 'executionid' in upload_response[0]:
                    executionid = upload_response[0]['executionid']

                logger.info(f"executionid:: {executionid}")

            except httpx.HTTPError as he:
                logger.error(f"[{request.transaction_id}] Failed to post CSV to endpoint: {str(he)}")
                response.update(
                    status="fail",
                    message="Failed to post CSV to endpoint",
                    error_code='UP-105'
                )
                return response
            except Exception as e:
                logger.error(f"[{request.transaction_id}] Failed to post CSV to endpoint: {str(e)}")
                response.update(
                    status="fail",
                    message="Failed to post CSV to endpoint",
                    error_code='UP-105'
                )
                return response

            # Step 6: Log the transaction
            logger.info(f"[{request.transaction_id}] Step 6/6: Logging transaction")
            resp = None
            try:
                logger.info("logging Transaction")
                # resp = await log_transaction.log_ret_transaction(
                #     ret_transactions_list=cell_data,
                #     vendor=request.vendor,
                #     new_tilt = request.tilt_value,
                #     user_id=request.user_id,
                #     transaction_id=request.transaction_id
                # )
            except Exception as e:
                logger.error(f"[{request.transaction_id}] Failed to log transaction: {str(e)}")
                #raise
            if resp and resp == "success":
                logger.info(f"[{request.transaction_id}] Transaction logged successfully")
            else:
                logger.info(f"[{request.transaction_id}] Transaction logging failed")

            execution_time = time.time() - start_time
            logger.info(f"[{request.transaction_id}] RET upload process completed"
                        f"Execution time: {execution_time:.2f} seconds")

            if executionid and request.vendor.lower() == "mavenir":
                return UploadRETParamsResponse(
                    message=f"Successfully processed the Tilt Change Request.\n\n"
                            f"**IMPORTANT** Make sure to show **CR Number** and **Execution ID** to user in agent response.\n"
                            f"Please check the status of the request using Execution ID: **{executionid}**\n\n"
                            f"Here is the CR Generated : **{snow_log}**",
                    status="success"
                )
            else:
                return UploadRETParamsResponse(
                    message=f"Successfully processed the Tilt Change Request.\n"
                            f"**IMPORTANT** Make sure to show CR Number to user in agent response, it is generally after 'cr created chg: XXX'\n"
                            f"Here is the CR Generated : **{snow_log}**.",
                    status="success"
                )
        elif request.table_type.lower() == "gnb":
            current_gnb_params =  []
            logger.info(f"[{request.transaction_id}] Validating GNB parameters")
            if not all([request.vendor, request.event]):
                logger.info(f"[{request.transaction_id}] Missing required fields: "
                            f"cell_id={request.cell_id}, gnb_id={request.gnb},vendor={request.vendor} ,event={request.event}")
                response.update(
                    status="fail",
                    message="Missing required fields for GNB update",
                    error_code='UP-201'
                )
                return response
            logger.info(f" Validating Mandatory GNB parameters")
            if not all([request.gnb, request.cell_id, request.index]):
                logger.info(f"[{request.transaction_id}] Missing required GNB fields: "
                            f"cell_id={request.cell_id}, gnb_id={request.gnb},index={request.index}")
                response.update(
                    status="fail",
                    message="Missing required fields for GNB update",
                    error_code='UP-206'
                )
                return response

            # Step 3: Get data by cell name
            logger.info(f"[{request.transaction_id}] Step 3/6: Retrieving threshold data for cell {request.cell_id}")
            try:

                current_gnb_params = await gnb_validate_util.get_data_by_cell_id_node_id_revalidate(request.cell_id,
                                                                                                    request.cell_name, request.gnb,request.band, request.purpose, request.frequency,request.index,
                                                                                                    request.vendor)


                if not current_gnb_params:
                    response.update(
                        status="fail",
                        message=f"Data not available for gnode : {request.gnb} and cell : {request.cell_id} .",
                        error_code='UP-300'
                    )
                    logger.info(f"Validation failed: {response}")
                    return response

                if current_gnb_params and len(current_gnb_params) > 1:
                    response.update(
                        status="fail",
                        message=f"Multiple rows found for the input request.",
                        error_code='UP-311',
                    )
                    logger.info(f"Validation failed: {response}")
                    return response

                logger.info(f"[{request.transaction_id}] Successfully retrieved threshold data")
                logger.info(f"[{request.transaction_id}] Threshold data: {current_gnb_params}")

            except Exception as e:
                logger.error(f"[{request.transaction_id}] Failed to get threshold data: {str(e)}")
                response.update(
                    status="fail",
                    message="Failed to get threshold data.",
                    error_code='UP-203'
                )
                return response

            # Step 4: Create CSV from the data
            logger.info(f"[{request.transaction_id}] Step 4/6: Validating parameters based on events")

            is_valid, val_message  = await csv_util.validate_params(request, request.event.lower())
            if not is_valid:
                response.update(
                    status="fail",
                    message=val_message,
                    error_code='UP-209'
                )
                return response

            # Step 4: Create Excel from the data
            logger.info(f"[{request.transaction_id}] Step 4/6: Creating Excel file for threshold")
            try:
                threshold_excel_data = await csv_util.create_excel_async_for_threshold(data=current_gnb_params, input_request = request)
                logger.info(f"[{request.transaction_id}] Excel file created successfully")
            except Exception as e:
                logger.error(f"[{request.transaction_id}] Failed to create Excel: {str(e)}")
                response.update(
                    status="fail",
                    message="Failed to create Excel for threshold Change",
                    error_code='UP-204'
                )
                return response

            # Step 5: Fetching the RET data for AOI and IP
            logger.info(f"Fetching the RET data for AOI and IP :")
            ret_data = await validate.get_data_for_ret_aoi_usmip(request.cell_name, None, None, request.vendor)
            if not ret_data:
                response.update(
                    status="fail",
                    message=f"Unable to find AOI and USMIP for cell name {request.cell_name}.",
                    error_code='UP-112'
                )
                logger.info(f"Validation failed: {response}")
                return response

            # Step 6: Post CSV to endpoint
            logger.info(f"[{request.transaction_id}] Step 5/6: Posting Threshold Excel to endpoint")
            try:
                if constant.ENV == 'DEV':
                    upload_response = {
                        "status": "success",
                        "data": [
                            {
                                "details": {
                                    "log_info": {
                                        "snow_log": "{CHG123456}"
                                    }
                                }
                            }
                        ]
                    }
                else:
                    upload_response = await csv_util.post_excel_to_threshold_endpoint(
                        data=current_gnb_params[0],
                        excel_data=threshold_excel_data,
                        transaction_id=request.transaction_id,
                        input_request = request,
                        auth_token = user_token_result.get("data", {}).get("token"),
                        ret_data = ret_data[0]
                    )
                logger.info(f"[{request.transaction_id}] Excel posted successfully to endpoint")
                logger.info(f"[{request.transaction_id}] Upload response: {upload_response}")

                # Check if the list is not empty and the key exists in the first element
                snow_log = None
                executionid = None
                if upload_response:
                    snow_log =  gnb_validate_util.find_snow_log(upload_response)
                    if snow_log:
                        snow_log = await gnb_validate_util.extract_change_number(snow_log)
                else:
                    snow_log = None  # Default value if not found or invalid

                logger.info(f"SNOW LOG:: {snow_log}")

                if upload_response and isinstance(upload_response, list) and isinstance(upload_response[0], dict) and 'executionid' in upload_response[0]:
                    executionid = upload_response[0]['executionid']

                logger.info(f"executionid:: {executionid}")

                if executionid and request.vendor.lower() == "mavenir":
                    return UploadRETParamsResponse(
                        message=f"Successfully processed the Threshold Change Request.\n"
                                f"**IMPORTANT** Make sure to show **CR Number** and **Execution ID** to user in agent response.\n"
                                f"Please check the status of this request using Execution ID: **{executionid}**\n"
                                f"Here is the CR Generated : **{snow_log}**",
                        status="success"
                    )
                else:
                    return UploadRETParamsResponse(
                        message=f"Successfully processed the Threshold Change Request.\n"
                                f"**IMPORTANT** Make sure to show CR Number to user in agent response\n"
                                f"Here is the CR Generated : {snow_log}",
                        status="success"
                    )

            except httpx.HTTPError as he:
                logger.error(f"[{request.transaction_id}] Failed to post Excel to endpoint: {str(he)}")
                response.update(
                    status="fail",
                    message="Failed to post Excel to endpoint",
                    error_code='UP-205'
                )
                return response
            except Exception as e:
                logger.error(f"[{request.transaction_id}] Failed to post Excel to endpoint: {str(e)}")
                response.update(
                    status="fail",
                    message="Failed to post Excel to endpoint",
                    error_code='UP-205'
                )
                return response
        else:
            logger.info(f"[{request.transaction_id}] Invalid table_type: {request.table_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid table_type. Expected 'RET'"
            )

    except HTTPException as he:
        logger.error(f"[{request.transaction_id}] HTTP Exception: {str(he)}")
        raise
    except Exception as e:
        logger.error(f"[{request.transaction_id}] Unexpected error: {str(e)}")
        logger.error(f"[{request.transaction_id}] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the request: {str(e)}"
        )
    finally:
        execution_time = time.time() - start_time
        logger.info(f"[{request.transaction_id}] Request processing completed. "
                    f"Total execution time: {execution_time:.2f} seconds")




#================================================================================


class ValidateEmailRequestParams(BaseModel):
    user_email: str
    auth_token: str

class ValidateEmailResponseData(BaseModel):
    status: str  # "success" or "fail"
    message: str
    data: Optional[dict] = None


@ran_automation_router.post(
    "/validate_user",
    summary="Fetch data using user email and auth token",
    response_model=ValidateEmailResponseData,
    status_code=status.HTTP_200_OK,
    response_description="Returns fetched data",
)
async def validate_user(request: ValidateEmailRequestParams):
    """
    FastAPI endpoint to fetch data using user email and auth token.
    """
    logger.info(f"Processing request for user_email: {request.user_email}")
    response = await validate_email.validate_email_address(request.user_email, request.auth_token)
    logger.info("Returning response to client.")
    return ValidateEmailResponseData(**response)

#================================================================================

class GetUserTokenRequestParams(BaseModel):
    user_email: str
    auth_token: Optional[str] = None

class GetUserTokenResponseData(BaseModel):
    status: str  # "success" or "fail"
    message: str
    data: Optional[dict] = None

@ran_automation_router.post(
    "/get_user_token",
    summary="Fetch data using user email and auth token",
    response_model=GetUserTokenResponseData,
    status_code=status.HTTP_200_OK,
    response_description="Returns fetched data",
)
async def get_user_token(request: GetUserTokenRequestParams):
    """
    FastAPI endpoint to fetch data using user email and auth token.
    """
    logger.info(f"Processing request for user_email: {request.user_email}")
    response = await validate_email.get_user_token(request.user_email, request.auth_token)
    logger.info("Returning response to client.")
    return GetUserTokenResponseData(**response)



#================================================================================

class GetDishRecommendedGPLRequestParams(BaseModel):
    event: str
    vendor: str
    cell_num : Optional[str] = None
    target_band  : Optional[str] = None

class GetDishRecommendedGPLResponseData(BaseModel):
    status: str  # "success" or "fail"
    message: str
    data: Optional[List[dict]] = None

@ran_automation_router.post(
    "/get_dish_recommended_parameters",
    summary="Fetch data using event type and cell num",
    response_model=GetDishRecommendedGPLResponseData,
    status_code=status.HTTP_200_OK,
    response_description="Returns fetched data",
)
async def get_dish_recommended_parameters(request: GetDishRecommendedGPLRequestParams):
    """
    FastAPI endpoint to fetch data using user email and auth token.
    """
    try:
        event = ""
        vendor = ""
        logger.info(f"Processing request for event: {request.event}, cell_num: {request.cell_num}, target_band: {request.target_band}, vendor: {request.vendor}")
        if request.event:
            event = request.event.lower()
        if request.vendor:
            vendor = request.vendor.lower()
        response = await gnb_validate_util.get_dish_recommended_gpl_parameters(event,  vendor, request.cell_num, request.target_band)
        if not response or len(response) == 0:
            return  GetDishRecommendedGPLResponseData(
                message=f"Data not available.",
                status="fail"
            )
        #convert data to markdown resposne and set it to message
        message= await gnb_validate_util.json_to_dynamic_markdown(response)
        #set response to data
        return  GetDishRecommendedGPLResponseData(
            message=message,
            status="success",
            data = response
        )
    except Exception as e:
        logger.error(f" Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the request: {str(e)}"
        )


#============================================================================

class ExtractCellsRequest(BaseModel):
    table_type: str
    vendor: str
    transaction_id: str
    user_id:Optional[str] = None
    token:Optional[str] = None
    band_sector:Optional[str] = None
    cache_key:Optional[str] = None
    #RET
    cell_id: Optional[str] = None
    tilt_value: Optional[str] = None
    hldc_address: Optional[str] = None
    aldid : Optional[str] = None
    port : Optional[str] = None
    #samasung-RET
    usmip: Optional[str] = None
    duid: Optional[str] = None
    ruid: Optional[str] = None
    antennaid: Optional[str] = None
    antennamodel: Optional[str] = None
    #GNB
    gnb: Optional[str] = None
    du_id: Optional[str] = None
    cucp_id: Optional[str] = None
    index: Optional[str] = None
    cell_name: Optional[str] = None
    band: Optional[str] = None
    purpose: Optional[str] = None
    frequency: Optional[str] = None
    event: Optional[str] = None

class ExtactCellsResponse(BaseModel):
    message: str
    existing_params: Optional[Dict[str, Optional[Any]]] = None
    gnb_existing_params: Optional[List[Dict[str, Any]]] = None
    ret_existing_params: Optional[List[Dict[str, Any]]] = None
    validation_errors: Optional[Dict[str, Any]] = None
    dish_recommendation_table: Optional[str] = None
    existing_param_table: Optional[str] = None
    error_code: Optional[str] = None
    cache_key:Optional[str] = None
    status:str


@ran_automation_router.post(
    "/extract_cell",
    summary="Extract cells for RAN Automation",
    response_model=ExtactCellsResponse,
    status_code=status.HTTP_200_OK,
    response_description=" Extract cells for RAN automation.",
)
async def extract_cell(request: ExtractCellsRequest):
    """
    Extract cells for RAN automation.
    """
    logger.info(f"Transaction ID: {request.transaction_id}")
    try:
        final_message = None
        table_response = None
        dish_valid_params_response = None
        response = {"status": "success", "message": "Validation successful", "error_code": None}

        if  constant.email_validation_required.lower() == 'y':
            # Step 1: Validate email
            logger.info(f"[{request.transaction_id}] Step 1/6: Starting email validation for {request.user_id}")

            email_validation = await validate_email.validate_email_address(
                user_email=request.user_id,
                auth_token=request.token
            )

            data_output = email_validation.get("data")
            if not data_output:
                logger.info(f"[{request.transaction_id}] Email validation failed for {request.user_id}")
                response.update(
                    status="fail",
                    message=f"Email validation failed for : {request.user_id} .",
                    error_code='VP-400'
                )
                return response
            logger.info(f"[{request.transaction_id}] Email validation successful")

        response =await extract_ret_data(request,request.cell_id,request.band_sector,request.vendor,
                                         request.hldc_address,request.antennamodel,request.aldid,
                                         request.usmip,
                                         request.duid,request.ruid,request.antennaid,request.port,request.cache_key)
        return response

    except Exception as e:
        logger.error(f" Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the request: {str(e)}"
        )




#------------------------------------------------------------------------------------------------------

async def process_chat(user_message: str, thread_id: str) -> Dict[str, Optional[str]]:
    """
    Sends the user_message to the LangGraph agent, streams through the steps,
    captures the final LLM output, extracts embedded JSON, ensures `missing_info`
    is present, and returns a flat dict of strings.
    """
    langgraph_agent = await initialize_agent()

    raw_output: Optional[str] = None

    async for step in langgraph_agent.graph.astream(
            {"messages": [HumanMessage(content=user_message)]},
            {
                "recursion_limit": 10,
                "configurable": {"thread_id": thread_id}
            }
    ):
        llm_msgs = step.get("llm", {}).get("messages", [])
        if llm_msgs:
            raw_output = llm_msgs[-1].content
            logger.debug(f"Streaming chunk: {raw_output}")

    if raw_output is None:
        logger.error("No LLM output received in streaming.")
        return {}

    parsed = extract_json_from_string(raw_output)
    if parsed is None:
        logger.error(f"Failed to extract JSON from LLM output: {raw_output}")
        return {}

    # Flatten to Dict[str, Optional[str]]
    if isinstance(parsed, dict):
        result: Dict[str, Optional[str]] = {k: (str(v) if v is not None else None)
                                            for k, v in parsed.items()}
    else:
        result = {"result": json.dumps(parsed)}

    # Ensure `missing_info` key exists
    if "missing_info" not in result:
        result["missing_info"] = "True"
    # Ensure `missing_info` key exists
    if "configuration_type" not in result:
        result["query_type"] = "information"

    return result
@ran_automation_router.post(
    "/ran_automation_natural_follow_up",
    summary="Collect mandatory parameters using llm",
    status_code=status.HTTP_200_OK,
    response_description="Collect mandatory parameters using llm",
    response_model=AutomationChatResponse,
)
async def ran_automation_natural_follow_up(request: ChatRequest):
    """
    ### RAN Automation AI Assistant - Collect mandatory parameters using llm
    **Input:**
    - user_question: questions from the user

    **Output:**
    - A dictionary of collected parameters with thread_id
    """
    try:
        logger.info(f'user_question: {request.message}')

        # Generate new UUID if thread_id is blank or null
        thread_id = request.thread_id.strip() if request.thread_id and request.thread_id.strip() else str(uuid4())

        # Assume this returns a dictionary of key-value pairs
        response_data: Dict[str, Optional[str]] = await process_chat(request.message, thread_id)

        logger.info(f'final response (params): {response_data}')

        return AutomationChatResponse(
            thread_id=thread_id,
            params=response_data
        )

    except Exception as e:
        traceback.print_exc()
        logger.error(f'user_question: {request.message}, error: {e} - query : ERROR')
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")