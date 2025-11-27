#!/usr/bin/env python3
"""
Test script to inspect how tool schemas are included in the prompt sent to the LLM model.
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

async def inspect_prompt_with_tools(model, model_name):
    """Inspect how tool schemas are included in the prompt sent to the LLM."""
    print(f"\n{'='*60}")
    print(f"🔍 Inspecting Prompt for {model_name}")
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
        
        # Test prompt
        test_prompt = "Please call the dummy tool with message 'hello world'"
        print(f"\n📝 Testing prompt: '{test_prompt}'")
        print("-" * 50)
        
        # Create the input state
        thread_id = f"test_{model_name.lower().replace(' ', '_')}_{int(time.time())}"
        messages = [{"role": "user", "content": test_prompt}]
        
        print(f"\n🔧 Tool Information:")
        print(f"  - Available tools: {list(agent.tools.keys())}")
        for tool_name, tool_obj in agent.tools.items():
            print(f"  - {tool_name}: {tool_obj.description}")
            print(f"    Schema: {tool_obj.args_schema}")
        
        # Try to inspect the model's internal prompt construction
        print(f"\n🤖 Model Configuration:")
        if hasattr(model, 'lc_kwargs'):
            print(f"  - Model kwargs: {model.lc_kwargs}")
        
        if hasattr(model, 'model_id'):
            print(f"  - Model ID: {model.model_id}")
        
        # Check if the model has function calling enabled
        print(f"\n📊 Function Calling Configuration:")
        try:
            # Try to get the model's function calling schema
            if hasattr(model, 'bind_tools'):
                print(f"  - Model supports bind_tools")
                
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
                
                # Bind tools to see what happens
                bound_model = model.bind_tools([function_schema])
                print(f"  - Successfully bound tools to model")
                
                # Try to inspect the bound model
                if hasattr(bound_model, 'lc_kwargs'):
                    print(f"  - Bound model kwargs: {bound_model.lc_kwargs}")
                
                # Test a simple call to see the actual prompt
                print(f"\n🧪 Testing direct model call to inspect prompt:")
                test_message = "Call the dummy tool with message 'test'"
                
                try:
                    # This will show us what the model actually receives
                    response = await bound_model.ainvoke([{"role": "user", "content": test_message}])
                    print(f"  ✅ Direct call successful")
                    print(f"  📤 Response: {response}")
                    
                    # Check if function calling was attempted
                    if hasattr(response, 'additional_kwargs') and response.additional_kwargs:
                        print(f"  🔧 Function calls in response: {response.additional_kwargs}")
                    else:
                        print(f"  ❌ No function calls in response")
                        
                except Exception as e:
                    print(f"  ❌ Direct call failed: {e}")
                    
            else:
                print(f"  - Model does not support bind_tools")
                
        except Exception as e:
            print(f"  ❌ Error inspecting function calling: {e}")
        
        # Try to get the actual prompt that would be sent
        print(f"\n📋 Prompt Construction Analysis:")
        try:
            # Check if we can access the model's prompt construction
            if hasattr(model, 'get_prompts'):
                prompts = model.get_prompts()
                print(f"  - Available prompts: {prompts}")
            
            # Check model's internal state
            if hasattr(model, '__dict__'):
                model_attrs = [attr for attr in dir(model) if not attr.startswith('_')]
                print(f"  - Model attributes: {model_attrs[:10]}...")  # First 10 attributes
                
        except Exception as e:
            print(f"  ❌ Error analyzing prompt construction: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error inspecting {model_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function to inspect prompts for both models."""
    print("🚀 Starting Prompt Inspection Test")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test both models
    results = {}
    
    # Test original model (Mistral Large)
    results['large'] = await inspect_prompt_with_tools(
        chatmodel_mistral_large_ran_2,
        "Mistral Large"
    )
    
    # Test new model (Mistral Medium)
    results['medium'] = await inspect_prompt_with_tools(
        chatmodel_mistral_medium_ran_2,
        "Mistral Medium"
    )
    
    # Compare results
    print(f"\n{'='*60}")
    print("📊 PROMPT INSPECTION COMPARISON")
    print(f"{'='*60}")
    
    for model_type, result in results.items():
        print(f"\n{model_type.upper()} MODEL:")
        print(f"  Prompt inspection: {'✅ PASSED' if result else '❌ FAILED'}")
    
    print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main()) 