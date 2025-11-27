import csv
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Awaitable
import pandas as pd
from langchain_core.messages import HumanMessage

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)
print(f"Added project root to path: {project_root}")

# Import utilities - these may need to be adjusted based on actual module structure
try:
    from utils.logger import get_logger
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger(__name__)

class ToolCallingTestUtility:
    def __init__(self, 
                 csv_file_path: str, 
                 agent_initializer: Optional[Callable[[], Awaitable[Any]]] = None,
                 llm_model: Any = None,
                 output_dir: str = "../results"):
        """
        Initialize the tool calling test utility.
        
        Args:
            csv_file_path: Path to the CSV file containing tool calling test scenarios
            agent_initializer: Function that initializes and returns the agent to test
            output_dir: Directory to save test results
        """
        self.csv_file_path = csv_file_path
        self.agent_initializer = agent_initializer
        self.llm = llm_model
        self.output_dir = output_dir
        self.results = []
        
        # Generate a unique thread ID for the entire test run
        self.thread_id = f"tool_test_run_{int(time.time())}"
        
        logger.info(f"Agent initializer provided: {agent_initializer is not None}")
        logger.info(f"LLM initialized: {self.llm is not None}")
        logger.info(f"Tool calling test run thread_id: {self.thread_id}")
        if self.llm:
            logger.info(f"LLM type: {type(self.llm)}")
        else:
            logger.warning("LLM not available for assessment")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    def read_scenarios(self) -> List[Dict[str, str]]:
        """
        Read tool calling test scenarios from CSV file.
        
        Expected CSV columns:
        - scenario: Name of the test scenario
        - step: Step number within the scenario
        - user_question: The user's input/question
        - expected_tool_call: Expected tool name to be called (or "NO_TOOL_CALL")
        - tool_params: Expected tool parameters (JSON string or description)
        - agent_response: Expected agent response description
        - description: Additional description of the test case
        
        Returns:
            List of scenario dictionaries
        """
        scenarios = []
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    scenarios.append({
                        'scenario': row.get('scenario', ''),
                        'step': int(row.get('step', 1)),
                        'user_question': row.get('user_question', ''),
                        'expected_tool_call': row.get('expected_tool_call', ''),
                        'tool_params': row.get('tool_params', ''),
                        'agent_response': row.get('agent_response', ''),
                        'description': row.get('description', '')
                    })
            logger.info(f"Loaded {len(scenarios)} tool calling scenarios from {self.csv_file_path}")
            return scenarios
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            return []
    
    def parse_tool_params(self, tool_params_str: str) -> Dict[str, Any]:
        """
        Parse tool parameters from human-friendly description.
        
        Args:
            tool_params_str: String containing tool parameters in human-friendly format
            
        Returns:
            Dictionary of expected tool parameters
        """
        if not tool_params_str or tool_params_str.strip() == '':
            return {}
        
        # Parse human-friendly parameter descriptions
        params = {}
        
        # Split by common separators and process each part
        parts = tool_params_str.replace(';', ',').replace(' and ', ',').split(',')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Look for key-value patterns
            if 'should be' in part.lower():
                # Format: "vendor should be mavenir"
                key_value = part.lower().split('should be')
                if len(key_value) == 2:
                    key = key_value[0].strip()
                    value = key_value[1].strip()
                    params[key] = value
            elif '=' in part:
                # Format: "vendor=mavenir"
                key_value = part.split('=', 1)
                if len(key_value) == 2:
                    key = key_value[0].strip()
                    value = key_value[1].strip().strip('"\'')
                    params[key] = value
            elif ':' in part:
                # Format: "vendor: mavenir"
                key_value = part.split(':', 1)
                if len(key_value) == 2:
                    key = key_value[0].strip()
                    value = key_value[1].strip().strip('"\'')
                    params[key] = value
            else:
                # Single value or description
                if 'vendor' in part.lower():
                    # Extract vendor name
                    vendor_keywords = ['mavenir', 'samsung', 'dish', 'ericsson', 'nokia']
                    for vendor in vendor_keywords:
                        if vendor in part.lower():
                            params['vendor'] = vendor
                            break
                elif 'parameter' in part.lower() or 'param' in part.lower():
                    # Extract parameter name
                    # Look for common parameter patterns
                    param_keywords = ['tilt', 'operational_state', 'administrative_state', 'rru_alarms', 'ret_tilt', 
                                   'preambleReceivedTargetPwr', 'Event A3 - Report Interval', 'qHyst', 'ACME_features',
                                   'MaxAnrTimerDuration', 'puschP0NominalWithoutGrant', 'cell_parameters', 'pdcch1SymbEnable']
                    for param in param_keywords:
                        if param.lower() in part.lower():
                            params['parameter'] = param
                            break
                elif 'site' in part.lower():
                    # Extract site information
                    if 'HOHOU00036B' in part:
                        params['site'] = 'HOHOU00036B'
                elif 'cucp' in part.lower():
                    # Extract CUCP information
                    cucp_patterns = ['JKRLA627035000', 'LSSNA741025000']
                    for cucp in cucp_patterns:
                        if cucp in part:
                            params['cucp'] = cucp
                            break
                elif 'du' in part.lower():
                    # Extract DU information
                    du_patterns = ['741025022']
                    for du in du_patterns:
                        if du in part:
                            params['du'] = du
                            break
                elif 'cell_identity' in part.lower() or 'cell-identity' in part.lower():
                    # Extract cell identity
                    if '541' in part:
                        params['cell_identity'] = '541'
                elif 'area' in part.lower():
                    if 'same' in part.lower():
                        params['area'] = 'same'
                elif 'check_optimal' in part.lower() or 'optimal' in part.lower():
                    params['check_optimal'] = True
                elif 'impact_analysis' in part.lower() or 'impact' in part.lower():
                    params['impact_analysis'] = True
                elif 'general' in part.lower():
                    params['parameter'] = 'general'
        
        return params
    
    def extract_actual_tool_calls(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract actual tool calls from the agent response.
        
        Args:
            result: Agent response result
            
        Returns:
            List of actual tool calls with their parameters
        """
        tool_calls = []
        
        if "messages" in result:
            # Only look at the last message (current step's response)
            messages = result["messages"]
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    for tool_call in last_message.tool_calls:
                        tool_calls.append({
                            "name": tool_call.get("name", ""),
                            "args": tool_call.get("args", {}),
                            "id": tool_call.get("id", "")
                        })
        
        return tool_calls
    
    def validate_tool_call(self, expected_tool: str, expected_params: Dict[str, Any], 
                          actual_tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate if the expected tool was called with correct parameters.
        
        Args:
            expected_tool: Expected tool name
            expected_params: Expected tool parameters
            actual_tool_calls: List of actual tool calls
            
        Returns:
            Validation result dictionary
        """
        if expected_tool == "NO_TOOL_CALL":
            if not actual_tool_calls:
                return {
                    "valid": True,
                    "message": "No tool call expected and none made",
                    "actual_tool": None,
                    "actual_params": None
                }
            else:
                return {
                    "valid": False,
                    "message": f"Expected no tool call but got: {[tc['name'] for tc in actual_tool_calls]}",
                    "actual_tool": [tc['name'] for tc in actual_tool_calls],
                    "actual_params": [tc['args'] for tc in actual_tool_calls]
                }
        
        if not actual_tool_calls:
            return {
                "valid": False,
                "message": f"Expected tool '{expected_tool}' but no tool was called",
                "actual_tool": None,
                "actual_params": None
            }
        
        # Check if expected tool was called
        matching_tools = [tc for tc in actual_tool_calls if tc['name'] == expected_tool]
        
        if not matching_tools:
            return {
                "valid": False,
                "message": f"Expected tool '{expected_tool}' but got: {[tc['name'] for tc in actual_tool_calls]}",
                "actual_tool": [tc['name'] for tc in actual_tool_calls],
                "actual_params": [tc['args'] for tc in actual_tool_calls]
            }
        
        # Check parameters for the matching tool
        tool_call = matching_tools[0]
        actual_params = tool_call['args']
        
        # Simple parameter validation - check if expected keys exist
        param_validation = {}
        missing_params = []
        
        for key, expected_value in expected_params.items():
            if key in actual_params:
                if isinstance(expected_value, dict) and isinstance(actual_params[key], dict):
                    # Nested parameter validation
                    nested_validation = self.validate_tool_call("", expected_value, [{"args": actual_params[key]}])
                    param_validation[key] = nested_validation["valid"]
                else:
                    param_validation[key] = actual_params[key] == expected_value
            else:
                missing_params.append(key)
                param_validation[key] = False
        
        all_params_valid = all(param_validation.values()) and not missing_params
        
        return {
            "valid": all_params_valid,
            "message": f"Tool '{expected_tool}' called with {'correct' if all_params_valid else 'incorrect'} parameters",
            "actual_tool": expected_tool,
            "actual_params": actual_params,
            "expected_params": expected_params,
            "param_validation": param_validation,
            "missing_params": missing_params
        }
    
    async def execute_tool_test(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single tool calling test scenario.
        
        Args:
            scenario: Dictionary containing scenario details
            
        Returns:
            Dictionary with test results
        """
        try:
            logger.info(f"Executing tool test: {scenario['scenario']} - Step {scenario['step']}")
            
            # Execute the query using the provided agent
            start_time = time.time()
            
            if not self.agent_initializer:
                response_content = "Agent initializer not provided"
                actual_tool_calls = []
            else:
                try:
                    # Initialize the agent
                    agent = await self.agent_initializer()
                    
                    # Execute the query
                    if hasattr(agent, 'ainvoke'):
                        # LangGraph style agent
                        config = {"configurable": {"thread_id": self.thread_id}}
                        result = await agent.ainvoke(
                            {"messages": [HumanMessage(content=scenario['user_question'])]},
                            config
                        )
                        
                        # Extract response content
                        if result.get("messages"):
                            last_message = result["messages"][-1]
                            response_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                        else:
                            response_content = "No messages in response"
                        
                        # Extract tool calls
                        actual_tool_calls = self.extract_actual_tool_calls(result)
                        
                    elif hasattr(agent, 'invoke'):
                        # LangChain style agent
                        result = await agent.ainvoke({"input": scenario['user_question']})
                        response_content = result.get("output", str(result))
                        actual_tool_calls = self.extract_actual_tool_calls(result)
                        
                    elif callable(agent):
                        # Function-style agent
                        response_content = await agent(scenario['user_question'])
                        actual_tool_calls = []
                    else:
                        response_content = f"Unknown agent type: {type(agent)}"
                        actual_tool_calls = []
                        
                except Exception as e:
                    response_content = f"Agent execution error: {str(e)}"
                    actual_tool_calls = []
            
            execution_time = time.time() - start_time
            
            # Parse expected tool parameters
            expected_params = self.parse_tool_params(scenario['tool_params'])
            
            # Validate tool call
            validation_result = self.validate_tool_call(
                scenario['expected_tool_call'],
                expected_params,
                actual_tool_calls
            )
            
            result = {
                'scenario': scenario['scenario'],
                'step': scenario['step'],
                'user_question': scenario['user_question'],
                'expected_tool_call': scenario['expected_tool_call'],
                'tool_params': scenario['tool_params'],
                'expected_tool_params': expected_params,
                'actual_tool_calls': actual_tool_calls,
                'validation_result': validation_result,
                'agent_response': response_content,
                'expected_agent_response': scenario['agent_response'],
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat(),
                'status': 'executed' if validation_result['valid'] else 'failed'
            }
            
            logger.info(f"Tool test {scenario['scenario']} - Step {scenario['step']} executed successfully in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool test {scenario['scenario']} - Step {scenario['step']}: {e}")
            return {
                'scenario': scenario['scenario'],
                'step': scenario['step'],
                'user_question': scenario['user_question'],
                'expected_tool_call': scenario['expected_tool_call'],
                'expected_tool_params': {},
                'actual_tool_calls': [],
                'validation_result': {
                    'valid': False,
                    'message': f"Error: {str(e)}",
                    'actual_tool': None,
                    'actual_params': None
                },
                'agent_response': f"Error: {str(e)}",
                'expected_agent_response': scenario['agent_response'],
                'execution_time': 0,
                'timestamp': datetime.now().isoformat(),
                'status': 'error'
            }
    
    async def run_conversation_flow(self) -> List[Dict[str, Any]]:
        """
        Run tool calling test scenarios as a conversation flow, maintaining context between messages.
        
        Returns:
            List of test results
        """
        scenarios = self.read_scenarios()
        if not scenarios:
            logger.error("No scenarios found to execute")
            return []
        
        if not self.agent_initializer:
            logger.error("Agent initializer not provided")
            return []
        
        # Group scenarios by scenario name to handle conversation flows
        conversation_groups = {}
        for scenario in scenarios:
            scenario_name = scenario['scenario']
            if scenario_name not in conversation_groups:
                conversation_groups[scenario_name] = []
            conversation_groups[scenario_name].append(scenario)
        
        # Sort each group by step number
        for scenario_name in conversation_groups:
            conversation_groups[scenario_name].sort(key=lambda x: x['step'])
        
        results = []
        
        for conversation_name, conversation_scenarios in conversation_groups.items():
            logger.info(f"Running tool calling conversation flow: {conversation_name}")
            
            # Initialize agent for this conversation
            agent = await self.agent_initializer()
            
            # Track conversation state for this conversation
            conversation_messages = []
            seen_tool_call_ids = set()
            
            conversation_results = []
            
            for i, scenario in enumerate(conversation_scenarios):
                logger.info(f"  Step {scenario['step']}: {scenario['user_question'][:50]}...")
                
                start_time = time.time()
                
                try:
                    # Add the current user message to conversation history
                    conversation_messages.append(HumanMessage(content=scenario['user_question']))
                    
                    # Execute the query in the conversation context
                    if hasattr(agent, 'ainvoke'):
                        # LangGraph style agent
                        config = {"configurable": {"thread_id": f"{self.thread_id}_{conversation_name}"}}
                        result = await agent.ainvoke(
                            {"messages": conversation_messages},
                            config
                        )
                        
                        # Extract response content from the last message
                        if result.get("messages"):
                            last_message = result["messages"][-1]
                            response_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                        else:
                            response_content = "No messages in response"
                        
                        # Extract tool calls from all messages, but only include new ones for this step
                        actual_tool_calls = []
                        if result.get("messages"):
                            for msg in result["messages"]:
                                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                    for tool_call in msg.tool_calls:
                                        tool_call_id = tool_call.get("id", "")
                                        if tool_call_id and tool_call_id not in seen_tool_call_ids:
                                            actual_tool_calls.append({
                                                "name": tool_call.get("name", ""),
                                                "args": tool_call.get("args", {}),
                                                "id": tool_call_id
                                            })
                                            seen_tool_call_ids.add(tool_call_id)
                        
                        # Update conversation history with the agent's response
                        if result.get("messages"):
                            conversation_messages = result["messages"]
                        
                    elif hasattr(agent, 'invoke'):
                        # LangChain style agent
                        result = await agent.ainvoke({"input": scenario['user_question']})
                        response_content = result.get("output", str(result))
                        actual_tool_calls = self.extract_actual_tool_calls(result)
                        
                    elif callable(agent):
                        # Function-style agent
                        response_content = await agent(scenario['user_question'])
                        actual_tool_calls = []
                    else:
                        response_content = f"Unknown agent type: {type(agent)}"
                        actual_tool_calls = []
                    
                    execution_time = time.time() - start_time
                    
                    # Parse expected tool parameters
                    expected_params = self.parse_tool_params(scenario['tool_params'])
                    
                    # Validate tool call
                    validation_result = self.validate_tool_call(
                        scenario['expected_tool_call'],
                        expected_params,
                        actual_tool_calls
                    )
                    
                    result_data = {
                        'scenario': scenario['scenario'],
                        'step': scenario['step'],
                        'conversation_step': i + 1,
                        'user_question': scenario['user_question'],
                        'expected_tool_call': scenario['expected_tool_call'],
                        'tool_params': scenario['tool_params'],
                        'expected_tool_params': expected_params,
                        'actual_tool_calls': actual_tool_calls,
                        'validation_result': validation_result,
                        'agent_response': response_content,
                        'expected_agent_response': scenario['agent_response'],
                        'execution_time': execution_time,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'executed' if validation_result['valid'] else 'failed'
                    }
                    
                    conversation_results.append(result_data)
                    logger.info(f"  Step {scenario['step']} completed in {execution_time:.2f}s")
                    
                except Exception as e:
                    logger.error(f"Error executing step {scenario['step']}: {e}")
                    result_data = {
                        'scenario': scenario['scenario'],
                        'step': scenario['step'],
                        'conversation_step': i + 1,
                        'user_question': scenario['user_question'],
                        'expected_tool_call': scenario['expected_tool_call'],
                        'expected_tool_params': {},
                        'actual_tool_calls': [],
                        'validation_result': {
                            'valid': False,
                            'message': f"Error: {str(e)}",
                            'actual_tool': None,
                            'actual_params': None
                        },
                        'agent_response': f"Error: {str(e)}",
                        'expected_agent_response': scenario['agent_response'],
                        'execution_time': 0,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error'
                    }
                    conversation_results.append(result_data)
                
                # Small delay between conversation steps
                time.sleep(0.5)
            results.extend(conversation_results)
        
        self.results = results
        return results
    
    async def run_all_tests(self) -> List[Dict[str, Any]]:
        """
        Run all tool calling test scenarios and collect results.
        
        Returns:
            List of test results
        """
        # Use the conversation flow method
        return await self.run_conversation_flow()
    
    def save_results(self, results: List[Dict[str, Any]], llm_assessment: str = None) -> str:
        """
        Save tool calling test results to a nicely formatted text file with LLM assessment.
        
        Args:
            results: List of test results
            llm_assessment: Optional LLM assessment report
            
        Returns:
            Path to the saved results file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tool_calling_test_results_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        # Calculate summary statistics
        total_tests = len(results)
        passed_tests = len([r for r in results if r['status'] == 'executed'])
        failed_tests = len([r for r in results if r['status'] == 'failed'])
        error_tests = len([r for r in results if r['status'] == 'error'])
        
        # Group results by conversation
        conversation_groups = {}
        for result in results:
            scenario_name = result['scenario']
            if scenario_name not in conversation_groups:
                conversation_groups[scenario_name] = []
            conversation_groups[scenario_name].append(result)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # Write comprehensive header
            f.write("=" * 80 + "\n")
            f.write("TOOL CALLING TEST RESULTS REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Test Steps: {total_tests}\n")
            f.write(f"Total Scenarios: {len(conversation_groups)}\n")
            f.write(f"Overall Passed: {passed_tests}\n")
            f.write(f"Overall Failed: {failed_tests}\n")
            f.write(f"Overall Errors: {error_tests}\n")
            f.write(f"Overall Success Rate: {(passed_tests/total_tests*100):.1f}%\n")
            f.write("=" * 80 + "\n\n")
            
            # Write scenario-by-scenario summary
            f.write("SCENARIO SUMMARY\n")
            f.write("-" * 40 + "\n")
            for scenario_name, conversation_results in conversation_groups.items():
                scenario_passed = len([r for r in conversation_results if r['status'] == 'executed'])
                scenario_failed = len([r for r in conversation_results if r['status'] == 'failed'])
                scenario_error = len([r for r in conversation_results if r['status'] == 'error'])
                scenario_total = len(conversation_results)
                scenario_success_rate = (scenario_passed/scenario_total*100) if scenario_total > 0 else 0
                
                f.write(f"🔧 {scenario_name}:\n")
                f.write(f"   Steps: {scenario_total} | Passed: {scenario_passed} | Failed: {scenario_failed} | Errors: {scenario_error} | Success Rate: {scenario_success_rate:.1f}%\n")
                f.write(f"   Description: {conversation_results[0].get('description', 'No description')}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("DETAILED RESULTS BY SCENARIO\n")
            f.write("=" * 80 + "\n\n")
            
            # Write detailed results for each conversation
            for conversation_name, conversation_results in conversation_groups.items():
                f.write(f"CONVERSATION: {conversation_name}\n")
                f.write("-" * 60 + "\n")
                
                # Calculate scenario-specific stats
                scenario_passed = len([r for r in conversation_results if r['status'] == 'executed'])
                scenario_failed = len([r for r in conversation_results if r['status'] == 'failed'])
                scenario_error = len([r for r in conversation_results if r['status'] == 'error'])
                scenario_total = len(conversation_results)
                scenario_success_rate = (scenario_passed/scenario_total*100) if scenario_total > 0 else 0
                
                f.write(f"Scenario Summary: {scenario_passed}/{scenario_total} steps passed ({scenario_success_rate:.1f}%)\n")
                f.write(f"Description: {conversation_results[0].get('description', 'No description')}\n\n")
                
                for i, result in enumerate(conversation_results, 1):
                    # Determine PASS/FAIL status
                    status = "PASS" if result['status'] == 'executed' else "FAIL" if result['status'] == 'failed' else "ERROR"
                    
                    f.write(f"Step {result['step']}:\n")
                    f.write(f"  Status: {status}\n")
                    f.write(f"  User Question: {result['user_question']}\n")
                    f.write(f"  Expected Tool: {result['expected_tool_call']}\n")
                    f.write(f"  Tool Params (intent): {result.get('tool_params', result.get('expected_tool_params', 'N/A'))}\n")
                    f.write(f"  Actual Tool Calls: {result['actual_tool_calls']}\n")
                    f.write(f"  Validation: {result['validation_result']['message']}\n")
                    f.write(f"  Agent Response: {result['agent_response'][:200]}...\n")
                    f.write(f"  Expected Response: {result['expected_agent_response']}\n")
                    f.write(f"  Execution Time: {result['execution_time']:.2f}s\n")
                    f.write(f"  Timestamp: {result['timestamp']}\n")
                    
                    if result['status'] == 'error':
                        f.write(f"  Error Details: {result['agent_response']}\n")
                    
                    f.write("\n")
                
                f.write("-" * 60 + "\n\n")
            
            # Write LLM Assessment if available
            if llm_assessment:
                f.write("=" * 80 + "\n")
                f.write("LLM ASSESSMENT REPORT\n")
                f.write("=" * 80 + "\n")
                f.write(llm_assessment)
                f.write("\n\n")
            
            # Write final summary
            f.write("=" * 80 + "\n")
            f.write("FINAL SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"Total Scenarios: {len(conversation_groups)}\n")
            f.write(f"Total Test Steps: {total_tests}\n")
            f.write(f"Overall Passed Steps: {passed_tests}\n")
            f.write(f"Overall Failed Steps: {failed_tests}\n")
            f.write(f"Overall Error Steps: {error_tests}\n")
            f.write(f"Overall Success Rate: {(passed_tests/total_tests*100):.1f}%\n")
            
            if failed_tests > 0 or error_tests > 0:
                f.write("\nFailed/Error Tests:\n")
                for result in results:
                    if result['status'] in ['failed', 'error']:
                        f.write(f"  - {result['scenario']} (Step {result['step']}): {result['validation_result']['message']}\n")
        
        logger.info(f"Tool calling test results saved to {filepath}")
        return filepath
    
    def generate_assessment_prompt(self, results: List[Dict[str, Any]]) -> str:
        """
        Generate a prompt for LLM assessment of tool calling test results.
        
        Args:
            results: List of test results
            
        Returns:
            Assessment prompt for LLM
        """
        prompt = """
        You are an expert QA tester evaluating the tool calling capabilities of an AI agent. For each test scenario, you are given:
        - The user question
        - The expected tool to be called
        - The tool parameters described in plain English (not exact JSON)
        - The actual tool call made by the agent (name and arguments)
        
        For each test, answer:
        1. Did the agent call the expected tool?
        2. Do the actual tool call arguments satisfy the intent described in the plain-English tool_params? (Do not require exact string or JSON match. Focus on whether the agent's tool call would achieve the user's intent as described.)
        3. Was the agent response appropriate and helpful?
        
        For each test, output PASS if the actual tool call satisfies the intent of the tool_params and the tool name matches, even if the arguments are not an exact match. Otherwise, output FAIL. Briefly explain your reasoning for each test.
        
        Test Results:
        """
        
        for i, result in enumerate(results, 1):
            prompt += f"""
            Test {i}: {result['scenario']} - Step {result['step']}
            User Question: {result['user_question']}
            Expected Tool: {result['expected_tool_call']}
            Tool Params (intent): {result['tool_params']}
            Actual Tool Calls: {result['actual_tool_calls']}
            Agent Response: {result['agent_response'][:200]}...
            Expected Response: {result['expected_agent_response']}
            Execution Time: {result['execution_time']:.2f}s
            Status: {result['status']}
            """
        
        prompt += """
            Please provide a detailed assessment including:
            1. Overall pass/fail rate for tool calling intent satisfaction
            2. Summary of what worked well (correct tool calls, intent satisfaction)
            3. Summary of issues found (wrong tools, missing intent, context issues)
            4. Recommendations for improvement
            5. Individual test results (PASS/FAIL with brief explanation)

            Format your response as a structured report with clear sections.
            """
        
        return prompt
    
    def assess_results_with_llm(self, results: List[Dict[str, Any]]) -> str:
        """
        Use LLM to assess tool calling test results and generate a report.
        
        Args:
            results: List of test results
            
        Returns:
            Assessment report from LLM
        """
        try:
            prompt = self.generate_assessment_prompt(results)
            
            # Get LLM response
            if self.llm is not None:
                try:
                    response = self.llm.invoke([{"role": "user", "content": prompt}])
                    assessment = response.content if hasattr(response, 'content') else str(response)
                except Exception as e:
                    logger.error(f"Error invoking LLM: {e}")
                    assessment = f"LLM invocation error: {str(e)}"
            else:
                assessment = "LLM not available - manual assessment required"
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error generating LLM assessment: {e}")
            return f"Error generating assessment: {str(e)}"
    
    async def run_complete_test_suite(self) -> Dict[str, Any]:
        """
        Run the complete tool calling test suite: execute tests, save results, and generate LLM assessment.
        
        Returns:
            Dictionary with path to results file and summary statistics
        """
        logger.info("Starting complete tool calling test suite execution")
        
        # Run all tests
        results = await self.run_all_tests()
        
        if not results:
            logger.error("No test results to process")
            return {}
        
        # Generate LLM assessment
        assessment = self.assess_results_with_llm(results)
        
        # Save results to formatted text file with LLM assessment included
        results_file = self.save_results(results, assessment)
        
        logger.info("Tool calling test suite execution completed")
        
        return {
            'results_file': results_file,
            'total_tests': len(results),
            'successful_tests': len([r for r in results if r['status'] == 'executed']),
            'failed_tests': len([r for r in results if r['status'] == 'failed']),
            'error_tests': len([r for r in results if r['status'] == 'error'])
        }


def create_sample_tool_calling_csv():
    """
    Create a sample CSV file with tool calling test scenarios.
    """
    sample_data = [
        {
            'scenario': 'Mavenir RAN Config Context Chain',
            'step': 1,
            'user_question': 'What is the current tilt value for site HOHOU00036B?',
            'expected_tool_call': 'NO_TOOL_CALL',
            'tool_params': '',
            'agent_response': 'Agent should ask for vendor specification',
            'description': 'Test agent asking for vendor when not specified'
        },
        {
            'scenario': 'Mavenir RAN Config Context Chain',
            'step': 2,
            'user_question': 'Mavenir',
            'expected_tool_call': 'fetch_ran_config',
            'tool_params': 'vendor should be mavenir, parameter should be tilt, site should be HOHOU00036B',
            'agent_response': 'Agent should call fetch_ran_config with Mavenir vendor and site parameters',
            'description': 'Test fetch_ran_config tool call with vendor context'
        },
        {
            'scenario': 'Mavenir RAN Config Context Chain',
            'step': 3,
            'user_question': 'What about the operational state of CUCP with name JKRLA627035000?',
            'expected_tool_call': 'fetch_ran_config',
            'tool_params': 'vendor should be mavenir, parameter should be operational_state, cucp should be JKRLA627035000',
            'agent_response': 'Agent should call fetch_ran_config with retained Mavenir context',
            'description': 'Test context retention for follow-up questions'
        },
        {
            'scenario': 'DISH GPL Parameter Context Chain',
            'step': 1,
            'user_question': 'What is the recommended GPL value for the parameter preambleReceivedTargetPwr?',
            'expected_tool_call': 'NO_TOOL_CALL',
            'tool_params': '',
            'agent_response': 'Agent should ask for vendor specification',
            'description': 'Test agent asking for vendor for GPL parameters'
        },
        {
            'scenario': 'DISH GPL Parameter Context Chain',
            'step': 2,
            'user_question': 'DISH',
            'expected_tool_call': 'fetch_gpl_values',
            'tool_params': 'vendor should be dish, parameter should be preambleReceivedTargetPwr',
            'agent_response': 'Agent should call fetch_gpl_values with DISH vendor',
            'description': 'Test fetch_gpl_values tool call with DISH context'
        },
        {
            'scenario': 'DISH GPL Parameter Context Chain',
            'step': 3,
            'user_question': 'What about the Event A3 - Report Interval parameter?',
            'expected_tool_call': 'fetch_gpl_values',
            'tool_params': 'vendor should be dish, parameter should be Event A3 - Report Interval',
            'agent_response': 'Agent should call fetch_gpl_values with retained DISH context',
            'description': 'Test context retention for GPL parameters'
        },
        {
            'scenario': 'Vendor Switching Test',
            'step': 1,
            'user_question': 'What is the current tilt value for site HOHOU00036B?',
            'expected_tool_call': 'NO_TOOL_CALL',
            'tool_params': '',
            'agent_response': 'Agent should ask for vendor specification',
            'description': 'Test initial vendor request'
        },
        {
            'scenario': 'Vendor Switching Test',
            'step': 2,
            'user_question': 'Mavenir',
            'expected_tool_call': 'fetch_ran_config',
            'tool_params': 'vendor should be mavenir, parameter should be tilt, site should be HOHOU00036B',
            'agent_response': 'Agent should call fetch_ran_config with Mavenir vendor',
            'description': 'Test Mavenir RAN config tool call'
        },
        {
            'scenario': 'Vendor Switching Test',
            'step': 3,
            'user_question': 'Now switch to Samsung and tell me about CUCP LSSNA741025000 administrative state',
            'expected_tool_call': 'fetch_ran_config',
            'tool_params': 'vendor should be samsung, parameter should be administrative_state, cucp should be LSSNA741025000',
            'agent_response': 'Agent should call fetch_ran_config with Samsung vendor',
            'description': 'Test vendor switching in same conversation'
        },
        {
            'scenario': 'Vendor Switching Test',
            'step': 4,
            'user_question': 'What about Mavenir\'s recommended value for MaxAnrTimerDuration?',
            'expected_tool_call': 'fetch_gpl_values',
            'tool_params': 'vendor should be mavenir, parameter should be MaxAnrTimerDuration',
            'agent_response': 'Agent should call fetch_gpl_values with Mavenir vendor',
            'description': 'Test switching to GPL parameters with different vendor'
        }
    ]
    
    csv_file = "../data/sample_tool_calling_scenarios.csv"
    os.makedirs(os.path.dirname(csv_file), exist_ok=True)
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as file:
        fieldnames = ['scenario', 'step', 'user_question', 'expected_tool_call', 'tool_params', 'agent_response', 'description']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sample_data)
    
    print(f"Sample tool calling CSV file created: {csv_file}")
    return csv_file


if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Create sample CSV if it doesn't exist
        csv_file = "../data/sample_tool_calling_scenarios.csv"
        if not os.path.exists(csv_file):
            csv_file = create_sample_tool_calling_csv()
        
        # Initialize and run the test utility
        test_utility = ToolCallingTestUtility(csv_file)
        
        # Run complete test suite
        results = await test_utility.run_complete_test_suite()
        
        print("\n" + "="*50)
        print("TOOL CALLING TEST SUITE EXECUTION COMPLETED")
        print("="*50)
        print(f"Total tests: {results.get('total_tests', 0)}")
        print(f"Successful: {results.get('successful_tests', 0)}")
        print(f"Failed: {results.get('failed_tests', 0)}")
        print(f"Errors: {results.get('error_tests', 0)}")
        print(f"Results file: {results.get('results_file', 'N/A')}")
        print("="*50)
    
    # Run the async main function
    asyncio.run(main()) 