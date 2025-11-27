# Tool Calling Test Utility

This utility provides a generic framework for testing agent tool calling capabilities. It can be used with any agent that supports tool calling functionality.

## Overview

The `ToolCallingTestUtility` class allows you to:

- Test agent tool calling accuracy
- Validate tool parameters
- Test context retention across conversation steps
- Test vendor switching and context management
- Generate detailed test reports

## Features

### 🔧 Generic Design
- Works with any agent that supports tool calling
- Configurable agent initializer function
- Flexible CSV-based test scenario format

### 📊 Comprehensive Testing
- Tool call validation
- Parameter validation
- Context retention testing
- Vendor switching scenarios
- Error handling validation

### 📈 Detailed Reporting
- Success/failure statistics
- Detailed test results
- Parameter validation details
- Execution time tracking
- LLM assessment reports
- PASS/FAIL evaluation with explanations

## CSV File Format

The test scenarios are defined in a CSV file with the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `scenario` | Name of the test scenario | "Mavenir RAN Config Context Chain" |
| `step` | Step number within the scenario | 1, 2, 3... |
| `user_question` | The user's input/question | "What is the current tilt value for site HOHOU00036B?" |
| `expected_tool_call` | Expected tool name to be called | "fetch_ran_config" or "NO_TOOL_CALL" |
| `tool_params` | Expected tool parameters (human-friendly description) | `vendor should be mavenir, parameter should be tilt` |
| `agent_response` | Expected agent response description | "Agent should call fetch_ran_config with Mavenir vendor" |
| `description` | Additional description of the test case | "Test agent asking for vendor when not specified" |

### Special Values

- **`NO_TOOL_CALL`**: Use this when you expect the agent to ask for clarification (e.g., vendor specification) instead of calling a tool
- **Empty `tool_params`**: Use empty string when no parameters are expected

### Parameter Format

The `tool_params` column uses human-friendly descriptions instead of JSON. The utility automatically parses these descriptions into structured parameters.

**Supported Formats:**
- `vendor should be mavenir, parameter should be tilt`
- `vendor=mavenir, parameter=tilt`
- `vendor: mavenir, parameter: tilt`
- `mavenir vendor, tilt parameter`

**Supported Parameters:**
- **Vendors**: mavenir, samsung, dish, ericsson, nokia
- **Parameters**: tilt, operational_state, administrative_state, rru_alarms, ret_tilt, preambleReceivedTargetPwr, Event A3 - Report Interval, qHyst, ACME_features, MaxAnrTimerDuration, puschP0NominalWithoutGrant, cell_parameters, pdcch1SymbEnable
- **Sites**: HOHOU00036B
- **CUCPs**: JKRLA627035000, LSSNA741025000
- **DUs**: 741025022
- **Cell Identities**: 541
- **Special Flags**: check_optimal, impact_analysis, general

## Usage

### Basic Usage

```python
import asyncio
from tool_calling_test_utility import ToolCallingTestUtility
from agent.ran_config_qa_agent import initialize_ran_config_qa_agent

async def main():
    # Define agent initializer
    async def agent_initializer():
        return await initialize_ran_config_qa_agent()
    
    # Get LLM model for assessment
    def get_assessment_llm():
        from llms.llms import chatmodel_mistral_large_ran_2
        return chatmodel_mistral_large_ran_2
    
    llm_model = get_assessment_llm()
    
    # Initialize test utility
    test_utility = ToolCallingTestUtility(
        csv_file_path="../data/sample_tool_calling_scenarios.csv",
        agent_initializer=agent_initializer,
        llm_model=llm_model,
        output_dir="../results"
    )
    
    # Run tests
    results = await test_utility.run_complete_test_suite()
    
    print(f"Total tests: {results['total_tests']}")
    print(f"Successful: {results['successful_tests']}")
    print(f"Failed: {results['failed_tests']}")
    print(f"Results file: {results['results_file']}")
    print(f"Assessment file: {results['assessment_file']}")

asyncio.run(main())
```

### Running with Sample Data

```bash
cd tests/scripts
python run_tool_calling_test.py
```

## Test Scenarios

### 1. Mavenir RAN Config Context Chain
Tests the agent's ability to:
- Ask for vendor when not specified
- Call `fetch_ran_config` with correct parameters
- Retain context across follow-up questions

### 2. DISH GPL Parameter Context Chain
Tests the agent's ability to:
- Handle GPL parameter queries
- Call `fetch_gpl_values` with correct vendor context
- Maintain context for related parameter queries

### 3. Vendor Switching Test
Tests the agent's ability to:
- Switch between different vendors in the same conversation
- Call appropriate tools for each vendor
- Handle explicit vendor specifications

### 4. Context Retention with Follow-ups
Tests the agent's ability to:
- Maintain context for follow-up questions
- Switch between different tool types
- Handle complex multi-step queries

### 5. Complex Multi-Vendor Context Switch
Tests the agent's ability to:
- Handle implicit vendor detection
- Switch between RAN config and GPL tools
- Maintain context across different query types

## Tool Validation

The utility validates:

1. **Tool Call Accuracy**: Checks if the expected tool was called
2. **Parameter Validation**: Validates tool parameters match expectations
3. **Context Retention**: Ensures context is maintained across conversation steps
4. **Vendor Switching**: Validates vendor context changes appropriately

## Output Files

The utility generates:

1. **Test Results File**: `tool_calling_test_results_YYYYMMDD_HHMMSS.txt`
   - Detailed test results
   - Success/failure statistics
   - Parameter validation details
   - Execution times

2. **Assessment Report File**: `tool_calling_assessment_report_YYYYMMDD_HHMMSS.txt`
   - LLM-generated assessment of test results
   - PASS/FAIL evaluation for each test
   - Summary of what worked well and issues found
   - Recommendations for improvement

3. **Console Output**: Real-time test progress and summary

## Customizing for Different Agents

To use this utility with a different agent:

1. **Update Agent Initializer**:
   ```python
   async def custom_agent_initializer():
       # Initialize your custom agent
       return await initialize_your_agent()
   ```

2. **Create Custom Test Scenarios**:
   - Define your agent's tools and expected parameters
   - Create CSV file with appropriate test cases
   - Update tool names and parameters as needed

3. **Adjust Tool Call Extraction** (if needed):
   - Modify `extract_actual_tool_calls()` method if your agent uses different response format
   - Update parameter validation logic if needed

## Example Test Scenario

```csv
scenario,step,user_question,expected_tool_call,tool_params,agent_response,description
Vendor Query,1,What is the current tilt value for site HOHOU00036B?,NO_TOOL_CALL,,Agent should ask for vendor specification,Test agent asking for vendor when not specified
Vendor Query,2,Mavenir,fetch_ran_config,vendor should be mavenir, parameter should be tilt, site should be HOHOU00036B,Agent should call fetch_ran_config with Mavenir vendor and site parameters,Test fetch_ran_config tool call with vendor context
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure project root is in Python path
2. **Agent Initialization**: Check that agent initializer returns correct agent type
3. **Tool Call Extraction**: Verify agent response format matches expected structure
4. **Parameter Validation**: Ensure tool parameters are in correct JSON format

### Debug Mode

Enable detailed logging by setting log level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

To add new test scenarios:

1. Add new rows to the CSV file
2. Follow the established format
3. Test with the utility
4. Update documentation if needed

## Dependencies

- `pandas`: For CSV handling
- `asyncio`: For async operations
- `langchain_core`: For message handling
- Agent-specific dependencies (e.g., RAN Config QA Agent) 