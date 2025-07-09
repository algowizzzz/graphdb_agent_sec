import logging
import sys
import importlib.util
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Handle numbered directory import
def import_from_file(file_path, class_name):
    """Helper function to import from a specific file"""
    spec = importlib.util.spec_from_file_location("temp_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)

# Import VectorDB from the numbered directory
current_dir = Path(__file__).parent
vector_db_path = current_dir / "vector_db.py"
try:
    VectorDB = import_from_file(vector_db_path, "VectorDB")
except Exception as e:
    print(f"Warning: Could not import VectorDB: {e}")
    # Define a dummy VectorDB class as fallback
    class VectorDB:
        def __init__(self):
            pass
        def load_index(self):
            pass
        def search(self, embedding, k=10):
            return [], []

class CypherQueryBuilder:
    """
    Builds Cypher queries based on a structured search plan.
    This version is designed to work with Neo4j and a FAISS vector index.
    """
    def __init__(self, model: SentenceTransformer, vector_db: VectorDB):
        """
        Initializes the query builder.

        Args:
            model: The sentence-transformer model for creating embeddings.
            vector_db: An instance of the VectorDB class for semantic search.
        """
        self.model = model
        self.vector_db = vector_db
        logging.info("CypherQueryBuilder initialized with FAISS vector database.")

    def build_query(self, plan: dict) -> str:
        search_type = plan.get("search_type")
        if search_type == "Hybrid":
            return self._build_hybrid_query(plan)
        elif search_type == "Comprehensive":
            return self._build_comprehensive_query(plan)
        else: # Default to Direct
            return self._build_direct_query(plan)

    def _build_comprehensive_query(self, plan: dict) -> str:
        """
        Builds a query to retrieve the 10 latest document sections for a given company.
        """
        logging.info("[Comprehensive Search] Building comprehensive Cypher query.")
        companies = plan.get('companies', [])
        if not companies:
            logging.error("Comprehensive search requires a company.")
            return ""

        companies_str = "[" + ", ".join(f"'{c}'" for c in companies) + "]"
        query = f"""
        MATCH (c:Company)-[:HAS_YEAR]->(y:Year)-[:HAS_QUARTER]->(q:Quarter)-[:HAS_DOC]->(d:Document)-[:HAS_SECTION]->(s:Section)
        WHERE c.name IN {companies_str}
        WITH s, d, y, q
        ORDER BY y.value DESC, q.label DESC
        LIMIT 10
        RETURN s.text AS text, s.filename AS filename
        """
        
        return query.strip()

    def _build_direct_query(self, plan: dict) -> str:
        logging.info("[Direct Search] Building direct Cypher query.")
        
        match_clause = "MATCH (c:Company)-[:HAS_YEAR]->(y:Year)-[:HAS_QUARTER]->(q:Quarter)-[:HAS_DOC]->(d:Document)-[:HAS_SECTION]->(s:Section)"
        
        where_parts = []
        
        companies = plan.get('companies', [])
        years = plan.get('years', [])
        quarters = plan.get('quarters', [])
        sections = plan.get('sections', [])

        if companies:
            companies_str = "[" + ", ".join(f"'{c}'" for c in companies) + "]"
            where_parts.append(f"c.name IN {companies_str}")
        
        if years:
            years_str = "[" + ", ".join(str(y) for y in years) + "]"
            where_parts.append(f"y.value IN {years_str}")

        if quarters:
            quarters_str = "[" + ", ".join(f"'{q}'" for q in quarters) + "]"
            where_parts.append(f"q.label IN {quarters_str}")

        if sections:
            sections_str = "[" + ", ".join(str(s) for s in sections) + "]"
            where_parts.append(f"id(s) IN {sections_str}")
        
        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)
        
        return_clause = "RETURN s.text AS text, s.filename AS filename"
        
        final_query = f"{match_clause} {where_clause} {return_clause}"
        return final_query

    def _build_hybrid_query(self, plan: dict) -> str:
        logging.info("[Hybrid Search] Building hybrid query using FAISS.")
        
        semantic_query = plan.get("concept")
        if not semantic_query:
            logging.error("Hybrid search failed: No 'concept' found in plan.")
            return ""

        logging.info(f"Performing FAISS search for: '{semantic_query}'")
        query_embedding = self.model.encode(semantic_query)
        distances, section_ids = self.vector_db.search(query_embedding, k=20) 

        if not section_ids:
            logging.warning("FAISS search returned no results.")
            return ""

        logging.info(f"FAISS search found {len(section_ids)} relevant sections.")
        
        # Build the Cypher query using the section IDs from FAISS
        section_ids_str = "[" + ", ".join(f"'{sid}'" for sid in section_ids) + "]"
        
        match_clause = "MATCH (s:Section)"
        where_parts = [f"s.id IN {section_ids_str}"]
        
        companies = plan.get('companies', [])
        years = plan.get('years', [])
        quarters = plan.get('quarters', [])

        # Add filters by traversing back through the graph
        if companies:
            companies_str = "[" + ", ".join(f"'{c}'" for c in companies) + "]"
            where_parts.append(f"EXISTS {{ MATCH (s)<-[:HAS_SECTION]-(d:Document)<-[:HAS_DOC]-(q:Quarter)<-[:HAS_QUARTER]-(y:Year)<-[:HAS_YEAR]-(c:Company) WHERE c.name IN {companies_str} }}")
        
        if years:
            years_str = "[" + ", ".join(str(y) for y in years) + "]"
            where_parts.append(f"EXISTS {{ MATCH (s)<-[:HAS_SECTION]-(d:Document)<-[:HAS_DOC]-(q:Quarter)<-[:HAS_QUARTER]-(y:Year) WHERE y.value IN {years_str} }}")
        
        if quarters:
            quarters_str = "[" + ", ".join(f"'{q}'" for q in quarters) + "]"
            where_parts.append(f"EXISTS {{ MATCH (s)<-[:HAS_SECTION]-(d:Document)<-[:HAS_DOC]-(q:Quarter) WHERE q.label IN {quarters_str} }}")

        where_clause = "WHERE " + " AND ".join(where_parts)
        return_clause = "RETURN s.text AS text, s.filename AS filename"

        final_query = f"{match_clause} {where_clause} {return_clause}"
        return final_query


# Legacy functions for backward compatibility
def generate_cypher_for_direct_lookup(analysis):
    """
    Builds a Cypher query for a direct entity lookup.
    Handles comprehensive lookups (no sections) and specific lookups.
    """
    params = {
        "companies": analysis.get("companies", []),
        "years": analysis.get("years", []),
        "quarters": analysis.get("quarters", []),
        "sections": analysis.get("sections", []),
        "excluded_docs": analysis.get("excluded_docs", [])
    }
    
    match_clause = "MATCH (s:Section)<--(d:Document)<--(q:Quarter)<--(y:Year)<--(c:Company)"

    where_parts = []

    # Add filters if they exist in the plan
    if params["companies"]:
        where_parts.append("c.name IN $companies")
    if params["years"]:
        where_parts.append("y.value IN $years")
    if params["quarters"]:
        where_parts.append("q.label IN $quarters")
    if params["sections"]:
        where_parts.append("s.section IN $sections")
    if params["excluded_docs"]:
        where_parts.append("s.filename NOT IN $excluded_docs")
    
    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)
        
    return_clause = "RETURN s.text AS text, s.filename AS filename"
    limit_clause = "LIMIT 10"

    final_query = f"{match_clause} {where_clause} {return_clause} {limit_clause}"
    
    print(f"\n[Direct Lookup] Generated Cypher Query:\n{final_query}")
    return final_query, params


def generate_cypher_for_pure_semantic_search(query_embedding, top_k=10):
    """
    Builds the most efficient query for a pure semantic search with no graph filters.
    We've increased the default top_k to 10 to match the new limit.
    """
    params = {"query_embedding": query_embedding}
    final_query = f"""
    CALL db.index.vector.queryNodes('section_embeddings', {top_k}, $query_embedding)
    YIELD node AS s, score
    RETURN s.text AS text, s.filename AS filename, score
    """
    print(f"\n[Pure Semantic Search] Generated Cypher Query:\n{final_query}")
    return final_query, params


def generate_cypher_for_hybrid_search(analysis, query_embedding, top_k=10):
    """
    Builds a vector search query that is then filtered by graph properties.
    We now fetch a larger initial set from the vector index (e.g., 50) and then
    limit the final results to 10 after filtering.
    """
    params = {
        "query_embedding": query_embedding,
        "companies": analysis.get("companies", []),
        "years": analysis.get("years", []),
        "quarters": analysis.get("quarters", []),
        "excluded_docs": analysis.get("excluded_docs", [])
    }

    # Fetch more results initially to allow for filtering
    call_clause = f"""
    CALL db.index.vector.queryNodes('section_embeddings', 50, $query_embedding)
    YIELD node AS s, score
    """
    
    match_clause = "MATCH (c:Company)-[:HAS_YEAR]->(y:Year)-[:HAS_QUARTER]->(q:Quarter)-[:HAS_DOC]->(d:Document)-[:HAS_SECTION]->(s)"

    where_parts = []
    if params["companies"]:
        where_parts.append("c.name IN $companies")
    if params["years"]:
        where_parts.append("y.value IN $years")
    if params["quarters"]:
        where_parts.append("q.label IN $quarters")
    if params["excluded_docs"]:
        where_parts.append("s.filename NOT IN $excluded_docs")

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    return_clause = "RETURN s.text AS text, s.filename AS filename, score"
    limit_clause = "LIMIT 10"

    final_query = f"{call_clause} {match_clause} {where_clause} {return_clause} {limit_clause}"

    print(f"\n[Hybrid Search] Generated Cypher Query:\n{final_query}")
    return final_query, params