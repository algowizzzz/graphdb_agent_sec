"""
Test script for Hybrid Search functionality
Tests the CypherQueryBuilder hybrid search method independently
"""
import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

from config import get_config
from agent_components.cypher_builder import CypherQueryBuilder
from agent_components.neo4j_executor import Neo4jExecutor
from sentence_transformers import SentenceTransformer

def test_basic_hybrid_search():
    """Test basic hybrid search with realistic company and concept."""
    print("=== Test 1: Basic Hybrid Search ===")
    
    config = get_config("anthropic", "default")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    cypher_builder = CypherQueryBuilder(model)
    executor = Neo4jExecutor(
        uri=config.database.uri,
        user=config.database.user,
        password=config.database.password
    )
    
    try:
        # Use UMBF which we know has embeddings
        test_plan = {
            'search_type': 'Hybrid',
            'companies': ['BAC'],  # Bank of America
            'years': [2025],
            'quarters': ['Q1'],
            'concept': 'business overview and revenue streams'
        }
        
        print(f"Test Plan: {test_plan}")
        
        # Build query
        query, params = cypher_builder.build_query(test_plan)
        
        print("✅ Query built successfully")
        print(f"Query: {query}")
        print(f"Params keys: {list(params.keys())}")
        
        # Execute query
        results = executor.run_cypher_query(query, params=params)
        
        print("\n✅ Query executed successfully")
        print(f"Results count: {len(results)}")
        
        if results:
            print("\nTop 3 results:")
            for i, result in enumerate(results[:3], 1):
                filename = result.get('filename', 'N/A')
                score = result.get('score', 0)
                text_preview = result.get('text', '')[:100]
                print(f"  {i}. Score: {score:.4f}")
                print(f"     File: {filename}")
                print(f"     Preview: {text_preview}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        executor.close()

def test_no_filters_hybrid_search():
    """Test hybrid search without company/year filters."""
    print("\n=== Test 2: Hybrid Search No Filters ===")
    
    config = get_config("anthropic", "default")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    cypher_builder = CypherQueryBuilder(model)
    executor = Neo4jExecutor(
        uri=config.database.uri,
        user=config.database.user,
        password=config.database.password
    )
    
    try:
        test_plan = {
            'search_type': 'Hybrid',
            'concept': 'executive compensation and corporate governance'
        }
        
        print(f"Test Plan: {test_plan}")
        
        # Build query
        query, params = cypher_builder.build_query(test_plan)
        
        print("✅ Query built successfully")
        print(f"Query: {query}")
        if "MATCH" not in query:
            print("✅ Correctly generated pure vector search (no MATCH clause)")
        
        # Execute query
        results = executor.run_cypher_query(query, params=params)
        
        print("\n✅ Query executed successfully")
        print(f"Results count: {len(results)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        executor.close()

def test_all_filters_hybrid_search():
    """Test hybrid search with multiple companies and filters."""
    print("\n=== Test 3: Hybrid Search All Filters ===")
    
    config = get_config("anthropic", "default")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    cypher_builder = CypherQueryBuilder(model)
    executor = Neo4jExecutor(
        uri=config.database.uri,
        user=config.database.user,
        password=config.database.password
    )
    
    try:
        # Use companies we actually have data for
        test_plan = {
            'search_type': 'Hybrid',
            'companies': ['BAC', 'ZION'],  # Test with BAC and ZION
            'years': [2025],  # Year we have data for
            'quarters': ['Q1'],  # Quarters we have data for
            'concept': 'mortgage lending and real estate loans'
        }
        
        print(f"Test Plan: {test_plan}")
        
        # Build query
        query, params = cypher_builder.build_query(test_plan)
        
        print("✅ Query built successfully")
        print(f"Query: {query}")
        if all(filter_type in query for filter_type in ['c.name IN', 'y.value IN', 'q.label IN']):
            print("✅ Correctly generated filtered hybrid search")
        
        # Execute query
        results = executor.run_cypher_query(query, params=params)
        
        print("\n✅ Query executed successfully")
        print(f"Results count: {len(results)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        executor.close()

def test_hybrid_search_edge_cases():
    """Test hybrid search edge cases"""
    print("\n=== Test 4: Hybrid Search Edge Cases ===")
    
    config = get_config("anthropic", "default")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    cypher_builder = CypherQueryBuilder(model)
    
    # Test case 1: Empty concept
    test_plan_empty = {
        "search_type": "Hybrid",
        "companies": ["BAC"],
        "concept": ""
    }
    
    print("Test Case 1: Empty concept")
    try:
        query, params = cypher_builder.build_query(test_plan_empty)
        if not query:
            print("✅ Correctly handled empty concept (returned empty query)")
        else:
            print("❌ Should have failed with empty concept")
    except Exception as e:
        print(f"✅ Correctly failed with empty concept: {e}")
    
    # Test case 2: Missing concept
    test_plan_missing = {
        "search_type": "Hybrid",
        "companies": ["BAC"]
        # No concept field
    }
    
    print("\nTest Case 2: Missing concept")
    try:
        query, params = cypher_builder.build_query(test_plan_missing)
        if not query:
            print("✅ Correctly handled missing concept (returned empty query)")
        else:
            print("❌ Should have failed with missing concept")
    except Exception as e:
        print(f"✅ Correctly failed with missing concept: {e}")
    
    return True

def test_embedding_generation():
    """Test that embeddings are generated correctly"""
    print("\n=== Test 5: Embedding Generation ===")
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    cypher_builder = CypherQueryBuilder(model)
    
    test_concept = "financial performance metrics"
    
    # Create a minimal plan to test embedding generation
    test_plan = {
        "search_type": "Hybrid",
        "concept": test_concept
    }
    
    try:
        query, params = cypher_builder.build_query(test_plan)
        
        # Check if embedding was generated
        if "embedding" in params:
            embedding = params["embedding"]
            print(f"✅ Embedding generated successfully")
            print(f"Embedding type: {type(embedding)}")
            print(f"Embedding length: {len(embedding)}")
            print(f"Embedding sample: {embedding[:5]}...")
            
            # Check if it's a proper list of floats
            if isinstance(embedding, list) and all(isinstance(x, float) for x in embedding[:5]):
                print("✅ Embedding is properly formatted as list of floats")
            else:
                print("❌ Embedding format is incorrect")
            
            return True
        else:
            print("❌ No embedding found in parameters")
            return False
            
    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        return False

def test_no_matching_results():
    """Test hybrid search for a concept that should yield no results."""
    print("\n=== Test 6: No Matching Results ===")
    
    config = get_config("anthropic", "default")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    cypher_builder = CypherQueryBuilder(model)
    executor = Neo4jExecutor(
        uri=config.database.uri,
        user=config.database.user,
        password=config.database.password
    )
    
    try:
        test_plan = {
            'search_type': 'Hybrid',
            'companies': ['UMBF'],
            'years': [2022],
            'concept': 'manufacturing processes for semiconductor wafers'
        }
        
        print(f"Test Plan: {test_plan}")
        
        query, params = cypher_builder.build_query(test_plan)
        
        print("✅ Query built successfully for non-matching concept")
        
        results = executor.run_cypher_query(query, params=params)
        
        print(f"Results count: {len(results)}")
        
        if len(results) == 0:
            print("✅ Correctly returned no results for an irrelevant concept.")
            return True
        else:
            print(f"❌ Test failed: Expected 0 results, but got {len(results)}")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        executor.close()

def test_multi_company_financial_comparison():
    """Test comparing financial performance across multiple companies."""
    print("\n=== Test 7: Multi-Company Financial Comparison ===")
    
    config = get_config("anthropic", "default")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    cypher_builder = CypherQueryBuilder(model)
    executor = Neo4jExecutor(
        uri=config.database.uri,
        user=config.database.user,
        password=config.database.password
    )
    
    try:
        test_plan = {
            'search_type': 'Hybrid',
            'companies': ['BAC', 'ZION'],
            'years': [2024, 2025],
            'concept': 'company revenue and earnings report'
        }
        
        print(f"Test Plan: {test_plan}")
        
        query, params = cypher_builder.build_query(test_plan)
        print("✅ Query built successfully for multi-company comparison")
        
        results = executor.run_cypher_query(query, params=params)
        print(f"\n✅ Query executed successfully, found {len(results)} results.")
        
        if results:
            print("Top 3 results:")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. Score: {result.get('score', 0):.4f}, File: {result.get('filename', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        executor.close()

def test_regulatory_and_risk_search():
    """Test for specific regulatory items like Dodd-Frank or Basel III"""
    print("\n=== Test 8: Regulatory and Risk Search ===")
    
    config = get_config("anthropic", "default")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    cypher_builder = CypherQueryBuilder(model)
    executor = Neo4jExecutor(
        uri=config.database.uri,
        user=config.database.user,
        password=config.database.password
    )
    
    try:
        test_plan = {
            'search_type': 'Hybrid',
            'concept': 'stress testing and capital adequacy'
        }
        
        print(f"Test Plan: {test_plan}")
        
        query, params = cypher_builder.build_query(test_plan)
        print("✅ Query built successfully for regulatory search")
        
        results = executor.run_cypher_query(query, params=params)
        print(f"\n✅ Query executed successfully, found {len(results)} results.")
        
        if results:
            print("Top 3 results:")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. Score: {result.get('score', 0):.4f}, File: {result.get('filename', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        executor.close()

if __name__ == "__main__":
    print("🧪 Testing Hybrid Search Tool Independently")
    print("=" * 60)
    
    results = []
    results.append(test_basic_hybrid_search())
    results.append(test_no_filters_hybrid_search())
    results.append(test_all_filters_hybrid_search())
    results.append(test_hybrid_search_edge_cases())
    results.append(test_embedding_generation())
    results.append(test_no_matching_results())
    results.append(test_multi_company_financial_comparison())
    results.append(test_regulatory_and_risk_search())

    print("\n" + "="*60)
    print("📊 Test Summary:")
    passed = sum(1 for r in results if r)
    failed = len(results) - passed
    print(f"  Passed: {passed}/{len(results)}")
    print(f"  Failed: {failed}/{len(results)}")
    print("="*60)

    if failed > 0:
        sys.exit(1) 