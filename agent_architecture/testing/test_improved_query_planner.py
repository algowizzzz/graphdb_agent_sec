"""
Test script for the improved query planner with focused data approach
"""

import sys
import os
import json
from pathlib import Path
import logging

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

# Import necessary components
from config import get_config, ConfigManager
from agent_components.unified_llm_client import UnifiedLLMClient
from agent_components.neo4j_executor import Neo4jExecutor
from agent_components.improved_query_planner import ImprovedQueryPlanner

# =============================================================================
# TEST CONFIGURATION
# =============================================================================

# Choose your LLM provider for testing
PROVIDER = "anthropic"  # Options: "openai", "anthropic", "ollama", "google"
MODEL_TIER = "sonnet"  # Options: "default", "fast", "powerful"

# TEST QUERIES - Change this to test different queries
USER_QUERY = "BAC 2025 q1 all sections, create a detailed sumamry report?"

# Additional sample queries to try:
SAMPLE_QUERIES = [
    "What was BAC financial metrics?",
    "Give me JPM risk factors for 2024",
    "Show me ZION business information",
    "What are WFC's financial statements for Q1 2025?",
    "Give me a summary for PNC",
    "BAC management discussion Q2 2025",
    "Financial metrics for all companies",
]

# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def print_section(title):
    """Print a formatted section"""
    print(f"\n📋 {title}")
    print("-" * 60)

def print_json_pretty(data, title="JSON Output"):
    """Pretty print JSON data"""
    print(f"\n🔍 {title}:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

def test_improved_planner(planner, query):
    """Test the improved query planner"""
    print_section("IMPROVED QUERY PLANNER TEST")
    print(f"Query: '{query}'")
    
    # Create a plan using the new, versatile entry point
    plan = planner.create_plan(query)
    
    print_json_pretty(plan, "Focused Query Plan")
    
    # Analyze the plan
    analyze_improved_plan(plan)
    
    return plan

def analyze_improved_plan(plan_or_list):
    """Analyze and explain the improved planning decision. Handles a single plan or a list of plans."""
    print_section("PLAN ANALYSIS")

    if not plan_or_list:
        print("❌ No plan generated")
        return

    # If it's a list of plans, analyze each one. Otherwise, put the single plan in a list to standardize.
    plans = plan_or_list if isinstance(plan_or_list, list) else [plan_or_list]

    for i, plan in enumerate(plans):
        if len(plans) > 1:
            print(f"\n--- Analyzing Plan {i+1}/{len(plans)} ---")

        search_type = plan.get('search_type', 'Unknown')
        # Extract the specific company for this part of the plan, if available.
        # This part of the logic may need refinement based on how multi-company plans are structured.
        all_companies = plan.get('companies', ['Unknown'])
        company = all_companies[i] if i < len(all_companies) else all_companies[0]

        reasoning = plan.get('reasoning', 'No reasoning provided')
        
        print(f"🎯 Search Strategy: {search_type}")
        print(f"🏢 Target Company: {company}")
        print(f"💭 Reasoning: {reasoning}")
        
        if search_type == 'Direct':
            sections = plan.get('sections', [])
            print(f"📂 Target Sections: {sections}")
            print("   ✅ Will use metadata filtering to find exact sections")
            
        elif search_type == 'Hybrid':
            concept = plan.get('concept', '')
            print(f"🔍 Search Concept: '{concept}'")
            print("   ✅ Will use vector search + metadata filtering")
            
        elif search_type == 'Comprehensive':
            print("📊 Will retrieve latest documents for the company")
            
        else:
            print(f"❓ Unknown search strategy: {search_type}")

def compare_old_vs_new_approach():
    """Compare the old 3-step vs new 1-step approach"""
    print_section("OLD vs NEW APPROACH COMPARISON")
    
    print("❌ OLD APPROACH (3 steps):")
    print("  1. Preliminary Plan: Extract entities with ALL companies' data")
    print("  2. Dynamic Schema: Get sections for extracted entities") 
    print("  3. Final Plan: LLM confused by too much irrelevant data")
    print("  Result: Poor section matching, wrong search type")
    
    print("\n✅ NEW APPROACH (1 step):")
    print("  1. Extract company → Get ONLY that company's real data")
    print("  2. Get focused sections for specific context")
    print("  3. LLM gets clean, relevant data → Better decisions")
    print("  Result: Accurate section matching, correct search type")

def main():
    """Main test execution"""
    print_header("IMPROVED QUERY PLANNER TEST")
    
    print(f"🔧 Configuration:")
    print(f"   Provider: {PROVIDER}")
    print(f"   Model Tier: {MODEL_TIER}")
    print(f"   Test Query: '{USER_QUERY}'")
    
    # Initialize components
    try:
        print_section("INITIALIZATION")
        
        # Get configuration
        config = get_config(PROVIDER, MODEL_TIER)
        if not ConfigManager.validate_config(config):
            print("❌ Configuration validation failed!")
            return
        
        print("✅ Configuration validated")
        
        # Initialize LLM client
        llm_client = UnifiedLLMClient(config.llm)
        print("✅ LLM client initialized")
        
        # Initialize Neo4j executor
        neo4j_executor = Neo4jExecutor(
            uri=config.database.uri,
            user=config.database.user,
            password=config.database.password
        )
        print("✅ Neo4j executor initialized")
        
        # Initialize improved planner
        planner = ImprovedQueryPlanner(llm_client, neo4j_executor)
        print("✅ Improved planner initialized")
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return
    
    # Test the improved planner
    try:
        # Test the improved approach
        plan = test_improved_planner(planner, USER_QUERY)
        
        # Show comparison
        compare_old_vs_new_approach()
        
        # Summary
        print_section("TEST SUMMARY")
        if plan:
            print(f"✅ Improved Plan: Generated")
            # Handle both single dict and list of dicts for the plan
            if isinstance(plan, list):
                print(f"✅ Generated {len(plan)} plans for {len(plan[0].get('companies', []))} companies.")
                for i, p in enumerate(plan):
                    print(f"  - Plan {i+1} ({p.get('companies', ['N/A'])[i]}): {p.get('search_type')} search with {len(p.get('sections',[]))} sections.")
            else:
                print(f"🎯 Search Strategy: {plan.get('search_type', 'Unknown')}")
                company = plan.get('companies', ['None'])[0] if plan.get('companies') else 'None'
                print(f"🏢 Target Company: {company}")
                
                if plan.get('search_type') == 'Direct':
                    print(f"📂 Matched Sections: {plan.get('sections', [])}")
        else:
            print("❌ Plan generation failed")
        
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        neo4j_executor.close()
        print("\n✅ Test complete. Connection closed.")

def show_sample_queries():
    """Show available sample queries"""
    print_header("SAMPLE QUERIES FOR TESTING")
    
    for i, query in enumerate(SAMPLE_QUERIES, 1):
        print(f"{i}. {query}")
    
    print("\n🔧 To test a different query:")
    print("1. Change the USER_QUERY variable at the top of this script")
    print("2. Or copy one of the sample queries above") 
    print("3. Run the script again")

def _llm_create_plan_with_focused_data(self, query: str, focused_data: dict, available_sections: list) -> dict:
    # Give LLM EXACT section names - no guessing needed
    exact_section_names = [section['name'] for section in available_sections]
    
    prompt = f"""
    Available sections (USE THESE EXACT NAMES):
    {exact_section_names}
    
    If you choose Direct search, you MUST use one of these exact section names.
    If none match the user query, choose Hybrid or Comprehensive.
    """

def _validate_and_enhance_plan(self, plan: dict, focused_data: dict, available_sections: list) -> dict:
    """
    MINIMAL validation - NEVER override LLM decisions
    """
    # Just ensure required fields exist
    plan.setdefault("companies", [focused_data.get("company", "")])
    plan.setdefault("years", [])
    plan.setdefault("quarters", [])
    plan.setdefault("sections", [])
    plan.setdefault("concept", "")
    plan.setdefault("search_type", "Comprehensive")
    plan.setdefault("reasoning", "")
    
    # LOG section mismatches but DON'T override
    if plan.get("search_type") == "Direct" and plan.get("sections"):
        section_names = [s['name'] for s in available_sections]
        for section in plan["sections"]:
            if section not in section_names:
                logging.warning(f"⚠️  LLM section '{section}' not found in available sections, but keeping Direct search")
    
    # NEVER override the LLM's decision
    return plan

if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--samples":
            show_sample_queries()
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python test_improved_query_planner.py           # Run the test")
            print("  python test_improved_query_planner.py --samples # Show sample queries")
            print("  python test_improved_query_planner.py --help    # Show this help")
    else:
        main() 