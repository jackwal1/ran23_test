#!/usr/bin/env python3
"""
Test script to verify tool docstrings are correctly injected before LLM calls.
"""

import sys
import os
import asyncio
import time
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from langchain_core.tools import tool
from typing import Dict
from agent.base_agent_asset import Telco_Agent
from utils.memory_checkpoint import get_checkpointer
from llms.llms import chatmodel_mistral_large_ran_2, chatmodel_mistral_medium_ran_2

# Create a simple dummy tool with clear docstring
@tool("dummy_tool")
async def dummy_tool(message: str) -> Dict[str, str]:
    """
    A simple dummy tool for testing.
    
    Use this tool when the user asks for a test or dummy response.
    
    Args:
        message: The message to echo back
        
    Returns:
        A dictionary with the echoed message
    """
    return {
        "message": f"Dummy tool called with: {message}",
        "timestamp": datetime.now().isoformat()
    }

async def test_tool_injection(model, model_name):
    """Test if tool docstrings are correctly injected before LLM calls."""
    print(f"\n{'='*60}")
    print(f"🔍 Testing Tool Injection for {model_name}")
    print(f"{'='*60}")
    
    try:
        # Initialize the agent with dummy tools
        print(f"Initializing {model_name} with dummy tools...")
        start_time = time.time()
        
        # Get checkpoint manager
        checkpointer = await get_checkpointer()
        
        # Create agent with dummy tools
        agent = Telco_Agent(
            model,
            [dummy_tool],  # Use only the dummy tool
            token_memory_limit=100000,
            system="You are a helpful assistant. Use the dummy_tool when asked to test or call a tool.",
            checkpointer=checkpointer,
        )
        
        graph = agent.graph
        
        init_time = time.time() - start_time
        print(f"✅ {model_name} initialized in {init_time:.2f}s")
        
        # Test prompt that should trigger tool call
        test_prompt = "Please call the dummy tool with message 'hello world'"
        print(f"\n📝 Testing prompt: '{test_prompt}'")
        print("-" * 50)
        
        # Create the input state
        thread_id = f"test_{model_name.lower().replace(' ', '_')}_{int(time.time())}"
        messages = [{"role": "user", "content": test_prompt}]
        
        print(f"\n🔧 Available tools in agent:")
        if hasattr(agent, 'tools'):
            for tool_name, tool_obj in agent.tools.items():
                print(f"  - {tool_name}: {tool_obj}")
        else:
            print("  [!] No 'tools' attribute found on agent")
        
        print(f"\n📋 Tool descriptions that should be injected:")
        for tool_name, tool_obj in agent.tools.items():
            print(f"  - {tool_name}: {tool_obj.description}")
        
        # Check if the model has function calling capabilities
        print(f"\n🤖 Model function calling capabilities:")
        if hasattr(model, 'bind_tools'):
            print(f"  - Model supports bind_tools method")
        else:
            print(f"  - Model does not have bind_tools method")
        
        if hasattr(model, 'with_structured_output'):
            print(f"  - Model supports with_structured_output method")
        else:
            print(f"  - Model does not have with_structured_output method")
        
        # Try to get the model's function calling schema
        print(f"\n📊 Model function calling schema:")
        try:
            # Check if model has function calling enabled
            if hasattr(model, 'lc_kwargs'):
                print(f"  - Model kwargs: {model.lc_kwargs}")
            
            # Check model configuration
            if hasattr(model, 'model_id'):
                print(f"  - Model ID: {model.model_id}")
            
            if hasattr(model, 'model_name'):
                print(f"  - Model Name: {model.model_name}")
                
        except Exception as e:
            print(f"  - Error getting model schema: {e}")
        
        # Test a simple direct call to see if the model can make function calls
        print(f"\n🧪 Testing direct model call with function calling:")
        try:
            # Create a simple function schema
            function_schema = {
                "name": "dummy_tool",
                "description": "A simple dummy tool for testing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message to echo back"
                        }
                    },
                    "required": ["message"]
                }
            }
            
            # Try to bind tools to the model
            if hasattr(model, 'bind_tools'):
                bound_model = model.bind_tools([function_schema])
                print(f"  ✅ Successfully bound tools to {model_name}")
                
                # Test a simple call
                test_message = "Call the dummy tool with message 'test'"
                print(f"  📝 Testing: '{test_message}'")
                
                # This might not work directly, but let's see what happens
                try:
                    response = await bound_model.ainvoke([{"role": "user", "content": test_message}])
                    print(f"  ✅ Direct call successful: {response}")
                except Exception as e:
                    print(f"  ❌ Direct call failed: {e}")
            else:
                print(f"  ❌ {model_name} does not support bind_tools")
                
        except Exception as e:
            print(f"  ❌ Error testing direct function calling: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing {model_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function to check tool injection for both models."""
    print("🚀 Starting Tool Injection Test")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test both models
    results = {}
    
    # Test original model (Mistral Large)
    results['large'] = await test_tool_injection(
        chatmodel_mistral_large_ran_2,
        "Mistral Large"
    )
    
    # Test new model (Mistral Medium)
    results['medium'] = await test_tool_injection(
        chatmodel_mistral_medium_ran_2,
        "Mistral Medium"
    )
    
    # Compare results
    print(f"\n{'='*60}")
    print("📊 TOOL INJECTION COMPARISON")
    print(f"{'='*60}")
    
    for model_type, result in results.items():
        print(f"\n{model_type.upper()} MODEL:")
        print(f"  Tool injection test: {'✅ PASSED' if result else '❌ FAILED'}")
    
    print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main()) 