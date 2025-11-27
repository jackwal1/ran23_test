# Agent Testing Utility

This utility provides a comprehensive framework for testing AI agents with different scenarios and generating automated assessment reports. The utility is now **generic** and can test any agent with any LLM by passing them as arguments.

## Features

- **Generic Agent Testing**: Test any agent with any LLM by passing them as arguments
- **CSV-based Test Scenarios**: Define test scenarios in a simple CSV format
- **Conversation Flow Management**: Groups CSV rows into realistic conversation flows
- **Thread ID Consistency**: Uses a single thread ID for entire test session
- **Automated Execution**: Run multiple test scenarios automatically
- **LLM Assessment**: Use AI to evaluate test results and generate reports
- **Detailed Reporting**: Save both raw results and assessment reports
- **Flexible Configuration**: Easy to extend with new scenarios
- **Organized Structure**: Clean separation of scripts, data, and results
- **Real Agent Integration**: Executes actual agent tools and maintains conversation context

## File Structure

```
tests/
├── scripts/                   # All Python test scripts and utilities
│   ├── agent_test_utility.py      # Main testing utility class (generic)
│   ├── run_agent_test.py          # Test runner with RAN Config QA Agent
│   ├── test_llm_assessment.py     # LLM assessment test
│   ├── test_single_scenario.py    # Single scenario testing
│   ├── test_tool_switching_scenario.py  # Tool switching tests
│   ├── test_fetch_gpl_values.py   # GPL values testing
│   ├── test_fetch_ran_config.py   # RAN config testing
│   ├── test_ran_config_qa_agent_context.py  # Agent context testing
│   └── setup_checkpoints_table.py # Database setup utilities
├── data/                     # Input CSV files and test data
│   └── sample_test_scenarios.csv  # Sample test scenarios with conversation flows
├── results/                  # Output directory for test results
│   ├── agent_test_results_*.txt      # Formatted test execution results
│   ├── agent_assessment_report_*.txt  # LLM assessment reports
│   └── test_tool_switching_*.txt     # Tool switching test results
├── README_agent_testing.md   # This documentation
└── README_organized_structure.md  # New structure documentation
```

## CSV Format

The test scenarios CSV file should have the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `scenario_name` | Name/ID of the test scenario | "Vendor Context" |
| `user_input` | The query/input to test | "What is the current tilt value for site HOHOU00036B?" |
| `expected_response` | Description of expected behavior | "The agent should ask for vendor" |
| `description` | Additional description of the test | "Test vendor identification flow" |

**Note**: Rows with the same `scenario_name` are grouped into conversation flows, maintaining context across steps.

## Usage

### 1. Create Test Scenarios

Create a CSV file with your test scenarios. Multiple rows with the same `scenario_name` will be grouped into conversation flows:

```csv
scenario_name,user_input,expected_response,description
Vendor Context,What is the current tilt value for site HOHOU00036B?,The agent should ask for vendor,Test vendor identification
Vendor Context,Mavenir,The agent should return the tilt value for Mavenir site,Test vendor-specific response
Vendor Context,ok thanks what about site HOUST12121?,The agent should confirm whether vendor is mavenir,Test conversation continuity
Vendor Context,No its samsung,The agent return the value for samsung site,Test vendor switching
```

### 2. Run Tests with Generic Agent

```python
from tests.scripts.agent_test_utility import AgentTestUtility

# Define your agent initializer function
def initialize_my_agent():
    # Your agent initialization code here
    return my_agent

# Initialize the utility with your agent and LLM
test_utility = AgentTestUtility(
    csv_file_path="path/to/your/scenarios.csv",
    agent_initializer=initialize_my_agent,
    llm_model=your_llm_model
)

# Run complete test suite
results = test_utility.run_complete_test_suite()

# Access results
print(f"Total tests: {results['total_tests']}")
print(f"Successful: {results['successful_tests']}")
print(f"Failed: {results['failed_tests']}")
```

### 3. Run with RAN Config QA Agent (Example)

```bash
# From the tests directory
cd tests/scripts
python run_agent_test.py

# Or from the project root
python tests/scripts/run_agent_test.py
```

## Generic Agent Testing

The utility is now **generic** and can test any agent with any LLM:

### Agent Initializer Function
Your agent initializer should:
- Return an agent instance that can be invoked
- Accept a `thread_id` parameter for conversation context
- Handle the agent's response format

### LLM Model
Pass any LangChain-compatible LLM model for assessment.

### Example with Mock Agent

```python
# Example usage with mock agent and LLM
def initialize_mock_agent():
    return MockAgent()

def initialize_mock_llm():
    return MockLLM()

test_utility = AgentTestUtility(
    csv_file_path="../data/sample_test_scenarios.csv",
    agent_initializer=initialize_mock_agent,
    llm_model=initialize_mock_llm()
)
```

## Output Files

The utility generates formatted output files:

### 1. Formatted Results (TXT)
- **Location**: `tests/results/agent_test_results_YYYYMMDD_HHMMSS.txt`
- **Content**: Detailed test results including:
  - Scenario summaries with pass/fail rates
  - Step-by-step execution details
  - User input and actual response
  - Execution time and timestamps
  - Overall success statistics

### 2. Assessment Report (TXT)
- **Location**: `tests/results/agent_assessment_report_YYYYMMDD_HHMMSS.txt`
- **Content**: LLM-generated assessment including:
  - Pass/fail rate
  - Summary of issues
  - Recommendations
  - Individual test results

## Key Features

### Conversation Flow Management
- Groups CSV rows by `scenario_name` into conversation flows
- Maintains context across multiple steps
- Waits for agent response before sending next prompt
- Realistic conversation simulation

### Thread ID Consistency
- Generates unique thread ID for entire test session
- Uses same thread ID across all scenarios and steps
- Ensures consistent conversation context

### Real Agent Integration
- Executes actual agent tools (e.g., `fetch_ran_config`, `fetch_gpl_values`)
- Maintains conversation state
- Handles tool calls and responses
- Realistic agent behavior testing

## Sample Test Results

Recent test run results:
```
================================================================================
AGENT TEST RESULTS REPORT
================================================================================
Generated: 2025-07-15 20:16:05
Total Test Steps: 9
Total Scenarios: 2
Overall Passed: 9
Overall Failed: 0
Overall Success Rate: 100.0%
================================================================================

SCENARIO SUMMARY
----------------------------------------
📋 Vendor Context:
   Steps: 4 | Passed: 4 | Failed: 0 | Success Rate: 100.0%

📋 Ambiguous scenario:
   Steps: 5 | Passed: 5 | Failed: 0 | Success Rate: 100.0%
```

## Customization

### Adding New Test Scenarios

1. Create or modify your CSV file with new scenarios in the `data/` directory
2. Update the file path in your test scripts to use `../data/your_file.csv`
3. Run the test utility with your CSV file
4. Review the generated assessment report

### Modifying Assessment Criteria

Edit the `generate_assessment_prompt()` method in `AgentTestUtility` class to customize the LLM assessment criteria.

### Extending Test Execution

Modify the `execute_scenario()` method to integrate with different agent systems or add custom validation logic.

## Sample Test Scenarios

The included `data/sample_test_scenarios.csv` contains conversation flows:

1. **Vendor Context** (4 steps): Tests vendor identification and parameter retrieval
2. **Ambiguous scenario** (5 steps): Tests parameter value queries and GPL value retrieval

Each scenario demonstrates:
- Vendor identification flows
- Tool switching between different functions
- Conversation continuity
- Parameter value retrieval
- GPL value queries

## Requirements

- Python 3.7+
- CSV file with test scenarios
- Access to LLM for assessment (optional)
- Agent/router system to test against
- LangChain-compatible agent and LLM models

## Troubleshooting

### Import Errors
If you encounter import errors, ensure the project root is in your Python path:
```python
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### File Path Issues
When running scripts from the `scripts/` directory, use relative paths:
- For data files: `../data/your_file.csv`
- For output: `../results/` (automatically handled by the utility)

### Agent Initialization Issues
Ensure your agent initializer:
- Returns a callable agent instance
- Accepts `thread_id` parameter
- Handles the expected response format

### LLM Not Available
If the LLM is not available, the utility will still run tests but will generate a placeholder assessment message.

### Router Not Available
If the agent router is not available, the utility will return placeholder responses for testing the framework.

## Example Output

```
============================================================
AGENT TEST UTILITY DEMONSTRATION
============================================================
Agent initializer: initialize_ran_config_qa_agent
LLM model: ChatWatsonx

Initializing AgentTestUtility...

Running test suite...

============================================================
TEST SUITE EXECUTION COMPLETED
============================================================
Total tests: 9
Successful: 9
Failed: 0
Results file: ../results/agent_test_results_20250715_201605.txt

Sample test results:
================================================================================
AGENT TEST RESULTS REPORT
================================================================================
Generated: 2025-07-15 20:16:05
Total Test Steps: 9
Total Scenarios: 2
Overall Passed: 9
Overall Failed: 0
Overall Success Rate: 100.0%
================================================================================

SCENARIO SUMMARY
----------------------------------------
📋 Vendor Context:
   Steps: 4 | Passed: 4 | Failed: 0 | Success Rate: 100.0%

📋 Ambiguous scenario:
   Steps: 5 | Passed: 5 | Failed: 0 | Success Rate: 100.0%
============================================================
Test utility demonstration completed!
============================================================
``` 