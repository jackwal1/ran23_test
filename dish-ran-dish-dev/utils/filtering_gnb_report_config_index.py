import logging
import asyncio
from typing import List, Dict, Optional
import re
from utils import constants as CONST

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

# Global mappings
A5_REPORT_CONFIG_MAPPING = {
    5: {
        'event': 'A5',
        'purpose': 'intra-nr-handover-purpose',
        'target_freq': 'n71',
        'meas_object_index': [0, 6, 7, 10]
    },
    6: {
        'event': 'A5',
        'purpose': 'intra-nr-handover-purpose',
        'target_freq': 'n70',
        'meas_object_index': [1]
    },
    8: {
        'event': 'A5',
        'purpose': 'intra-nr-handover-purpose',
        'target_freq': 'n66_1',
        'meas_object_index': [3, 8, 9, 11]
    },
    9: {
        'event': 'A5',
        'purpose': 'intra-nr-handover-purpose',
        'target_freq': 'n71_2',
        'meas_object_index': [0, 6, 7, 10]
    },
    13: {
        'event': 'A5',
        'purpose': 'intra-nr-handover-purpose',
        'target_freq': 'n66_2',
        'meas_object_index': [3, 8, 9, 11]
    }
}

MEASUREMENT_OBJECT_MAPPING = {
    0: {
        'band': 'n71',
        'ssb_freq': 'Co-located n71 freq',
        'description': 'Co-located n71 frequency'
    },
    1: {
        'band': 'n70',
        'ssb_freq': '401050',
        'description': 'n70 band frequency'
    },
    2: {
        'band': 'n26',
        'ssb_freq': '173330',
        'description': 'n26 band frequency'
    },
    3: {
        'band': 'n66',
        'ssb_freq': 'Co-located n66 freq',
        'description': 'Co-located n66 frequency'
    },
    4: {
        'band': 'n66_SDL',
        'ssb_freq': '438030',
        'description': 'n66 SDL frequency'
    },
    5: {
        'band': 'n29_SDL',
        'ssb_freq': '714970',
        'description': 'n29 SDL frequency'
    },
    6: {
        'band': 'n71',
        'ssb_freq': 'Second n71 frequency',
        'description': 'Second n71 frequency'
    },
    7: {
        'band': 'n71',
        'ssb_freq': 'Third n71 frequency',
        'description': 'Third n71 frequency'
    },
    8: {
        'band': 'n66',
        'ssb_freq': 'Second n66 frequency',
        'description': 'Second n66 frequency'
    },
    9: {
        'band': 'n66',
        'ssb_freq': 'Third n66 frequency',
        'description': 'Third n66 frequency'
    },
    10: {
        'band': 'n71',
        'ssb_freq': 'Forth n71 frequency',
        'description': 'Fourth n71 frequency'
    },
    11: {
        'band': 'n66',
        'ssb_freq': 'Forth n66 frequency',
        'description': 'Fourth n66 frequency'
    }
}

async def extract_band_prefix(band_input: str) -> str:
    """
    Extract the band prefix (e.g., n66, n71, n70) from band input.

    Args:
        band_input (str): Input band string like 'n70_AWS-4', 'n71_F-G', etc.

    Returns:
        str: Extracted band prefix
    """
    logger.debug(f"Extracting band prefix from: {band_input}")

    # Use regex to extract the band prefix (n followed by digits)
    match = re.match(r'(n\d+)', band_input.lower())
    if match:
        band_prefix = match.group(1)
        logger.debug(f"Extracted band prefix: {band_prefix}")
        return band_prefix

    logger.warning(f"Could not extract band prefix from: {band_input}")
    return ""

async def find_measurement_objects_by_band(band_prefix: str) -> List[int]:
    """
    Find all measurement object indices that match the given band prefix.

    Args:
        band_prefix (str): Band prefix like 'n66', 'n71', etc.

    Returns:
        List[int]: List of measurement object indices
    """
    logger.debug(f"Finding measurement objects for band: {band_prefix}")

    matching_objects = []
    for obj_idx, obj_data in MEASUREMENT_OBJECT_MAPPING.items():
        obj_band = obj_data['band'].lower()
        # Check if the band starts with the prefix (handles cases like n66, n66_SDL)
        if obj_band.startswith(band_prefix.lower()):
            matching_objects.append(obj_idx)
            logger.debug(f"Found matching measurement object {obj_idx} for band {obj_band}")

    logger.info(f"Found {len(matching_objects)} measurement objects for band {band_prefix}: {matching_objects}")
    return matching_objects

async def find_prioritized_config_by_measurement_objects(measurement_objects: List[int], existing_data: List[Dict]) -> Optional[Dict]:
    """
    Find a single prioritized report config based on measurement objects and existing data.
    Priority order: n66_1 > n66_2, n71 > n71_2

    Args:
        measurement_objects (List[int]): List of measurement object indices
        existing_data (List[Dict]): List of existing configuration dictionaries

    Returns:
        Optional[Dict]: Single prioritized configuration dictionary or None
    """
    logger.debug(f"Finding prioritized config for measurement objects: {measurement_objects}")

    # Create a mapping of existing data by report_config_entry_index for quick lookup
    existing_by_index = {}
    for data_entry in existing_data:
        if 'report_config_entry_index' in data_entry:
            index_key = str(data_entry['report_config_entry_index'])
            existing_by_index[index_key] = data_entry

    logger.debug(f"Available existing indices: {list(existing_by_index.keys())}")

    # Define priority order for target frequencies
    priority_order = ['n66_1', 'n66_2', 'n71', 'n71_2']

    # Find matching report configs with their target frequencies
    matching_configs_with_freq = []
    measurement_obj_set = set(measurement_objects)

    for config_idx, config_data in A5_REPORT_CONFIG_MAPPING.items():
        config_meas_objects = set(config_data['meas_object_index'])
        # Check if there's any intersection between the sets
        if measurement_obj_set & config_meas_objects:
            matching_configs_with_freq.append({
                'config_index': config_idx,
                'target_freq': config_data['target_freq'],
                'matching_meas_objects': list(config_meas_objects & measurement_obj_set)
            })
            logger.debug(f"Config {config_idx} matches with target_freq: {config_data['target_freq']}")

    logger.info(f"Found {len(matching_configs_with_freq)} matching report configs")

    # Sort by priority order
    for priority_freq in priority_order:
        for config_info in matching_configs_with_freq:
            if config_info['target_freq'] == priority_freq:
                config_idx_str = str(config_info['config_index'])
                if config_idx_str in existing_by_index:
                    logger.info(f"Found prioritized config: Index {config_idx_str}, Target Freq: {priority_freq}")
                    logger.info(f"Matching measurement objects: {config_info['matching_meas_objects']}")
                    return existing_by_index[config_idx_str]
                else:
                    logger.debug(f"Config {config_idx_str} with target_freq {priority_freq} not found in existing data")

    logger.warning("No prioritized config found in existing data")
    return None

async def process_event(event: str, band: str, existing_data: List[Dict]) -> List[Dict]:
    """
    Process A5 event with given band and return configuration(s) based on band type.
    For exact matches with n66_1, n66_2, n71_2: returns all matching configs (no priority logic)
    For other bands: returns single prioritized configuration or original data

    Args:
        event (str): Event type (should be 'A5' for this processor)
        band (str): Band specification like 'n70_AWS-4', 'n71_F-G', etc.
        existing_data (List[Dict]): List of dictionaries containing report_config_entry_index

    Returns:
        List[Dict]: Configuration(s) based on band type and matching logic
    """
    logger.info(f"Processing event: {event}, band: {band}")
    logger.info(f"Input existing_data contains {len(existing_data)} entries")

    # Log existing data indices for debugging
    existing_indices = []
    for data in existing_data:
        if 'report_config_entry_index' in data:
            existing_indices.append(data['report_config_entry_index'])
    logger.debug(f"Existing report_config_entry_index values: {existing_indices}")

    # Validate event type
    if event.upper() != 'A5':
        logger.error(f"Unsupported event type: {event}. Only A5 events are supported.")
        logger.info("Returning original existing_data as fallback")
        return existing_data

    # Extract band prefix
    band_prefix = await extract_band_prefix(band)
    if not band_prefix:
        logger.warning(f"Could not extract band prefix from {band}. Returning original existing_data.")
        return existing_data

    # Check if band contains exact priority bands (n66_1, n66_2, n71_2) as prefix
    exact_priority_bands = ['n66_1', 'n66_2', 'n71_2']
    matched_priority_band = None

    for priority_band in exact_priority_bands:
        if band.lower().startswith(priority_band.lower()):
            matched_priority_band = priority_band
            break

    if matched_priority_band:
        logger.info(f"Band '{band}' contains priority band '{matched_priority_band}' - skipping priority logic")

        # Create lookup for existing data
        existing_by_index = {}
        for data_entry in existing_data:
            if 'report_config_entry_index' in data_entry:
                index_key = str(data_entry['report_config_entry_index'])
                existing_by_index[index_key] = data_entry

        # Find the single config that matches the priority band target frequency
        for config_idx, config_data in A5_REPORT_CONFIG_MAPPING.items():
            if config_data['target_freq'].lower() == matched_priority_band.lower():
                config_idx_str = str(config_idx)
                if config_idx_str in existing_by_index:
                    logger.info(f"Found exact match config: Index {config_idx_str}, Target Freq: {config_data['target_freq']}")
                    logger.info(f"Returning single exact matching configuration")
                    return [existing_by_index[config_idx_str]]  # Return as list with single element
                else:
                    logger.warning(f"Config {config_idx_str} with target_freq {matched_priority_band} not found in existing data")
                    break  # There should be only one match, so break after finding it

        logger.warning(f"No exact matching config found for priority band {matched_priority_band}. Returning original existing_data.")
        return existing_data

    # For non-priority bands, use the original priority logic
    logger.info(f"Band '{band}' does not contain priority bands - using priority logic")

    # Find measurement objects for the band
    measurement_objects = await find_measurement_objects_by_band(band_prefix)
    if not measurement_objects:
        logger.warning(f"No measurement objects found for band {band_prefix}. Returning original existing_data.")
        return existing_data

    # Find single prioritized config
    prioritized_config = await find_prioritized_config_by_measurement_objects(measurement_objects, existing_data)

    if prioritized_config:
        logger.info(f"Successfully found prioritized config with index: {prioritized_config['report_config_entry_index']}")
        logger.info(f"Returning single configuration instead of {len(existing_data)} original entries")
        return [prioritized_config]  # Return as list with single element
    else:
        logger.warning(f"No prioritized config found for band {band_prefix}. Returning original existing_data.")
        logger.info(f"Fallback: Returning all {len(existing_data)} original entries")
        return existing_data

async def get_band_summary(band_prefix: str) -> Dict:
    """
    Get a summary of all measurement objects and report configs for a given band.

    Args:
        band_prefix (str): Band prefix like 'n66', 'n71', etc.

    Returns:
        Dict: Summary information
    """
    logger.info(f"Getting summary for band: {band_prefix}")

    measurement_objects = await find_measurement_objects_by_band(band_prefix)

    # Find report configs for the measurement objects
    report_configs = []
    measurement_obj_set = set(measurement_objects)

    for config_idx, config_data in A5_REPORT_CONFIG_MAPPING.items():
        config_meas_objects = set(config_data['meas_object_index'])
        if measurement_obj_set & config_meas_objects:
            report_configs.append(config_idx)

    summary = {
        'band': band_prefix,
        'measurement_objects': measurement_objects,
        'report_configs': report_configs,
        'measurement_object_details': [
            {
                'index': idx,
                'band': MEASUREMENT_OBJECT_MAPPING[idx]['band'],
                'description': MEASUREMENT_OBJECT_MAPPING[idx]['description']
            }
            for idx in measurement_objects
        ]
    }

    logger.info(f"Band {band_prefix} summary: {len(measurement_objects)} measurement objects, {len(report_configs)} report configs")
    return summary

async def main():
    """
    Example usage of the A5 Event Processing functions
    """
    logger.info("Starting A5 Event Processing Example")

    # Sample existing_data with dictionary format
    sample_existing_data = [
        {
            'report_config_entry_index': '5',
            'event_type': 'A5',
            'purpose': 'intra-nr-handover-purpose',
            'additional_info': 'config_5_data'
        },
        {
            'report_config_entry_index': '6',
            'event_type': 'A5',
            'purpose': 'intra-nr-handover-purpose',
            'additional_info': 'config_6_data'
        },
        {
            'report_config_entry_index': '8',
            'event_type': 'A5',
            'purpose': 'intra-nr-handover-purpose',
            'additional_info': 'config_8_data'
        },
        {
            'report_config_entry_index': '9',
            'event_type': 'A5',
            'purpose': 'intra-nr-handover-purpose',
            'additional_info': 'config_9_data'
        },
        {
            'report_config_entry_index': '13',
            'event_type': 'A5',
            'purpose': 'intra-nr-handover-purpose',
            'additional_info': 'config_13_data'
        },
        {
            'report_config_entry_index': '1',
            'event_type': 'A1',
            'purpose': 'other-purpose',
            'additional_info': 'config_1_data'
        },
        {
            'report_config_entry_index': '2',
            'event_type': 'A2',
            'purpose': 'other-purpose',
            'additional_info': 'config_2_data'
        }
    ]

    # Test cases
    test_cases = [
        {
            'event': 'A5',
            'band': 'n70_AWS-4',
            'existing_data': sample_existing_data
        },
        {
            'event': 'A5',
            'band': 'n71_F-G',
            'existing_data': sample_existing_data
        },
        {
            'event': 'A5',
            'band': 'n66_C-Block',
            'existing_data': sample_existing_data
        },
        {
            'event': 'A5',
            'band': 'n66_1',  # Exact priority match - should skip priority logic
            'existing_data': sample_existing_data
        },
        {
            'event': 'A5',
            'band': 'n71_2',  # Exact priority match - should skip priority logic
            'existing_data': sample_existing_data
        },
        {
            'event': 'A5',
            'band': 'n66_2_G_H_I',  # Priority band with suffix - should skip priority logic
            'existing_data': sample_existing_data
        },
        {
            'event': 'A1',  # Unsupported event
            'band': 'n71_Test',
            'existing_data': sample_existing_data[:3]  # Smaller subset for testing
        }
    ]

    # Process test cases
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n--- Test Case {i} ---")
        logger.info(f"Event: {test_case['event']}, Band: {test_case['band']}")
        logger.info(f"Input data count: {len(test_case['existing_data'])}")

        result = await process_event(
            test_case['event'],
            test_case['band'],
            test_case['existing_data']
        )

        logger.info(f"Filtered result count: {len(result)}")
        logger.info("Filtered entries:")
        for entry in result:
            logger.info(f"  - Index: {entry['report_config_entry_index']}, Info: {entry.get('additional_info', 'N/A')}")

    # Get band summaries
    logger.info("\n--- Band Summaries ---")
    for band in ['n70', 'n71', 'n66']:
        summary = await get_band_summary(band)
        logger.info(f"\nSummary for {band}:")
        logger.info(f"  Measurement Objects: {summary['measurement_objects']}")
        logger.info(f"  Report Configs: {summary['report_configs']}")

    # Demonstrate filtering with realistic data
    logger.info("\n--- Realistic Example ---")
    realistic_data = [
        {
            'report_config_entry_index': '5',
            'ssb_config_ssb_freq': '129870',
            'purpose': 'intra-nr-handover-purpose',
            'band': 'n71_G'
        },
        {
            'report_config_entry_index': '8',
            'ssb_config_ssb_freq': '431530',
            'purpose': 'intra-nr-handover-purpose',
            'band': 'n66_G'
        },
        {
            'report_config_entry_index': '6',
            'ssb_config_ssb_freq': '401050',
            'purpose': 'intra-nr-handover-purpose',
            'band': 'n70'
        }
    ]

    result = await process_event('A5', 'n71_F-G', realistic_data)
    logger.info(f"Realistic example - n71 band filtering:")
    logger.info(f"Input: {len(realistic_data)} entries, Output: {len(result)} entries")
    for entry in result:
        logger.info(f"  Selected: {entry}")

if __name__ == "__main__":
    asyncio.run(main())