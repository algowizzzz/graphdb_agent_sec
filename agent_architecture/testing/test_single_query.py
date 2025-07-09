"""
End-to-End Test Script for the Full QueryAgent Workflow

This script demonstrates how to run a complete, end-to-end query using the 
high-level `Neo4jQueryAgent`. It leverages the unified configuration system,
allowing easy switching between different LLM providers.
"""
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
# This allows the script to find the 'core_agents' and 'config' modules
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Import the main agent and config system
from config import get_config, ConfigManager
from core_agents.query_agent import Neo4jQueryAgent

# =============================================================================
# CONFIGURATION - CHANGE THESE TO SWITCH PROVIDERS
# =============================================================================
PROVIDER = "anthropic"  # Options: "openai", "anthropic", "ollama", "google"
MODEL_TIER = "default"    # Options: "default", "fast", "powerful" (e.g., "sonnet")

# Test query for a single, focused E2E test
USER_QUERY = "BAC business summary across all available years, provide a summary for each year in bullets?"
#zion business summary of 2025 
#zion business summary of 2025 vs 2024, include all relevant documents 
#"ZION business summary across all available years, provide a summary for each year in bullets?"
# =============================================================================

def main():
    """Main execution function for the end-to-end test"""
    print("\n================================================================================")
    print(" E2E AGENT TEST SCRIPT")
    print("================================================================================")

    # Get and validate configuration
    try:
        config = get_config(PROVIDER, MODEL_TIER)
        print(f"⚙️  Configuration Loaded: Provider='{config.llm.provider}', Model='{config.llm.model}'")
        if not ConfigManager.validate_config(config):
            print("❌ Configuration validation failed! Ensure API keys are in .env file.")
            return
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return

    agent = None
    try:
        # 1. Initialize the high-level Neo4jQueryAgent with the config
        print("\n🔧 Initializing Neo4jQueryAgent...")
        agent = Neo4jQueryAgent(config=config)
        print("✅ Agent initialized successfully!")
        
        # 2. Run the end-to-end query
        print(f"\n🚀 Processing query: '{USER_QUERY}'")
        print("-" * 60)
        result = agent.run(USER_QUERY)
        
        # 3. Print the final result
        print("\n📊 FINAL RESULT:")
        print("-" * 60)
        # The result is a string, so we just print it.
        # If it were JSON, we would use json.dumps
        print(result)

    except Exception as e:
        print(f"\n❌ An error occurred during agent execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 4. Clean up the connection
        if agent:
            agent.close()
            print("\n🔌 Test complete. Connection closed.")

if __name__ == "__main__":
    main()