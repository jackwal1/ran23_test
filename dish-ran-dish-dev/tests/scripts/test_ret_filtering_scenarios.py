import pytest
import asyncio
import csv
from unittest.mock import patch, AsyncMock, MagicMock

# The module to be tested is in the parent directory, so we need to adjust the path
from tools.ran_automation_tools import handle_ret_update

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

# Global variable to store test data
CSV_DATA = []

def load_csv_data():
    """Loads test data from the CSV file."""
    global CSV_DATA
    if CSV_DATA:
        return
    with open('tests/data/ret_site.csv', mode='r') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            # Convert numeric strings to actual numbers where applicable
            for key, value in row.items():
                if key in ['HDLC_ADDRESS', 'TILT', 'PORT', 'ANTENNA_UNIT', 'MINIMUMTILT', 'MAXIMUMTILT']:
                    try:
                        row[key] = float(value) if '.' in value else int(value)
                    except (ValueError, TypeError):
                        pass
            CSV_DATA.append(row)

# Load data once before tests run
load_csv_data()

# Helper to mock the database session
def mock_db_session(query_val):
    # Filter data based on the ILIKE 'val%' part of the query
    return [row for row in CSV_DATA if row['CELLNAME'].upper().startswith(query_val.upper())]

@pytest.fixture
def mock_dependencies():
    """A pytest fixture to mock external dependencies."""
    with patch('tools.ran_automation_tools._fetch_ran_vendor', new_callable=AsyncMock) as mock_fetch_vendor, \
         patch('tools.ran_automation_tools.snow_db.get_db_session') as mock_get_session, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:

        # Mock vendor fetch to always return 'mavenir'
        mock_fetch_vendor.return_value = {"vendor": "mavenir"}

        # Define the side effect for the mocked asyncio.to_thread
        async def to_thread_side_effect(func, *args, **kwargs):
            # This is where we simulate the behavior of session.execute
            if "execute" in str(func):
                query, params = args[0], args[1] # Extract the query and params
                result_mock = MagicMock()
                query_val = params.get("val", "").replace('%', '')
                filtered_data = mock_db_session(query_val)
                result_mock.keys.return_value = CSV_DATA[0].keys() if CSV_DATA else []
                result_mock.fetchall.return_value = [tuple(r.values()) for r in filtered_data]
                return result_mock
            return await asyncio.get_event_loop().run_in_executor(None, func, *args)

        mock_to_thread.side_effect = to_thread_side_effect

        yield mock_fetch_vendor, mock_get_session, mock_to_thread


# --- Test Cases ---

async def test_filter_by_site_only(mock_dependencies):
    """Tests filtering by site_name only, expecting multiple unique results."""
    args = {"operation": "validate", "site_name": "ALALB00001C"}
    result = await handle_ret_update.ainvoke(args)
    
    assert len(result) == 1
    assert "unique_options" in result[0]
    # Based on the CSV, there should be multiple unique cellname/hdlc_address combinations
    assert len(result[0]["unique_options"]) > 1 
    assert "unique combinations found" in result[0]["tool_message"]


async def test_filter_by_site_and_sector(mock_dependencies):
    """Tests filtering by site_name and a specific sector."""
    args = {"operation": "validate", "site_name": "ALALB00001C", "sector": "3"}
    result = await handle_ret_update.ainvoke(args)
    
    assert len(result) == 1
    assert "unique_options" in result[0]
    # Check that all returned options are for sector 3
    for option in result[0]["unique_options"]:
        assert '_3_' in option['cellname']
    # Based on CSV, filtering by sector 3 still leaves multiple combinations
    assert len(result[0]["unique_options"]) > 1

async def test_filter_by_site_and_hdlc(mock_dependencies):
    """Tests filtering by site_name and a specific hdlc_address."""
    args = {"operation": "validate", "site_name": "ALALB00001C", "hdlc_address": "1"}
    result = await handle_ret_update.ainvoke(args)
    
    assert len(result) == 1
    assert "unique_options" in result[0]
    # All options should have hdlc_address = 1
    for option in result[0]["unique_options"]:
        assert option['hdlc_address'] == 1
    assert len(result[0]["unique_options"]) > 1


async def test_find_unique_cell_with_multiple_filters(mock_dependencies):
    """Tests finding a single, unique cell using multiple filters."""
    args = {
        "operation": "validate",
        "site_name": "ALALB00001C",
        "sector": "3",
        "band": "n29",
        "hdlc_address": "1"
    }
    result = await handle_ret_update.ainvoke(args)
    
    assert len(result) == 1
    assert "confirmed_parameters" in result[0]
    confirmed = result[0]["confirmed_parameters"]
    assert confirmed["cellname"] == "ALALB00001C_3_n29_E_DL"
    assert confirmed["hdlc_address"] == 1
    assert result[0]["tool_message"].startswith("Successfully identified the target cell")


async def test_find_unique_cell_by_cellname_and_hdlc(mock_dependencies):
    """Tests finding a unique cell directly with cellname and hdlc_address."""
    args = {
        "operation": "validate",
        "cell_name": "ALALB00001C_2_n71_A",
        "hdlc_address": "2"
    }
    result = await handle_ret_update.ainvoke(args)
    
    assert len(result) == 1
    assert "confirmed_parameters" in result[0]
    confirmed = result[0]["confirmed_parameters"]
    assert confirmed["cellname"] == "ALALB00001C_2_n71_A"
    assert confirmed["hdlc_address"] == 2


async def test_no_match_scenario(mock_dependencies):
    """Tests a filter combination that should return no results."""
    args = {
        "operation": "validate",
        "site_name": "ALALB00001C",
        "port": "99" # This port does not exist in the data
    }
    result = await handle_ret_update.ainvoke(args)
    
    assert len(result) == 1
    assert "tool_message" in result[0]
    assert "No matching records found" in result[0]["tool_message"]

async def test_validation_failure_range(mock_dependencies):
    """Tests a scenario where tilt validation fails due to being out of range."""
    args = {
        "operation": "validate",
        "cell_name": "ALALB00001C_3_n29_E_DL",
        "hdlc_address": "1",
        "target_tilt": "20.0" # Min is 2.0, Max is 12.0
    }
    result = await handle_ret_update.ainvoke(args)
    
    assert len(result) == 1
    assert "tool_message" in result[0]
    assert "Validation failed" in result[0]["tool_message"]
    assert "outside allowed range" in result[0]["tool_message"]

async def test_validation_failure_same_value(mock_dependencies):
    """Tests a scenario where validation succeeds but gives an info message because target is same as current."""
    args = {
        "operation": "validate",
        "cell_name": "ALALB00001C_3_n29_E_DL",
        "hdlc_address": "1",
        "target_tilt": "2.0" # Current is 2.0
    }
    result = await handle_ret_update.ainvoke(args)
    
    assert len(result) == 1
    assert "tool_message" in result[0]
    assert "Successfully identified" in result[0]["tool_message"]
    assert "is the same as the current value" in result[0]["tool_message"]

async def test_successful_update_flow(mock_dependencies):
    """Tests the full validate -> update flow."""
    validate_args = {
        "operation": "validate",
        "cell_name": "ALALB00001C_1_n71_A",
        "hdlc_address": "2",
        "target_tilt": "10.0"
    }
    
    # 1. Validate
    validate_result = await handle_ret_update.ainvoke(validate_args)
    assert "confirmed_parameters" in validate_result[0]

    # 2. Update
    update_args = {
        "operation": "update",
        "cell_name": "ALALB00001C_1_n71_A",
        "hdlc_address": "2",
        "target_tilt": "10.0"
    }
    update_result = await handle_ret_update.ainvoke(update_args)
    
    assert len(update_result) == 1
    assert update_result[0]["status"] == "success"
    assert update_result[0]["target_tilt"] == "10.0"
    assert update_result[0]["cell_name"] == "ALALB00001C_1_n71_A" 