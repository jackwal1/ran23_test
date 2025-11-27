import csv
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Awaitable
import pandas as pd

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

class AgentTestUtility:
    def __init__(self,
                 csv_file_path: str,
                 agent_initializer: Optional[Callable[[], Awaitable[Any]]] = None,
                 llm_model: Any = None,
                 output_dir: str = "../results"):
        """
        Initialize the generic agent test utility.
        
        Args:
            csv_file_path: Path to the CSV file containing test scenarios
            agent_initializer: Function that initializes and returns the agent to test
            llm_model: LLM model to use for assessment (optional)
            output_dir: Directory to save test results
        """
        self.csv_file_path = csv_file_path
        self.agent_initializer = agent_initializer
        self.llm = llm_model
        self.output_dir = output_dir
        self.results = []

        # Generate a unique thread ID for the entire test run
        self.thread_id = f"test_run_{int(time.time())}"

        logger.info(f"Agent initializer provided: {agent_initializer is not None}")
        logger.info(f"LLM initialized: {self.llm is not None}")
        logger.info(f"Test run thread_id: {self.thread_id}")
        if self.llm:
            logger.info(f"LLM type: {type(self.llm)}")
        else:
            logger.warning("LLM not available for assessment")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    def read_scenarios(self) -> List[Dict[str, str]]:
        """
        Read test scenarios from CSV file.
        
        Returns:
            List of scenario dictionaries
        """
        scenarios = []
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    scenarios.append({
                        'scenario_name': row.get('scenario_name', ''),
                        'user_input': row.get('user_input', ''),
                        'expected_response': row.get('expected_response', ''),
                        'description': row.get('description', '')
                    })
            logger.info(f"Loaded {len(scenarios)} scenarios from {self.csv_file_path}")
            return scenarios
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            return []

    async def execute_scenario(self, scenario: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute a single test scenario.
        
        Args:
            scenario: Dictionary containing scenario details
            
        Returns:
            Dictionary with test results
        """
        try:
            logger.info(f"Executing scenario: {scenario['scenario_name']}")

            # Execute the query using the provided agent
            start_time = time.time()

            if not self.agent_initializer:
                response_content = "Agent initializer not provided"
            else:
                try:
                    # Initialize the agent
                    agent = await self.agent_initializer()

                    # Execute the query - this is a generic approach
                    # The agent should accept a user input and return a response
                    if hasattr(agent, 'ainvoke'):
                        # LangGraph style agent
                        config = {"configurable": {"thread_id": self.thread_id}}
                        result = await agent.ainvoke(
                            {"messages": [{"role": "user", "content": scenario['user_input']}]},
                            config
                        )
                        if result.get("messages"):
                            last_message = result["messages"][-1]
                            response_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                        else:
                            response_content = "No messages in response"
                    elif hasattr(agent, 'invoke'):
                        # LangChain style agent
                        result = await agent.ainvoke({"input": scenario['user_input']})
                        response_content = result.get("output", str(result))
                    elif callable(agent):
                        # Function-style agent
                        response_content = await agent(scenario['user_input'])
                    else:
                        response_content = f"Unknown agent type: {type(agent)}"

                except Exception as e:
                    response_content = f"Agent execution error: {str(e)}"

            execution_time = time.time() - start_time

            result = {
                'scenario_name': scenario['scenario_name'],
                'user_input': scenario['user_input'],
                'expected_response': scenario['expected_response'],
                'actual_response': response_content,
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat(),
                'status': 'executed'
            }

            logger.info(f"Scenario {scenario['scenario_name']} executed successfully in {execution_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Error executing scenario {scenario['scenario_name']}: {e}")
            return {
                'scenario_name': scenario['scenario_name'],
                'user_input': scenario['user_input'],
                'expected_response': scenario['expected_response'],
                'actual_response': f"Error: {str(e)}",
                'execution_time': 0,
                'timestamp': datetime.now().isoformat(),
                'status': 'error'
            }

    async def run_conversation_flow(self) -> List[Dict[str, Any]]:
        """
        Run test scenarios as a conversation flow, maintaining context between messages.
        
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

        # Group scenarios by scenario_name to handle conversation flows
        conversation_groups = {}
        for scenario in scenarios:
            scenario_name = scenario['scenario_name']
            if scenario_name not in conversation_groups:
                conversation_groups[scenario_name] = []
            conversation_groups[scenario_name].append(scenario)

        results = []

        for conversation_name, conversation_scenarios in conversation_groups.items():
            logger.info(f"Running conversation flow: {conversation_name}")

            # Initialize agent for this conversation
            agent = await self.agent_initializer()

            conversation_results = []

            for i, scenario in enumerate(conversation_scenarios):
                logger.info(f"  Step {i+1}/{len(conversation_scenarios)}: {scenario['user_input'][:50]}...")

                start_time = time.time()

                try:
                    # Execute the query in the conversation context
                    if hasattr(agent, 'ainvoke'):
                        # LangGraph style agent
                        config = {"configurable": {"thread_id": self.thread_id}}
                        result = await agent.ainvoke(
                            {"messages": [{"role": "user", "content": scenario['user_input']}]},
                            config
                        )
                        if result.get("messages"):
                            last_message = result["messages"][-1]
                            response_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                        else:
                            response_content = "No messages in response"
                    elif hasattr(agent, 'invoke'):
                        # LangChain style agent
                        result = await agent.ainvoke({"input": scenario['user_input']})
                        response_content = result.get("output", str(result))
                    elif callable(agent):
                        # Function-style agent
                        response_content = await agent(scenario['user_input'])
                    else:
                        response_content = f"Unknown agent type: {type(agent)}"

                    execution_time = time.time() - start_time

                    result_data = {
                        'scenario_name': scenario['scenario_name'],
                        'conversation_step': i + 1,
                        'user_input': scenario['user_input'],
                        'expected_response': scenario['expected_response'],
                        'actual_response': response_content,
                        'execution_time': execution_time,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'executed'
                    }

                    conversation_results.append(result_data)
                    logger.info(f"  Step {i+1} completed in {execution_time:.2f}s")

                except Exception as e:
                    logger.error(f"Error executing step {i+1}: {e}")
                    result_data = {
                        'scenario_name': scenario['scenario_name'],
                        'conversation_step': i + 1,
                        'user_input': scenario['user_input'],
                        'expected_response': scenario['expected_response'],
                        'actual_response': f"Error: {str(e)}",
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
        Run all test scenarios and collect results.
        
        Returns:
            List of test results
        """
        # Use the new conversation flow method
        return await self.run_conversation_flow()

    def save_results(self, results: List[Dict[str, Any]]) -> str:
        """
        Save test results to a nicely formatted text file.
        
        Args:
            results: List of test results
            
        Returns:
            Path to the saved results file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agent_test_results_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)

        # Calculate summary statistics
        total_tests = len(results)
        passed_tests = len([r for r in results if r['status'] == 'executed'])
        failed_tests = len([r for r in results if r['status'] == 'error'])

        # Group results by conversation
        conversation_groups = {}
        for result in results:
            scenario_name = result['scenario_name']
            if scenario_name not in conversation_groups:
                conversation_groups[scenario_name] = []
            conversation_groups[scenario_name].append(result)

        with open(filepath, 'w', encoding='utf-8') as f:
            # Write comprehensive header with all scenarios summary
            f.write("=" * 80 + "\n")
            f.write("AGENT TEST RESULTS REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Test Steps: {total_tests}\n")
            f.write(f"Total Scenarios: {len(conversation_groups)}\n")
            f.write(f"Overall Passed: {passed_tests}\n")
            f.write(f"Overall Failed: {failed_tests}\n")
            f.write(f"Overall Success Rate: {(passed_tests/total_tests*100):.1f}%\n")
            f.write("=" * 80 + "\n\n")

            # Write scenario-by-scenario summary
            f.write("SCENARIO SUMMARY\n")
            f.write("-" * 40 + "\n")
            for scenario_name, conversation_results in conversation_groups.items():
                scenario_passed = len([r for r in conversation_results if r['status'] == 'executed'])
                scenario_failed = len([r for r in conversation_results if r['status'] == 'error'])
                scenario_total = len(conversation_results)
                scenario_success_rate = (scenario_passed/scenario_total*100) if scenario_total > 0 else 0

                f.write(f"📋 {scenario_name}:\n")
                f.write(f"   Steps: {scenario_total} | Passed: {scenario_passed} | Failed: {scenario_failed} | Success Rate: {scenario_success_rate:.1f}%\n")
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
                scenario_failed = len([r for r in conversation_results if r['status'] == 'error'])
                scenario_total = len(conversation_results)
                scenario_success_rate = (scenario_passed/scenario_total*100) if scenario_total > 0 else 0

                f.write(f"Scenario Summary: {scenario_passed}/{scenario_total} steps passed ({scenario_success_rate:.1f}%)\n")
                f.write(f"Description: {conversation_results[0].get('description', 'No description')}\n\n")

                for i, result in enumerate(conversation_results, 1):
                    # Determine PASS/FAIL status
                    status = "PASS" if result['status'] == 'executed' else "FAIL"

                    f.write(f"Step {i}:\n")
                    f.write(f"  Status: {status}\n")
                    f.write(f"  User Input: {result['user_input']}\n")
                    f.write(f"  Expected: {result['expected_response']}\n")
                    f.write(f"  Actual Response: {result['actual_response']}\n")
                    f.write(f"  Execution Time: {result['execution_time']:.2f}s\n")
                    f.write(f"  Timestamp: {result['timestamp']}\n")

                    if result['status'] == 'error':
                        f.write(f"  Error Details: {result['actual_response']}\n")

                    f.write("\n")

                f.write("-" * 60 + "\n\n")

            # Write final summary
            f.write("=" * 80 + "\n")
            f.write("FINAL SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"Total Scenarios: {len(conversation_groups)}\n")
            f.write(f"Total Test Steps: {total_tests}\n")
            f.write(f"Overall Passed Steps: {passed_tests}\n")
            f.write(f"Overall Failed Steps: {failed_tests}\n")
            f.write(f"Overall Success Rate: {(passed_tests/total_tests*100):.1f}%\n")

            if failed_tests > 0:
                f.write("\nFailed Tests:\n")
                for result in results:
                    if result['status'] == 'error':
                        f.write(f"  - {result['scenario_name']} (Step {result.get('conversation_step', 'N/A')}): {result['actual_response']}\n")

        logger.info(f"Results saved to {filepath}")
        return filepath

    def generate_assessment_prompt(self, results: List[Dict[str, Any]]) -> str:
        """
        Generate a prompt for LLM assessment of test results.
        
        Args:
            results: List of test results
            
        Returns:
            Assessment prompt for LLM
        """

        prompt = """
        You are an expert QA tester evaluating the performance of an AI agent. Please assess the following test results and provide a comprehensive report.

        For each test scenario, evaluate:
        1. Did the agent provide a relevant response to the user's query?
        2. Does the response match the expected behavior described in the expected_response?
        3. Is the response accurate and helpful?

        Test Results:
        """

        for i, result in enumerate(results, 1):
            prompt += f"""
            Test {i}: {result['scenario_name']}
            User Input: {result['user_input']}
            Expected Response: {result['expected_response']}
            Actual Response: {result['actual_response']}
            Execution Time: {result['execution_time']:.2f}s
            Status: {result['status']}
            """

        prompt += """
            Please provide a detailed assessment including:
            1. Overall pass/fail rate
            2. Summary of what worked well
            3. Summary of issues found
            4. Recommendations for improvement
            5. Individual test results (PASS/FAIL with brief explanation)

            Format your response as a structured report with clear sections.
            """

        return prompt

    def assess_results_with_llm(self, results: List[Dict[str, Any]]) -> str:
        """
        Use LLM to assess test results and generate a report.
        
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

    def save_assessment_report(self, assessment: str) -> str:
        """
        Save the LLM assessment report to a file.
        
        Args:
            assessment: Assessment report from LLM
            
        Returns:
            Path to the saved assessment file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agent_assessment_report_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Agent Test Assessment Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*50}\n\n")
            f.write(assessment)

        logger.info(f"Assessment report saved to {filepath}")
        return filepath

    async def run_complete_test_suite(self) -> Dict[str, Any]:
        """
        Run the complete test suite: execute tests and save results.
        
        Returns:
            Dictionary with path to results file and summary statistics
        """
        logger.info("Starting complete test suite execution")

        # Run all tests
        results = await self.run_all_tests()

        if not results:
            logger.error("No test results to process")
            return {}

        # Save results to formatted text file
        results_file = self.save_results(results)

        logger.info("Test suite execution completed")

        return {
            'results_file': results_file,
            'total_tests': len(results),
            'successful_tests': len([r for r in results if r['status'] == 'executed']),
            'failed_tests': len([r for r in results if r['status'] == 'error'])
        }


def create_sample_csv():
    """
    Create a sample CSV file with test scenarios.
    """
    sample_data = [
        {
            'scenario_name': 'Basic RAN Configuration Query',
            'user_input': 'What is the A3 time to trigger parameter for Nokia?',
            'expected_response': 'The agent should provide the A3 time to trigger parameter value for Nokia vendor, typically around 480ms.',
            'description': 'Test basic vendor-specific parameter query'
        },
        {
            'scenario_name': 'Multi-Vendor Comparison',
            'user_input': 'Compare A3 offset values between Nokia and Ericsson',
            'expected_response': 'The agent should provide A3 offset values for both Nokia and Ericsson vendors, showing the differences.',
            'description': 'Test multi-vendor parameter comparison'
        },
        {
            'scenario_name': 'Invalid Parameter Query',
            'user_input': 'What is the XYZ parameter for Samsung?',
            'expected_response': 'The agent should handle the invalid parameter gracefully and provide an appropriate error message or suggest valid parameters.',
            'description': 'Test error handling for invalid parameters'
        },
        {
            'scenario_name': 'Timer Configuration Query',
            'user_input': 'What is the t300 timer value for Ericsson?',
            'expected_response': 'The agent should provide the t300 timer value for Ericsson vendor, typically around 1000ms.',
            'description': 'Test timer parameter query'
        },
        {
            'scenario_name': 'DISH Recommended Values',
            'user_input': 'What are the DISH recommended values for A3 time to trigger?',
            'expected_response': 'The agent should provide DISH recommended values for A3 time to trigger parameter.',
            'description': 'Test DISH recommended values query'
        }
    ]

    csv_file = "../data/sample_test_scenarios.csv"
    os.makedirs(os.path.dirname(csv_file), exist_ok=True)

    with open(csv_file, 'w', newline='', encoding='utf-8') as file:
        fieldnames = ['scenario_name', 'user_input', 'expected_response', 'description']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sample_data)

    print(f"Sample CSV file created: {csv_file}")
    return csv_file


if __name__ == "__main__":
    import asyncio

    async def main():
        # Create sample CSV if it doesn't exist
        # csv_file = "../data/sample_test_scenarios.csv"
        csv_file = "..\\data\\sample_test_scenarios.csv"
        if not os.path.exists(csv_file):
            csv_file = create_sample_csv()

        # Initialize and run the test utility
        test_utility = AgentTestUtility(csv_file)

        # Run complete test suite
        results = await test_utility.run_complete_test_suite()

        print("\n" + "="*50)
        print("TEST SUITE EXECUTION COMPLETED")
        print("="*50)
        print(f"Total tests: {results.get('total_tests', 0)}")
        print(f"Successful: {results.get('successful_tests', 0)}")
        print(f"Failed: {results.get('failed_tests', 0)}")
        print(f"Results file: {results.get('results_file', 'N/A')}")
        print(f"Assessment file: {results.get('assessment_file', 'N/A')}")
        print("="*50)

    # Run the async main function
    asyncio.run(main()) 