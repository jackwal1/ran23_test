

# KPI readout
import json
# import requests
from utils import constants as CONST
# from utils.constants import KPI_THRESHOLDS, KPI_READOUT_LIST, KPI_READOUT_DURATION, STATION_ACCESS_TOKEN, STATION_BASE_URL
from utils.log_init import logger

import time
import traceback
# import threading
from .kpi_station_call import fetch_aoi_data, fetch_site_data, identify_threshold_violations_aoi, build_site_query_strings, transform_data, identify_threshold_violations, compute_avg_kpi
from .kpi_anomaly_detection import detect_anomalies
# from llms.llms import analyze_kpi_readout
import asyncio

DIR_PATH = "C:\\sohan\\projects\\DISH-genAI\\ran\\RAN-3-PM\\kpi_readout"

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

        # Step-1.a): Calculate average of each KPI, for AOI
        average_kpi = compute_avg_kpi(aoi_data)

        # Step-2: Detect anomalies
        logger.info(f'Starting anomaly detection...')
        anomaly_data = detect_anomalies(aoi_data)
        logger.info(f'Anomaly detection completed.')

        # Step-3: identify threshold violations at AOI level
        aoi_offenders = identify_threshold_violations_aoi(aoi_data)
        logger.info(f'Count of aoi_offenders --> {len(aoi_offenders)}')
        with open(f'{DIR_PATH}\\{aoi}_aoi_offenders.json', "w") as f:
            json.dump(aoi_offenders, f, indent=4, ensure_ascii=False)

        # Step-4: Fetch KPI data from station, at SITE level, for each offending KPI of AOI
        site_query_list = build_site_query_strings(aoi_offenders)
        logger.info(f'Count of site_query_list --> {len(site_query_list)}')

        # find offending sites - using async tasks instead of threads
        offending_sites_data = []

        # Create worker tasks
        async def worker(query_str):
            site_offenders = await fetch_site_data(query_str)
            return site_offenders

        # Create tasks for all queries
        tasks = [worker(query_str) for query_str in site_query_list]
        # Execute all tasks concurrently and wait for completion
        results = await asyncio.gather(*tasks)

        # with open(f'{DIR_PATH}\\{aoi}_sites_offenders_results.json', "w") as f:
        #     json.dump(results, f, indent=4, ensure_ascii=False)

        # Combine results
        for site_offenders_list in results:
            for sites in site_offenders_list:
                # remove bronze category sites
                site_name = sites.get("site", "")
                site_category = CONST.SITES_CATEGORY.get(site_name, "Bronze")
                if site_category != "Bronze":
                    sites["category"] = site_category
                    offending_sites_data.append(sites)

        logger.info(f"Count of records, offending_sites_data -->{len(offending_sites_data)}")
        logger.debug(f"offending_sites_data --> {json.dumps(offending_sites_data, indent=4)}")
        with open(f'{DIR_PATH}\\{aoi}_sites_offenders.json', "w") as f:
            json.dump(offending_sites_data, f, indent=4, ensure_ascii=False)

        # Identify violations - site level -- filter out non-violations (though they are top 10 offending for a KPI)
        top_offenders = identify_threshold_violations(offending_sites_data)
        logger.info(f"Count of records, after filtering out violations --> {len(top_offenders)}")

        # Rearrange data structure, only for sites data
        offending_sites_data_rearranged = transform_data(offending_sites_data)
        logger.info(f"Count of top offending SITES --> {len(offending_sites_data_rearranged)}")
        top_offenders = offending_sites_data_rearranged

        # initialize kpi_readout_data
        kpi_readout_data = {
            "aoi": aoi,
            "engineer": engineer,
            "average_kpi": average_kpi,            
            "data": anomaly_data['data'],
            "trend_indicator": anomaly_data['trend_indicator'],
            "top_offenders": top_offenders,

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

