#!/usr/bin/env python3
"""
Tool Calling Test Runner

This script demonstrates how to use the ToolCallingTestUtility to test
agent tool calling capabilities with the RAN Config QA Agent.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool_calling_test_utility import ToolCallingTestUtility
from agent.ran_config_qa_agent import initialize_ran_config_qa_agent

# Example LLM model for assessment
def get_assessment_llm():
    """Get the LLM model for assessment."""
    try:
        from llms.llms import chatmodel_mistral_small_3_1_24b_instruct_2503
        return chatmodel_mistral_small_3_1_24b_instruct_2503
    except ImportError as e:
        print(f"❌ Failed to import LLM model: {e}")
        return None


async def run_ran_config_qa_tool_tests():
    """Run tool calling tests for the RAN Config QA Agent."""
    
    print("=" * 80)
    print("🧪 RAN Config QA Agent Tool Calling Tests")
    print("=" * 80)
    
    # Define the agent initializer function
    async def agent_initializer():
        """Initialize the RAN Config QA Agent."""
        print("Initializing RAN Config QA Agent...")
        agent = await initialize_ran_config_qa_agent()
        print("✅ Agent initialized successfully")
        return agent
    
    # Get LLM model for assessment
    llm_model = get_assessment_llm()
    
    # Initialize the test utility
    csv_file = "../data/sample_tool_calling_scenarios.csv"
    test_utility = ToolCallingTestUtility(
        csv_file_path=csv_file,
        agent_initializer=agent_initializer,
        llm_model=llm_model,
        output_dir="../results"
    )
    
    print(f"📁 Using test scenarios from: {csv_file}")
    print(f"📁 Results will be saved to: {test_utility.output_dir}")
    print(f"🤖 LLM Model: {type(llm_model).__name__ if llm_model else 'None'}")
    
    # Run the complete test suite
    print("\n🚀 Starting tool calling test suite...")
    results = await test_utility.run_complete_test_suite()
    
    # Display results summary
    print("\n" + "=" * 80)
    print("📊 TOOL CALLING TEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {results.get('total_tests', 0)}")
    print(f"✅ Successful: {results.get('successful_tests', 0)}")
    print(f"❌ Failed: {results.get('failed_tests', 0)}")
    print(f"💥 Errors: {results.get('error_tests', 0)}")
    
    if results.get('total_tests', 0) > 0:
        success_rate = (results.get('successful_tests', 0) / results.get('total_tests', 0)) * 100
        print(f"📈 Success Rate: {success_rate:.1f}%")
    
    print(f"📄 Detailed Results: {results.get('results_file', 'N/A')}")
    print(f"📊 Assessment Report: {results.get('assessment_file', 'N/A')}")
    print("=" * 80)
    
    return results


async def run_custom_tool_tests():
    """Run tool calling tests with custom scenarios."""
    
    print("\n" + "=" * 80)
    print("🔧 Custom Tool Calling Tests")
    print("=" * 80)
    
    # You can create custom test scenarios here
    custom_scenarios = [
        {
            'scenario': 'Custom Test 1',
            'step': 1,
            'user_question': 'What is the current tilt value for site HOHOU00036B?',
            'expected_tool_call': 'NO_TOOL_CALL',
            'tool_params': '',
            'agent_response': 'Agent should ask for vendor specification',
            'description': 'Custom test for vendor request'
        },
        {
            'scenario': 'Custom Test 1',
            'step': 2,
            'user_question': 'Mavenir',
            'expected_tool_call': 'fetch_ran_config',
            'tool_params': '{"vendor": "mavenir", "parameter": "tilt", "site": "HOHOU00036B"}',
            'agent_response': 'Agent should call fetch_ran_config with Mavenir vendor',
            'description': 'Custom test for fetch_ran_config tool call'
        }
    ]
    
    # Create a temporary CSV file for custom tests
    import csv
    import tempfile
    
    temp_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    fieldnames = ['scenario', 'step', 'user_question', 'expected_tool_call', 'tool_params', 'agent_response', 'description']
    
    with open(temp_csv.name, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(custom_scenarios)
    
    # Define the agent initializer function
    async def agent_initializer():
        """Initialize the RAN Config QA Agent."""
        agent = await initialize_ran_config_qa_agent()
        return agent
    
    # Get LLM model for assessment
    llm_model = get_assessment_llm()
    
    # Initialize the test utility with custom scenarios
    test_utility = ToolCallingTestUtility(
        csv_file_path=temp_csv.name,
        agent_initializer=agent_initializer,
        llm_model=llm_model,
        output_dir="../results"
    )
    
    print(f"📁 Using custom test scenarios from: {temp_csv.name}")
    print(f"🤖 LLM Model: {type(llm_model).__name__ if llm_model else 'None'}")
    
    # Run the custom test suite
    print("\n🚀 Starting custom tool calling test suite...")
    results = await test_utility.run_complete_test_suite()
    
    # Display results summary
    print("\n" + "=" * 80)
    print("📊 CUSTOM TOOL CALLING TEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {results.get('total_tests', 0)}")
    print(f"✅ Successful: {results.get('successful_tests', 0)}")
    print(f"❌ Failed: {results.get('failed_tests', 0)}")
    print(f"💥 Errors: {results.get('error_tests', 0)}")
    
    if results.get('total_tests', 0) > 0:
        success_rate = (results.get('successful_tests', 0) / results.get('total_tests', 0)) * 100
        print(f"📈 Success Rate: {success_rate:.1f}%")
    
    print(f"📄 Detailed Results: {results.get('results_file', 'N/A')}")
    print(f"📊 Assessment Report: {results.get('assessment_file', 'N/A')}")
    print("=" * 80)
    
    # Clean up temporary file
    os.unlink(temp_csv.name)
    
    return results


def main():
    """Main function to run all tool calling tests."""
    
    print("🚀 Starting Tool Calling Test Suite")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run the main RAN Config QA Agent tests
    main_results = asyncio.run(run_ran_config_qa_tool_tests())
    
    # Run custom tests (optional)
    # custom_results = asyncio.run(run_custom_tool_tests())
    
    print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎉 Tool calling test suite completed!")
    
    return main_results


if __name__ == "__main__":
    main() 