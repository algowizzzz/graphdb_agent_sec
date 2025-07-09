from neo4j import GraphDatabase

def generate_cypher_for_raw_scout(query_embedding, excluded_docs, top_k=3):
    """Generates the Cypher query for the 'raw scout' phase."""
    # We now check if the excluded_docs list is empty to avoid an unnecessary WHERE clause.
    where_clause = ""
    if excluded_docs:
        where_clause = "WHERE s.filename NOT IN $excluded_docs"

    query = f"""
    CALL db.index.vector.queryNodes('section_embeddings', {top_k}, $query_embedding)
    YIELD node AS s, score
    WITH s, score
    {where_clause}
    RETURN s.filename AS filename, s.section AS section_name, score
    ORDER BY score DESC
    """
    params = {"query_embedding": query_embedding, "excluded_docs": excluded_docs}
    return query, params

def find_relevant_sections(driver: GraphDatabase.driver, query_embedding, excluded_docs=[]):
    """
    Performs a 'scout' search to identify the most relevant section types for a concept.
    
    Args:
        driver: The Neo4j database driver.
        query_embedding: The vector embedding for the user's concept.

    Returns:
        A list of the most relevant section names (e.g., ['Financials', 'Risk Factors']).
    """
    # === Query 1: Get the raw scout data for visibility ===
    raw_scout_query, params = generate_cypher_for_raw_scout(query_embedding, excluded_docs=excluded_docs)
    
    print("\n--- Scout Phase: Identifying relevant section types ---")
    print("Step 1/2: Running raw scout query to find top 10 candidate documents...")

    with driver.session() as session:
        result = session.run(raw_scout_query, params)
        raw_candidates = [dict(record) for record in result]
    
    if raw_candidates:
        print("Raw scout results (the evidence):")
        for doc in raw_candidates:
            print(f"  - {doc['filename']} (Section: {doc['section_name']}, Score: {doc['score']:.4f})")
    else:
        print("Raw scout did not find any candidate documents.")
        return []

    # === Step 2: Tally the results to find the top section types ===
    # This step is now done in Python for clarity, using the data from the first query.
    print("\nStep 2/2: Tallying results to determine best section types...")
    
    # Count occurrences of each section type from the raw results
    section_counts = {}
    for doc in raw_candidates:
        section = doc['section_name']
        section_counts[section] = section_counts.get(section, 0) + 1
        
    # Sort the sections by how many times they appeared in the top 10
    # This gives us the most frequently relevant section types
    sorted_sections = sorted(section_counts.items(), key=lambda item: item[1], reverse=True)
    
    # We will return the top 3 most frequent section types
    top_section_names = [section[0] for section in sorted_sections[:3]]
    
    if top_section_names:
        print(f"Scout Phase identified the following section types as most relevant: {top_section_names}")
    else:
        print("Scout Phase could not identify any specific section types.")

    return top_section_names