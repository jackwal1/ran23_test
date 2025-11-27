

# KPI readout
import json
# import requests
# from utils import constants as CONST
# from utils.constants import KPI_THRESHOLDS, KPI_READOUT_LIST, KPI_READOUT_DURATION, STATION_ACCESS_TOKEN, STATION_BASE_URL
from utils.log_init import logger

import time
import traceback
import threading
from .kpi_station_call import fetch_aoi_data, fetch_cell_data, identify_threshold_violations_aoi, build_query_strings, transform_data, identify_threshold_violations_cell
from .kpi_anomaly_detection import detect_anomalies
from llms.llms import analyze_kpi_readout
import asyncio

DIR_PATH = "C:\\sohan\\projects\\DISH-genAI\\ran\\RAN-3-PM\\kpi_readout"

# async def kpi_readout(aoi: str, engineer: str):
#     """
#     The function processes events in this sequence:
#     1. Streams model content in real-time
#     2. Collects sources from ToolMessage events during streaming
#     3. Appends formatted source links after content streaming ends
#
#     Args:
#         aoi (str): The area of interest to process
#
#     Yields:
#         str: Content chunks including model output and source information
#     """
#
#
#         # sequential flow
#         # 1. Fetch AOI KPI data for 14/30 days
#         #     1.1 Process / clean KPI data
#
#         # Tasks in parallel:
#         #     2.1 Identify overall trend (spike/dip) and sigma deviation (one value for each KPI)
#         #     2.2 Identify threshold violations in KPI data (for AOI)
#         #         2.2.1 Fetch CELL KPI data for 14/30 days, only for days where AOI level is violated.
#         #         2.2.2 Identify threshold violations in KPI data (for Cell), prepare offenders list
#
#         # 3. Generate insights from anomalies data and stream
#
#     try:
#         # Start timer
#         start_time = time.time()
#
#         # Step-1: Fetch KPI data from station, for AOI
#         aoi_data = await fetch_aoi_data(aoi)
#         logger.info(f'Count of aoi_data --> {len(aoi_data)}')
#         if not isinstance(aoi_data, list) or (len(aoi_data) == 0):
#             raise ValueError("Either Invalid response or no data received from Station")
#
#         # Step-2: Detect anomalies
#         logger.info(f'Starting anomaly detection...')
#         anomaly_data = detect_anomalies(aoi_data)
#         logger.info(f'Anomaly detection completed.')
#
#         # Step-3: Calculate thresholds for some KPIs
#         # calculate_kpi_ratios(aoi_data, selected_kpis)
#
#
#         # Step-4: identify threshold violations at AOI level
#         aoi_offenders = identify_threshold_violations_aoi(aoi_data)
#         logger.info(f'Count of aoi_offenders --> {len(aoi_offenders)}')
#         # logger.debug(f'aoi_offenders --> {json.dumps(aoi_offenders, indent=4)}')
#         # with open(f'{DIR_PATH}\\{aoi}_aoi_offenders.json', "w") as f:
#         #     json.dump(aoi_offenders, f, indent=4, ensure_ascii=False)
#
#         # Step-5: Fetch KPI data from station, at CELL level, for each AOI offending KPI
#         cell_query_list = build_query_strings(aoi_offenders)
#         logger.info(f'Count of cell_query_list --> {len(cell_query_list)}')
#         # logger.debug(f'cell_query_list --> {json.dumps(cell_query_list, indent=4)}')
#
#
#         # find offending cells
#         lock = threading.Lock()
#         offending_cells_data = []
#         # function to compare classifications -- use Threads
#         async def worker(query_str):
#             cell_offenders = await fetch_cell_data(query_str)
#             # logger.debug(json.dumps(cell_kpi_data, indent=4))
#             offending_cells_data.extend(cell_offenders)
#
#             # identify violations
#             # cell_offenders = identify_threshold_violations(cell_kpi_data)
#             # if cell_offenders:
#             #     with lock:
#             #         offending_cells_data.extend(cell_offenders)
#
#         threads = []
#         for record in cell_query_list:
#             t = threading.Thread(target=worker, args=(record,)) # COMMA is important here
#             threads.append(t)
#             t.start()
#
#         # Wait for all threads to finish
#         for t in threads:
#             t.join()
#
#         logger.info(f"Count of records, offending_cells_data -->{len(offending_cells_data)}")
#         logger.debug(f"offending_cells_data --> {json.dumps(offending_cells_data, indent=4)}")
#
#         # Identify violations - CELL level
#         top_offenders = identify_threshold_violations_cell(offending_cells_data)
#         logger.info(f"Count of records, after filtering out violations --> {len(top_offenders)}")
#
#         # save offending_cells_data to a file
#         # with open(f'{DIR_PATH}\\{aoi}_cells_offenders_BEFORE_rearrange.json', "w") as f:
#         #     json.dump(top_offenders, f, indent=4, ensure_ascii=False)
#
#         # # Rearrange data structure, only for CELLs data
#         offending_cells_data_rearranged = transform_data(offending_cells_data)
#         logger.info(f"Count of top offenders --> {len(offending_cells_data_rearranged)}")
#         top_offenders = offending_cells_data_rearranged
#
#         # with open(f'{DIR_PATH}\\{aoi}_for_kpi_readout.json', "w") as f:
#         #     json.dump(kpi_readout_data, f, indent=4, ensure_ascii=False)
#
#         # initialize kpi_readout_data
#         kpi_readout_data = {
#             "aoi": aoi,
#             "engineer": engineer,
#             "data": anomaly_data['data'],
#             "trend_indicator": anomaly_data['trend_indicator'],
#             "top_offenders": top_offenders
#         }
#
#         logger.info(json.dumps(kpi_readout_data, indent=4))
#
#         # End timer
#         end_time = time.time()
#
#         logger.info(f"Execution time: {end_time - start_time:.4f} seconds")
#
#
#         # # Read JSON into a Python object (dict or list)
#         # with open(f'{DIR_PATH}\\{aoi}_aoi_offenders.json', "r") as f:
#         #     kpi_readout_data = json.load(f)
#
#         # status = analyze_kpi_readout(kpi_readout_data)
#         async for content in analyze_kpi_readout(kpi_readout_data):
#             # yield content
#             item = {'type': 'text', 'content': content}
#             yield f"data: {json.dumps(item)}"
#             yield "\n\n"
#
#     except Exception as e:
#         logger.info(f"Error in streaming process: {str(e)}")
#         logger.info(traceback.format_exc())
#         error_message = {'type': 'error', 'content': "I encountered an issue while processing your request. Please try again."}
#         yield f"data: {json.dumps(error_message)}"
#         yield "\n\n"


async def kpi_readout(aoi: str, engineer: str):
    """
    The function processes events in this sequence:
    1. Streams model content in real-time
    2. Collects sources from ToolMessage events during streaming
    3. Appends formatted source links after content streaming ends
    Args:
        aoi (str): The area of interest to process
    Yields:
        str: Content chunks including model output and source information
        :param aoi:
        :param engineer:
    """
    try:
        # Start timer
        start_time = time.time()
        # Step-1: Fetch KPI data from station, for AOI
        aoi_data = await fetch_aoi_data(aoi)
        logger.info(f'Count of aoi_data --> {len(aoi_data)}')
        if not isinstance(aoi_data, list) or (len(aoi_data) == 0):
            raise ValueError("Either Invalid response or no data received from Station")

        # Step-2: Detect anomalies
        logger.info(f'Starting anomaly detection...')
        anomaly_data = detect_anomalies(aoi_data)
        logger.info(f'Anomaly detection completed.')

        # Step-4: identify threshold violations at AOI level
        aoi_offenders = identify_threshold_violations_aoi(aoi_data)
        logger.info(f'Count of aoi_offenders --> {len(aoi_offenders)}')

        # Step-5: Fetch KPI data from station, at CELL level, for each AOI offending KPI
        cell_query_list = build_query_strings(aoi_offenders)
        logger.info(f'Count of cell_query_list --> {len(cell_query_list)}')

        # # find offending cells - using async tasks instead of threads
        # offending_cells_data = []

        # # Create worker tasks
        # async def worker(query_str):
        #     cell_offenders = await fetch_cell_data(query_str)
        #     return cell_offenders

        # # Create tasks for all queries
        # tasks = [worker(query_str) for query_str in cell_query_list]

        # # Execute all tasks concurrently and wait for completion
        # results = await asyncio.gather(*tasks)

        # # Combine results
        # for cell_offenders in results:
        #     offending_cells_data.extend(cell_offenders)

        # find offending cells
        # lock = threading.Lock()
        offending_cells_data = []
        # function to compare classifications -- use Threads
        def worker(query_str):
            cell_offenders = fetch_cell_data(query_str)
            # logger.debug(json.dumps(cell_kpi_data, indent=4))
            offending_cells_data.extend(cell_offenders)

            # identify violations
            # cell_offenders = identify_threshold_violations(cell_kpi_data)
            # if cell_offenders:
            #     with lock:
            #         offending_cells_data.extend(cell_offenders)

        threads = []
        for record in cell_query_list:
            t = threading.Thread(target=worker, args=(record,)) # COMMA is important here
            threads.append(t)
            t.start()

        # Wait for all threads to finish
        for t in threads:
            t.join()

        logger.info(f"Count of records, offending_cells_data -->{len(offending_cells_data)}")
        logger.debug(f"offending_cells_data --> {json.dumps(offending_cells_data, indent=4)}")

        # Identify violations - CELL level
        top_offenders = identify_threshold_violations_cell(offending_cells_data)
        logger.info(f"Count of records, after filtering out violations --> {len(top_offenders)}")

        # Rearrange data structure, only for CELLs data
        offending_cells_data_rearranged = transform_data(offending_cells_data)
        logger.info(f"Count of top offenders --> {len(offending_cells_data_rearranged)}")
        top_offenders = offending_cells_data_rearranged

        # initialize kpi_readout_data
        kpi_readout_data = {
            "aoi": aoi,
            "engineer": engineer,
            "data": anomaly_data['data'],
            "trend_indicator": anomaly_data['trend_indicator'],
            "top_offenders": top_offenders
        }
        logger.info(json.dumps(kpi_readout_data, indent=4))

        # End timer
        end_time = time.time()
        logger.info(f"Execution time: {end_time - start_time:.4f} seconds")

        # Stream analysis results
        async for content in analyze_kpi_readout(kpi_readout_data):
            item = {'type': 'text', 'content': content}
            yield f"data: {json.dumps(item)}"
            yield "\n\n"

    except Exception as e:
        logger.info(f"Error in streaming process: {str(e)}")
        logger.info(traceback.format_exc())
        error_message = {'type': 'error',
                         'content': "I encountered an issue while processing your request. Please try again."}
        yield f"data: {json.dumps(error_message)}"
        yield "\n\n"


async def collect_kpi_data(aoi: str, engineer: str):
    """
    Collects and processes KPI data for analysis.
    Args:
        aoi (str): The area of interest to process
        engineer (str): The engineer identifier
    Returns:
        dict: Processed KPI data ready for analysis
    """
    try:
        # Start timer
        start_time = time.time()

        # Step-1: Fetch KPI data from station, for AOI
        aoi_data = await fetch_aoi_data(aoi)
        logger.info(f'Count of aoi_data --> {len(aoi_data)}')
        if not isinstance(aoi_data, list) or (len(aoi_data) == 0):
            raise ValueError("Either Invalid response or no data received from Station")

        # Step-2: Detect anomalies
        logger.info(f'Starting anomaly detection...')
        anomaly_data = detect_anomalies(aoi_data)
        logger.info(f'Anomaly detection completed.')

        # Step-4: identify threshold violations at AOI level
        aoi_offenders = identify_threshold_violations_aoi(aoi_data)
        logger.info(f'Count of aoi_offenders --> {len(aoi_offenders)}')

        # Step-5: Fetch KPI data from station, at CELL level, for each AOI offending KPI
        cell_query_list = build_query_strings(aoi_offenders)
        logger.info(f'Count of cell_query_list --> {len(cell_query_list)}')

        # find offending cells - using async tasks instead of threads
        offending_cells_data = []

        # Create worker tasks
        async def worker(query_str):
            cell_offenders = await fetch_cell_data(query_str)
            return cell_offenders

        # Create tasks for all queries
        tasks = [worker(query_str) for query_str in cell_query_list]
        # Execute all tasks concurrently and wait for completion
        results = await asyncio.gather(*tasks)
        # Combine results
        for cell_offenders in results:
            offending_cells_data.extend(cell_offenders)

        logger.info(f"Count of records, offending_cells_data -->{len(offending_cells_data)}")
        logger.debug(f"offending_cells_data --> {json.dumps(offending_cells_data, indent=4)}")

        # Identify violations - CELL level
        top_offenders = identify_threshold_violations_cell(offending_cells_data)
        logger.info(f"Count of records, after filtering out violations --> {len(top_offenders)}")

        # Rearrange data structure, only for CELLs data
        offending_cells_data_rearranged = transform_data(offending_cells_data)
        logger.info(f"Count of top offenders --> {len(offending_cells_data_rearranged)}")
        top_offenders = offending_cells_data_rearranged

        # initialize kpi_readout_data
        kpi_readout_data = {
            "aoi": aoi,
            "engineer": engineer,
            "data": anomaly_data['data'],
            "trend_indicator": anomaly_data['trend_indicator'],
            "top_offenders": top_offenders
        }

        logger.info(json.dumps(kpi_readout_data, indent=4))

        # End timer
        end_time = time.time()
        logger.info(f"Execution time: {end_time - start_time:.4f} seconds")

        return kpi_readout_data

    except Exception as e:
        logger.error(f"Error in data collection: {str(e)}")
        logger.error(traceback.format_exc())
        raise





# if __name__ == "__main__":
#     output = kpi_readout("ATL")

