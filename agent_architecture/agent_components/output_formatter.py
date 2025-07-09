def format_plan_to_natural_language(analysis, query_type):
    """
    Translates the agent's analysis and chosen query plan into a human-readable string.
    """
    sentences = ["Okay, here is my thought process and final plan to answer your request."]

    # 1. Companies
    if analysis.get("companies"):
        sentences.append(f"- **Filters:** I will focus my search on the following company/companies: {', '.join(analysis['companies'])}.")
    else:
        sentences.append("- **Filters:** Since no specific company was mentioned, I will search across all available companies.")

    # 2. Years
    if analysis.get("years"):
        sentences.append(f"- **Filters:** The search will be limited to the year(s): {', '.join(map(str, analysis['years']))}.")
    else:
        sentences.append("- **Filters:** No specific year was requested, so I will include all available years.")
    
    # 3. Quarters
    if analysis.get("quarters"):
        sentences.append(f"- **Filters:** I will narrow the search to the following quarter(s): {', '.join(analysis['quarters'])}.")
    else:
        sentences.append("- **Filters:** No particular quarter was specified, so my search will cover all quarters within the selected year(s).")

    # 4. Search Strategy (The core reasoning)
    sentences.append("\n- **Strategy:**")
    if analysis.get("scout_reasoning"):
        sentences.append(f"  - {analysis['scout_reasoning']}")
    
    if query_type == "direct_lookup":
        sentences.append(f"  - Because specific section(s) have been identified ('{', '.join(analysis['sections'])}'), my plan is to use the **Direct Lookup** strategy to perform a comprehensive search and retrieve all matching documents.")
    elif query_type == "hybrid_search":
        sentences.append(f"  - The query is conceptual but also contains specific filters. My plan is to use the **Hybrid Search** strategy, which combines a vector search with graph-based filtering.")
    elif query_type == "pure_semantic_search":
        sentences.append(f"  - The query is a general knowledge question with no specific filters. My plan is to use the **Pure Semantic Search** strategy to find the most relevant documents from the entire database.")
    else:
        sentences.append("  - I could not determine a valid strategy for this query.")
        
    return "\n".join(sentences)