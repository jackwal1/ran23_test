#!/usr/bin/env python3
"""
Generic test runner for the agent testing utility.
This script demonstrates how to use the AgentTestUtility class with any agent and LLM.
"""

import os
import sys
import json
from datetime import datetime
import platform
import asyncio

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_test_utility import AgentTestUtility, create_sample_csv

# Example agent initializer for RAN Config QA Agent
async def initialize_ran_config_qa_agent():
    """Initialize the RAN Config QA Agent."""
    try:
        from agent.ran_config_qa_agent import initialize_ran_config_qa_agent as init_agent
        return await init_agent()
    except ImportError as e:
        print(f" Failed to import RAN Config QA Agent: {e}")
        return None

# Example LLM model for assessment
def get_assessment_llm():
    """Get the LLM model for assessment."""
    try:
        from llms.llms import chatmodel_mistral_large_ran_2
        return chatmodel_mistral_large_ran_2
    except ImportError as e:
        print(f" Failed to import LLM model: {e}")
        return None

async def main():
    """Main function to run the agent test utility."""
    print("="*60)
    print("GENERIC AGENT TEST UTILITY DEMONSTRATION")
    print("="*60)

    # Create sample CSV if it doesn't exist
    # csv_file = "C:\\sohan\\projects\\DISH-genAI\\gitlab-dish\\dish-ran\\tests\\data\\sample_test_scenarios-1.csv"
    csv_file = "../data/sample_test_scenarios.csv"
    # csv_file = "..\\data\\sample_test_scenarios-1.csv"
    if not os.path.exists(csv_file):
        print("Creating sample test scenarios CSV file...")
        csv_file = create_sample_csv()

    print(f"Using test scenarios from: {csv_file}")

    # Get agent initializer and LLM model
    agent_initializer = initialize_ran_config_qa_agent
    llm_model = get_assessment_llm()

    print(f"Agent initializer: {agent_initializer.__name__}")
    print(f"LLM model: {type(llm_model).__name__ if llm_model else 'None'}")

    # Initialize the test utility with agent and LLM
    print("\nInitializing AgentTestUtility...")
    test_utility = AgentTestUtility(
        csv_file_path=csv_file,
        agent_initializer=agent_initializer,
        llm_model=llm_model
    )

    # Run the complete test suite
    print("\nRunning test suite...")
    results = await test_utility.run_complete_test_suite()

    # Display results
    print("\n" + "="*60)
    print("TEST SUITE EXECUTION COMPLETED")
    print("="*60)
    print(f"Total tests: {results.get('total_tests', 0)}")
    print(f"Successful: {results.get('successful_tests', 0)}")
    print(f"Failed: {results.get('failed_tests', 0)}")
    print(f"Results file: {results.get('results_file', 'N/A')}")

    # Display sample results if available
    if results.get('results_file') and os.path.exists(results['results_file']):
        print("\nSample test results:")
        try:
            with open(results['results_file'], 'r') as f:
                lines = f.readlines()
                # Show the summary section
                for line in lines[:15]:  # Show first 15 lines (header + summary)
                    print(line.rstrip())
        except Exception as e:
            print(f"Error reading results file: {e}")

    print("\n" + "="*60)
    print("Test utility demonstration completed!")
    print("="*60)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 