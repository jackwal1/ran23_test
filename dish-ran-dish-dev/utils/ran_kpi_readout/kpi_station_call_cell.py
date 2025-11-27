import json
import requests
from utils import constants as CONST
# from utils.constants import KPI_THRESHOLDS, KPI_READOUT_LIST, KPI_READOUT_DURATION, STATION_ACCESS_TOKEN, STATION_BASE_URL
from utils.log_init import logger
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from collections import defaultdict
from statistics import mean
import aiohttp
import asyncio
from typing import List, Dict


# STATION_BASE_URL = 'https://api.station2.nonpci-wireless-gba-p.aws.dishcloud.io/np/network/pm/kpi/'
# STATION_ACCESS_TOKEN = '76782dc5-38f5-4622-95f5-57cad23e1e83'
# KPI_READOUT_DURATION = "14"
# KPI_READOUT_LIST = [
#     "nca_kpi_in_network_vonr_access",
#     "nca_kpi_in_network_vonr_retain",
#     "vonr_drb_attempts_c",
#     "data_access_c",
#     "data_retain_c",
#     "hosr_c",
#     "ran_availability_1hr_c",
#     "prb_util_dl_avg_c",
#     "rrc_conns_sum_c",
#     "mac_vol_dl_c",
#     "mac_vol_mid_band_ratio_c",
#     "dl_ue_thrpt_c",
#     "ul_ue_thrpt_c",
#     "ookla_st_dish_throughput_dl_avg",
#     "ookla_st_dish_throughput_ul_avg",
#     "ookla_st_dish_latency_avg"
# ]

# SELECTED_KPIS = ["vonr_drb_attempts_c", "rrc_conns_sum_c", "mac_vol_dl_c", "ookla_st_dish_latency_avg"]

# KPI_THRESHOLDS = {
#             "nca_kpi_in_network_vonr_retain": lambda v: v < 99,
#             "nca_kpi_in_network_vonr_access": lambda v: v < 99.5,
#             # "vonr_drb_attempts_c": 170000, # (Yesterday_Value / Avg_Last14Days) < 0.20
#             "data_access_c": lambda v: v < 99,
#             "data_retain_c": lambda v: v < 99,
#             "hosr_c": lambda v: v < 97,
#             "ran_availability_1hr_c": lambda v: v < 99.5,
#             "prb_util_dl_avg_c": lambda v: v > 70,
#             # "rrc_conns_sum_c": 400000,  # (Yesterday_Value / Avg_Last14Days) < 0.20
#             # "mac_vol_dl_c": 17000,  #  (Yesterday_Value / Avg_Last14Days) < 0.10
#             "mac_vol_mid_band_ratio_c": lambda v: v < 60,
#             "dl_ue_thrpt_c": lambda v: v < 30,
#             "ul_ue_thrpt_c": lambda v: v < 1,
#             "ookla_st_dish_throughput_dl_avg": lambda v: v < 30,
#             "ookla_st_dish_throughput_ul_avg": lambda v: v < 3,
#             # "ookla_st_dish_latency_avg": 25, # (Yesterday_Value / Avg_Last14Days) < 0.20
# }

# KPI_THRESHOLDS = {
#             "nca_kpi_in_network_vonr_retain": lambda v: v < 98,
#             "nca_kpi_in_network_vonr_access": lambda v: v < 98,
#             # "vonr_drb_attempts_c": 170000, # (Yesterday_Value / Avg_Last14Days) < 0.20
#             "data_access_c": lambda v: v < 95,
#             "data_retain_c": lambda v: v < 98,
#             "hosr_c": lambda v: v < 95,
#             "ran_availability_1hr_c": lambda v: v < 99,
#             "prb_util_dl_avg_c": lambda v: v > 70,
#             # "rrc_conns_sum_c": 400000,  # (Yesterday_Value / Avg_Last14Days) < 0.20
#             # "mac_vol_dl_c": 17000,  #  (Yesterday_Value / Avg_Last14Days) < 0.10
#             "mac_vol_mid_band_ratio_c": lambda v: v < 60,
#             "dl_ue_thrpt_c": lambda v: v < 20,
#             "ul_ue_thrpt_c": lambda v: v < 1,
#             "ookla_st_dish_throughput_dl_avg": lambda v: v < 30,
#             "ookla_st_dish_throughput_ul_avg": lambda v: v < 3,
#             # "ookla_st_dish_latency_avg": 25, # (Yesterday_Value / Avg_Last14Days) < 0.20
# }

# # KPI_SORT_ORDER: asc = False, desc = True
# KPI_SORT_ORDER = {
#             "nca_kpi_in_network_vonr_retain": False,
#             "nca_kpi_in_network_vonr_access": False,
#             # "vonr_drb_attempts_c":  True, # (Yesterday_Value / Avg_Last14Days) < 0.20
#             "data_access_c": False,
#             "data_retain_c": False,
#             "hosr_c": False,
#             "ran_availability_1hr_c": False,
#             "prb_util_dl_avg_c":  True,
#             # "rrc_conns_sum_c":   True,  # (Yesterday_Value / Avg_Last14Days) < 0.20
#             # "mac_vol_dl_c":   True,  (Yesterday_Value / Avg_Last14Days) < 0.10
#             "mac_vol_mid_band_ratio_c":  False,
#             "dl_ue_thrpt_c": False,
#             "ul_ue_thrpt_c": False,
#             "ookla_st_dish_throughput_dl_avg": False,
#             "ookla_st_dish_throughput_ul_avg": False,
#             # "ookla_st_dish_latency_avg":  True, (Yesterday_Value / Avg_Last14Days) < 0.20
# }

# KPI_THRESHOLDS = {
#     "ookla_st_dish_latency_avg": lambda v: v > 27,
#     "nca_kpi_in_network_vonr_retain": lambda v: v > 99.5,
# }


# Remove null and 0 values data
def remove_null(input_data):

    clean_data = [
        {k: v for k, v in record.items() if v is not None}
        for record in input_data
    ]

    # Keep only dicts that have 'kpivalue' and it's not None
    # filtered_data = [
    #     item for item in input_data 
    #     if isinstance(item, dict) and "kpivalue" in item and item["kpivalue"] is not None
    # ]    

    return clean_data

# Function to call the Station API, to fetch KPI data at AOI level
# def fetch_aoi_data(aoi: str) -> List[Dict]:
#
#     # Calculate dates
#     # Past midnight UTC time as end_date
#     end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
#
#     # Start date = 14 days before end_date
#     start_date = end_date - timedelta(days=int(CONST.KPI_READOUT_DURATION))
#
#     # Format both dates to required format
#     date_format = "%Y-%m-%dT%H:%M:%S.%f"
#     end_date_str = end_date.strftime(date_format)[:-3] + "Z"
#     start_date_str = start_date.strftime(date_format)[:-3] + "Z"
#
#     # Using join() method to concatenate all elements of list into a single string
#     kpi_list = ",".join(CONST.KPI_READOUT_LIST)
#     query_string = f"query?k={kpi_list}&o=aoi&fot=aoi&fol={aoi}&g=1dy&st={start_date_str}&et={end_date_str}&ta=false"
#
#     full_url = f"{CONST.STATION_BASE_URL}{query_string}"
#     logger.info(f"Calling API URL: {full_url}")
#
#     headers = {
#         "Authorization": f"Bearer {CONST.STATION_ACCESS_TOKEN}"
#     }
#
#     # Perform the GET request
#     response = requests.get(full_url, headers=headers)
#     # Pretty print JSON response
#     try:
#         data_response = response.json()
#         aoi_data_list = data_response.get("data", [])
#
#         # remove null & 0 value attributes
#         aoi_data_list = remove_null(aoi_data_list)
#         logger.info("AOI data fetched")
#         logger.debug(json.dumps(aoi_data_list, indent=4))
#         return aoi_data_list
#         # Remove 'kpi_legend' if it exists
#         # data.get("metadata", {}).pop("kpi_legend", None)
#         # logger.info(json.dumps(data, indent=4))
#     except ValueError:
#         logger.error("Response is not JSON:")
#         logger.error(response.text)
#         return []


async def fetch_aoi_data(aoi: str) -> List[Dict]:
    # Calculate dates
    end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=int(CONST.KPI_READOUT_DURATION))

    # Format dates to required format
    date_format = "%Y-%m-%dT%H:%M:%S.%f"
    end_date_str = end_date.strftime(date_format)[:-3] + "Z"
    start_date_str = start_date.strftime(date_format)[:-3] + "Z"

    # Create query parameters
    kpi_list = ",".join(CONST.KPI_READOUT_LIST)
    query_string = (
        f"query?k={kpi_list}&o=aoi&fot=aoi&fol={aoi}"
        f"&g=1dy&st={start_date_str}&et={end_date_str}&ta=false"
    )
    full_url = f"{CONST.STATION_BASE_URL}{query_string}"

    logger.info(f"Calling API URL: {full_url}")
    headers = {
        "Authorization": f"Bearer {CONST.STATION_ACCESS_TOKEN}"
    }

    try:
        # Create async HTTP session
        async with aiohttp.ClientSession() as session:
            # Perform the async GET request
            async with session.get(full_url, headers=headers) as response:
                # Check for HTTP errors
                response.raise_for_status()

                # Parse JSON response
                data_response = await response.json()
                aoi_data_list = data_response.get("data", [])

                # Process data
                aoi_data_list = remove_null(aoi_data_list)
                logger.info("AOI data fetched")
                logger.debug(json.dumps(aoi_data_list, indent=4))
                return aoi_data_list

    except aiohttp.ClientError as e:
        logger.error(f"HTTP request failed: {str(e)}")
        return []
    except ValueError:
        logger.error("Response is not valid JSON:")
        if 'response' in locals():
            logger.error(await response.text())
        else:
            logger.error("No response available")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return []

# Function to call the Station API, to fetch KPI data at AOI level
# def fetch_cell_data(query_str: str) -> List[Dict]:
#
#     full_url = f"{CONST.STATION_BASE_URL}{query_str}"
#     logger.info(f"Calling API URL: {full_url}")
#
#     headers = {
#         "Authorization": f"Bearer {CONST.STATION_ACCESS_TOKEN}"
#     }
#
#     # Perform the GET request
#     response = requests.get(full_url, headers=headers)
#     # Pretty print JSON response
#     try:
#         data_response = response.json()
#         # cell_data_list = data_response.get("data", [])
#
#         cell_data_list = sort_data_by_kpi(data_response)
#
#         # logger.info(f"Count of offending_cells_data records -->{len(cell_data_list)}")
#         # logger.info(json.dumps(cell_data_list, indent=4))
#         return cell_data_list
#
#     except ValueError:
#         logger.error("Response is not JSON:")
#         logger.error(response.text)
#         return []


async def fetch_cell_data(query_str: str) -> List[Dict]:
    full_url = f"{CONST.STATION_BASE_URL}{query_str}"
    logger.info(f"Calling API URL: {full_url}")
    headers = {
        "Authorization": f"Bearer {CONST.STATION_ACCESS_TOKEN}"
    }

    try:
        # Create async HTTP session
        async with aiohttp.ClientSession() as session:
            # Perform the async GET request
            async with session.get(full_url, headers=headers) as response:
                # Check for HTTP errors
                response.raise_for_status()

                # Parse JSON response
                data_response = await response.json()
                cell_data_list = sort_data_by_kpi(data_response)
                return cell_data_list

    except aiohttp.ClientError as e:
        logger.error(f"HTTP request failed: {str(e)}")
        return []
    except ValueError:
        logger.error("Response is not valid JSON:")
        logger.error(await response.text() if 'response' in locals() else "No response available")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return []

# Function to build query strings for Cell level data fetch, based on AOI offending records
def build_query_strings(input_data):
    output_data = []
    date_format = "%Y-%m-%dT%H:%M:%S.%f"

    for record in input_data:
        fol = record["object"]
        st_raw = datetime.strptime(record["__time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        et_raw = st_raw + timedelta(days=1)

        # format datetime
        st = st_raw.strftime(date_format)[:-3] + "Z"
        et = et_raw.strftime(date_format)[:-3] + "Z"

        # collect KPI keys (exclude object and __time)
        kpi_list = [key for key in record.keys() if key not in ("object", "__time")]
        # kpi_str = ",".join(kpis)
        # Set sort (s) depending on KPI name
        for item in kpi_list:
            query = f"query?k={item}&o=cell&fot=aoi&fol={fol}&g=1dy&st={st}&et={et}"
            output_data.append(query)

    return output_data

# identify threshold violations  -- AOI
def identify_threshold_violations_aoi(data: List[Dict]) -> List[Dict]:

    thresholds = CONST.KPI_THRESHOLDS
    filtered = []
    for record in data:
        violations = {
            k: v for k, v in record.items()
            if k in thresholds and thresholds[k](v)
        }
        if violations:  # keep only if there is at least one violation
            filtered.append({
                "object": record["object"],
                "__time": record["__time"],
                **violations
            })
    return filtered

# identify threshold violations - CELL
def identify_threshold_violations_cell(input_data: List[Dict]) -> List[Dict]:

    thresholds = CONST.KPI_THRESHOLDS
    filtered_data = [
        item for item in input_data
        if item["kpiname"] in thresholds and thresholds[item["kpiname"]](item["kpivalue"])
    ]
    return filtered_data

# find KPI ratios
def calculate_kpi_ratios(input_data):
    # Step 1: Convert __time to datetime
    for item in input_data:
        item["__time"] = datetime.strptime(item["__time"], "%Y-%m-%d %H:%M:%S")

    # Step 2: Sort by date and get latest record
    sorted_data = sorted(input_data, key=lambda x: x["__time"])
    latest_record = sorted_data[-1]

    # Step 3: Compute averages only for selected KPIs
    averages = {kpi: mean(item[kpi] for item in sorted_data) for kpi in CONST.SELECTED_KPIS}

    # Step 4: Compute ratios (latest / avg)
    ratios = {kpi: latest_record[kpi] / averages[kpi] for kpi in CONST.SELECTED_KPIS}

    return ratios

# rearrange offending cells data
def rearrange_data(input_data):
    """
    Rearranges input data into grouped format:
    - Unique cell blocks
    - KPIs grouped with list of {date, value}
    """
    cell_dict = defaultdict(lambda: defaultdict(list))

    for record in input_data:
        cell = record["cell"]
        date = record["date"]
        for kpi, value in record.items():
            if kpi not in ("cell", "date"):  # skip cell and date
                cell_dict[cell][kpi].append({
                    "date": date,
                    "value": value
                })

    # Convert to required output format
    output_data = [
        {
            "cell": cell,
            "kpis": dict(kpis)  # convert defaultdict back to dict
        }
        for cell, kpis in cell_dict.items()
    ]

    return output_data

# sort and pick top 10
def sort_data_by_kpi(input_data):
    """
    Sorts a list of dictionaries by the 'kpivalue'.

    Args:
        data: The list of dictionaries to sort.
        order: The sort order, 'asc' for ascending or 'desc' for descending.

    Returns:
        A new list sorted by 'kpivalue'.
    """
    # read KPI name
    kpi_key = next(iter(input_data["metadata"]["kpi_alias"]))
    logger.info(f"kpi_key -->{kpi_key}")

    # asc or desc, based on KPI name
    is_descending = CONST.KPI_SORT_ORDER.get(kpi_key, False)

    kpi_data = input_data.get("data", [])
    logger.info(f"kpi_key -->{kpi_key}, is_descending --> {is_descending}, count of cell records -->{len(kpi_data)}")

    # # remove null value attributes
    # kpi_data = remove_null(kpi_data)

    # Filter out items with None/null kpivalue
    # kpi_data = [item for item in kpi_data if item.get("kpivalue") is not None]    

    # # Filter out records without 'kpivalue'
    # kpi_data = [item for item in kpi_data if "kpivalue" in item]  
    # logger.info(f"Count of cell records after removing null/0 kpivalue -->{len(kpi_data)}")

    # Keep only dicts that have 'kpivalue' and it's not None
    kpi_data = [
        item for item in kpi_data 
        if isinstance(item, dict) and "kpivalue" in item and item["kpivalue"] is not None
    ]
    # logger.info(f"Count of cell records after removing blocks where kpivalue is missing -->{len(kpi_data)}")

    # with open(f'C:\\sohan\\projects\\DISH-genAI\\ran\\RAN-3-PM\\kpi_readout\\cell_records_before_filter.json', "w") as f:
    #     json.dump(filtered_data, f, indent=4, ensure_ascii=False)     

    # Sort and take top 10
    kpi_data = sorted(
        kpi_data,
        key=lambda item: item["kpivalue"],
        reverse=is_descending
    )[:10]    

    final_output = []
    for item in kpi_data:
        # keep only the date part (YYYY-MM-DD)
        date_str = item["__time"].split(" ")[0]
        final_output.append({
            "cell": item["object"],
            "date": date_str,
            "kpivalue": item["kpivalue"],
            "kpiname": kpi_key
        })    

    return final_output


def transform_data(data):
    cell_map = defaultdict(lambda: {"kpis": defaultdict(list), "dates": set(), "kpi_count": 0})

    for item in data:
        cell = item["cell"]
        kpi = item["kpiname"]
        date = item["date"]
        value = item["kpivalue"]

        # Add KPI data
        cell_map[cell]["kpis"][kpi].append({"date": date, "kpivalue": value})
        # Track unique dates
        cell_map[cell]["dates"].add(date)
        # Count total KPI occurrences
        cell_map[cell]["kpi_count"] += 1

    # Convert to required output format
    output = []
    for cell, info in cell_map.items():
        output.append({
            "cell": cell,
            "kpis": dict(info["kpis"]),
            "days": str(len(info["dates"])),
            "kpi_occurrence": str(info["kpi_count"])
        })

    # Sort by "days" (as integer), descending
    output.sort(key=lambda x: int(x["kpi_occurrence"]), reverse=True)
    logger.info(f"Count of records after sorting by days --> {len(output)}")

    return output[:10]

# transform data
# def transform_data(data):
#     cell_map = defaultdict(lambda: {"kpis": defaultdict(list), "dates": set()})

#     for item in data:
#         cell = item["cell"]
#         kpi = item["kpiname"]
#         date = item["date"]
#         value = item["kpivalue"]

#         # Add kpi data
#         cell_map[cell]["kpis"][kpi].append({"date": date, "kpivalue": value})
#         # Track unique dates
#         cell_map[cell]["dates"].add(date)

#     # Convert to required output format
#     output = []
#     for cell, info in cell_map.items():
#         output.append({
#             "cell": cell,
#             "kpis": dict(info["kpis"]),
#             "days": str(len(info["dates"]))
#         })

#     # Sort by "days" (as integer), descending
#     output.sort(key=lambda x: int(x["days"]), reverse=True)
#     logger.info(f"Count of records after sorting by days --> {len(output)}")

#     # return top 30 worst offenders
#     return output