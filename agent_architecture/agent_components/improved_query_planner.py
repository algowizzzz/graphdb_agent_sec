"""
Improved Query Planner - Completely self-contained with built-in prompts

Key improvements:
1. NO external prompt files needed
2. Company-specific focused data
3. Single-step intelligent planning
4. Built-in semantic section matching
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ImprovedQueryPlanner:
    """
    Enhanced query planner that generates a dynamic, grounded, multi-step extraction
    plan instead of just a simple query.
    """
    
    def __init__(self, llm_client, neo4j_executor):
        self.llm_client = llm_client
        self.neo4j_executor = neo4j_executor
        
    def create_plan(self, query: str) -> Optional[Dict]:
        """
        Primary entry point. Generates a comprehensive, grounded extraction plan.

        Returns:
            A JSON object representing the detailed extraction plan, or None if a plan
            cannot be created.
        """
        logging.info(f"🎯 Creating a dynamic extraction plan for query: '{query}'")

        # Step 1: Preliminary check for a simple metadata query
        metadata_plan = self._llm_classify_and_build_metadata_query(query)
        if metadata_plan and metadata_plan.get("query_type") == "metadata":
            logging.info("✅ This is a metadata query. Returning a simple metadata plan.")
            # We wrap it in our new structure for consistency
            return {
                "plan_type": "metadata",
                "analysis_goal": metadata_plan.get("human_readable_answer", "Execute metadata query."),
                "cypher_query": metadata_plan.get("cypher_query"),
                "sections_to_retrieve": [],
                "extraction_checklist": []
            }

        # Step 2: For content queries, gather all available context from the database
        logging.info("Query is content-focused. Proceeding to gather all available documents.")
        all_companies = self.neo4j_executor.get_unique_values_for_property('Company', 'name')
        found_companies = self._llm_extract_company(query, all_companies)
        
        if not found_companies:
            logging.warning("No companies were identified in the query. Cannot create a plan.")
            return None

        # Aggregate all available sections for all found companies
        all_available_sections = []
        for company in found_companies:
            entities = self._extract_entities_from_query(query, company)
            sections = self._get_focused_sections(company, entities)
            # Add company name to each section for clarity in the plan
            for section in sections:
                section['company'] = company
            all_available_sections.extend(sections)

        if not all_available_sections:
            logging.warning("No documents found for the given companies and filters. Cannot create a plan.")
            return None

        # Step 3: Generate the Grounded Extraction Plan using the new LLM call
        logging.info("Generating grounded extraction plan with LLM...")
        extraction_plan = self._llm_generate_extraction_guide(query, all_available_sections)
        
        if not extraction_plan:
            logging.error("Failed to generate a valid extraction plan from the LLM.")
            return None
            
        logging.info("✅ Successfully created dynamic extraction plan.")
        return extraction_plan

    def _extract_entities_from_query(self, query: str, company: str) -> Dict[str, list]:
        """
        Extracts year, quarter, and document type for a given company to pre-filter documents.
        This helps narrow down the context for the main planning LLM call.
        """
        # This is a simplified version of the original entity extraction logic
        company_data = self._get_company_focused_data(company)
        entities = {"companies": [company]}
        context_entities = self._llm_extract_context_entities(query, company_data)
        entities.update(context_entities)
        logging.info(f"📋 Extracted entities for pre-filtering for {company}: {entities}")
        return entities

    def _llm_generate_extraction_guide(self, query: str, available_sections: List[Dict]) -> Optional[Dict]:
        """
        The core of the new planner. This LLM call looks at the user's query and the
        list of available documents and generates a detailed plan (the "guide").
        """
        # Create a simplified, readable list of documents for the prompt
        readable_docs = [
            f"- Company: {s['company']}, Document: {s['doc_type']}, Section Name: {s['section_name']}, Section ID: {s['section_id']}"
            for s in available_sections
        ]

        prompt = f"""
You are a world-class financial analyst and strategic planner. Your task is to create a structured, step-by-step plan to answer a user's complex query about SEC filings. You will be given the user's query and a list of all the specific document sections that are available in the database.

**User's Query:**
{query}

**Available Document Sections:**
{json.dumps(readable_docs, indent=2)}

**Your Task:**
Based on the user's query and the *specific documents available*, generate a JSON object that contains a detailed and realistic plan. The plan must have three parts:

1.  `analysis_goal`: A clear, one-sentence description of what the final report should accomplish. This will be the main instruction for the final answer synthesis.
2.  `sections_to_retrieve`: A list of the specific `section_id` numbers from the "Available Document Sections" that are absolutely necessary to achieve the `analysis_goal`. Be selective; only choose the most relevant sections.
3.  `extraction_checklist`: A detailed, point-by-point checklist of the specific information that needs to be extracted. Each item in the checklist must be an object with two keys:
    - `task`: A string describing the specific data point or summary to extract.
    - `type`: A string categorizing the task. Use **'table_extraction'** for tasks requiring precise data points likely found in financial tables (e.g., Net Income, Revenue, specific loan amounts). Use **'narrative_summary'** for tasks requiring summarization of prose or qualitative information (e.g., "key drivers for performance," "risk factors").

**Example Output:**
{{
  "analysis_goal": "A comparative summary of the financial performance and risk profiles of BAC and JPM for Q2 2025.",
  "sections_to_retrieve": [5348, 5353, 3781, 3784],
  "extraction_checklist": [
    {{
      "task": "Extract the Net Income, Revenue, and EPS for each company for Q2 2025.",
      "type": "table_extraction"
    }},
    {{
      "task": "Summarize the key drivers for revenue and expense changes and any forward-looking guidance.",
      "type": "narrative_summary"
    }},
    {{
      "task": "Summarize the top 3 disclosed risks for each company for the quarter.",
      "type": "narrative_summary"
    }}
  ]
}}

You MUST provide your response as a single, valid JSON object with these three keys, and nothing else.
"""
        try:
            response = self.llm_client.chat.completions.create(
                model=None,
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"}
            )
            raw_response = response.choices[0].message.content
            logging.info(f"LLM extraction guide response: {raw_response}")
            
            # Basic validation to ensure the response is a dict with the right keys
            plan = json.loads(raw_response)
            if all(key in plan for key in ["analysis_goal", "sections_to_retrieve", "extraction_checklist"]):
                # Advanced validation for the new checklist structure
                if isinstance(plan["extraction_checklist"], list) and all(
                    isinstance(item, dict) and 'task' in item and 'type' in item
                    for item in plan["extraction_checklist"]
                ):
                    plan["plan_type"] = "content_extraction" # Add our internal type
                    return plan
                else:
                    logging.error("LLM-generated extraction_checklist is not in the correct format.")
                    return None
            else:
                logging.error("LLM-generated plan is missing required keys.")
                return None
        except Exception as e:
            logging.error(f"Error during LLM plan generation: {e}")
            return None

    def _llm_extract_company(self, query: str, all_companies: List[str]) -> List[str]:
        """
        Uses an LLM to extract the company ticker from a query, handling synonyms.
        """
        prompt = f"""
You are an expert entity extractor. Your task is to identify which company from a provided list is mentioned in the user's query. The user may use full names, abbreviations, or tickers.

**List of Available Companies:**
{json.dumps(all_companies)}

**User Query:**
"{query}"

**Instructions:**
1. Read the user query carefully.
2. Compare the company mentioned in the query against the "List of Available Companies".
3. Identify the official company ticker from the list that corresponds to the company in the query. For example, if the query says "JP Morgan", and the list contains "JPM", you must identify "JPM".
4. If no company from the list is mentioned, return an empty list.
5. If the query asks for "all companies" or similar, return the entire list of available companies.

You MUST provide your response as a single, valid JSON object with a single key "companies", and nothing else.
**Output Format:**
{{
  "companies": ["ticker_1", "ticker_2", ...]
}}
"""
        try:
            response = self.llm_client.chat.completions.create(
                model=None,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": f"Query: {query}"}],
                response_format={"type": "json_object"}
            )
            raw_response = response.choices[0].message.content
            logging.info(f"LLM company extraction response: {raw_response}")
            
            try:
                data = json.loads(raw_response)
            except json.JSONDecodeError:
                logging.warning("LLM company extraction response was not valid JSON. Attempting to extract from text.")
                match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if match:
                    json_str = match.group()
                    data = json.loads(json_str)
                else:
                    raise ValueError("No JSON object found in LLM response.")

            found_companies = data.get("companies", [])
            valid_companies = [c for c in found_companies if c in all_companies]
            
            if len(found_companies) != len(valid_companies):
                logging.warning(f"LLM returned companies not in the master list: {set(found_companies) - set(valid_companies)}")

            return valid_companies
        except Exception as e:
            logging.error(f"Error during LLM company extraction: {e}")
            return []

    def _llm_extract_context_entities(self, query: str, company_data: dict) -> Dict[str, list]:
        """
        Uses LLM to extract year, quarter, and doc type, grounded by available data.
        """
        available_years = list(company_data.get("actual_data", {}).keys())
        available_doc_types = sorted(list(set(
            doc_type
            for year_data in company_data.get("actual_data", {}).values()
            for quarter_data in year_data.values()
            for doc_type in quarter_data
        )))
        
        prompt = f"""
You are an expert entity extractor. Your job is to independently identify the year, quarter, and document type from a user's query, based on available data.

**Available Data for the company:**
- Years: {json.dumps(available_years)}
- Document Types: {json.dumps(available_doc_types)}

**User Query:**
"{query}"

**Instructions:**
1.  **Year Extraction:** Look for a 4-digit year in the query. It must be one of the "Available Years". If not found, return an empty list for `years`. You can also extract a range of years.
2.  **Quarter Extraction:** Look for a quarter mention (e.g., "Q1", "q2", "3rd quarter"). Extract only the quarter label (e.g., "Q1", "Q2", "Q3", "Q4"). If not found, return an empty list for `quarters`.
3.  **Document Type Extraction:** Look for a document type mention (e.g., "10-K", "10-Q", "annual report"). It must be one of the "Available Document Types".
    -   "annual report" or "annual filing" maps to "10-K".
    -   "quarterly report" or "quarterly filing" maps to "10-Q".

**CRITICAL RULE:** The decision for each entity MUST be independent. Specifically, **you must NOT infer a document type** just because a quarter is mentioned. If the query does not explicitly state a document type like '10-K' or 'annual report', the `document_types` field MUST be an empty list `[]`.

You MUST provide your response as a single, valid JSON object, and nothing else.
**Output Format:**
{{
  "years": [YYYY],
  "quarters": ["Q#"],
  "document_types": ["doc_type"]
}}
"""
        try:
            response = self.llm_client.chat.completions.create(
                model=None,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": f"Query: {query}"}],
                response_format={"type": "json_object"}
            )
            raw_response = response.choices[0].message.content
            logging.info(f"LLM context extraction response: {raw_response}")
            
            try:
                data = json.loads(raw_response)
            except json.JSONDecodeError:
                logging.warning("LLM context extraction response was not valid JSON. Attempting to extract from text.")
                match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if match:
                    json_str = match.group()
                    data = json.loads(json_str)
                else:
                    raise ValueError("No JSON object found in LLM response.")

            validated_data = {
                "years": [y for y in self._sanitize_llm_list_output(data.get("years", [])) if y in available_years],
                "quarters": [q.upper() for q in self._sanitize_llm_list_output(data.get("quarters", [])) if isinstance(q, str) and re.match(r'^Q[1-4]$', q, re.IGNORECASE)],
                "document_types": [dt for dt in self._sanitize_llm_list_output(data.get("document_types", [])) if dt in available_doc_types]
            }
            return validated_data
            
        except Exception as e:
            logging.error(f"Error during LLM context extraction: {e}")
            return {"years": [], "quarters": [], "document_types": []}

    def _get_company_focused_data(self, company: str) -> dict:
        """
        Get real year/quarter/document type combinations for the specific company.
        """
        query = """
        MATCH (c:Company {name: $company})-[:HAS_YEAR]->(y:Year)-[:HAS_QUARTER]->(q:Quarter)-[:HAS_DOC]->(d:Document)
        RETURN y.value as year, q.label as quarter, d.document_type as doc_type
        ORDER BY y.value DESC, q.label
        """
        
        result = self.neo4j_executor.run_cypher_query(query, {"company": company})
        
        focused_data = {"company": company, "actual_data": {}}
        for record in result:
            year, quarter, doc_type = record['year'], record['quarter'], record['doc_type']
            focused_data["actual_data"].setdefault(year, {}).setdefault(quarter, []).append(doc_type)
        
        return focused_data
    
    def _get_focused_sections(self, company: str, entities: dict) -> List[dict]:
        """
        Builds and executes a precise Cypher query to fetch only the sections that
        match the filters extracted from the user's query, using the correct graph schema.
        """
        logging.info(f"Getting focused sections for {company} with entities: {entities}")

        # Base of the Cypher query matching the actual graph structure
        cypher_query = """
        MATCH (c:Company {name: $company})-[:HAS_YEAR]->(y:Year)-[:HAS_QUARTER]->(q:Quarter)-[:HAS_DOC]->(d:Document)-[:HAS_SECTION]->(s:Section)
        """
        
        # Start building the WHERE clause and parameters
        where_clauses = []
        params = {"company": company}

        # Dynamically add filters based on extracted entities
        if entities.get("years"):
            where_clauses.append("y.value IN $years")
            params["years"] = entities["years"]
        
        if entities.get("quarters"):
            where_clauses.append("q.label IN $quarters")
            params["quarters"] = entities["quarters"]
            
        if entities.get("doc_types"):
            where_clauses.append("d.document_type IN $doc_types")
            params["doc_types"] = entities["doc_types"]
            
        # Append WHERE clauses if any exist
        if where_clauses:
            cypher_query += "WHERE " + " AND ".join(where_clauses)
            
        # Finalize the query to return all necessary data
        cypher_query += """
        RETURN
            id(s) as section_id,
            s.name as section_name,
            d.document_type as doc_type,
            y.value as year,
            q.label as quarter
        ORDER BY y.value DESC, q.label DESC
        """
        
        logging.info(f"Constructed precise Cypher query for pre-filtering:\n{cypher_query}\nParams: {params}")
        
        # Execute the query
        results = self.neo4j_executor.run_cypher_query(cypher_query, params)
        
        if not results:
            logging.warning("Precise pre-filtering query returned no sections.")
        
        return results
    
    def _sanitize_llm_list_output(self, value) -> list:
        """
        Robustly handles LLM output that might be a string representation of a list.
        """
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                # Attempt to parse it as JSON
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Fallback for simple strings that aren't JSON, e.g., "[]"
                cleaned_value = value.strip().replace('[', '').replace(']', '').replace('"', '').replace("'", "")
                if not cleaned_value:
                    return []
                # Split by comma and strip spaces
                return [item.strip() for item in cleaned_value.split(',')]
        return []

    def _llm_classify_and_build_metadata_query(self, query: str) -> Optional[dict]:
        """
        Uses an LLM call to classify if a query is "metadata" or "content".
        If it is, it generates the appropriate Cypher query.
        """
        prompt = self._build_metadata_prompt_builtin()
        
        try:
            response = self.llm_client.chat.completions.create(
                model=None, # Use default from client
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": f"Query: {query}"}],
                response_format={"type": "json_object"}
            )
            raw_response = response.choices[0].message.content
            logging.info(f"LLM metadata classification response: {raw_response}")
            return json.loads(raw_response)
        except Exception as e:
            logging.error(f"Error during metadata classification: {e}")
            return None # Return None on failure to allow fallback to content planning

    def _build_metadata_prompt_builtin(self) -> str:
        """Builds the prompt for the metadata classification LLM call."""
        return """
You are a query classifier and builder for a financial graph database.
Your task is to determine if a user's query is a "metadata query" or a "content query".

- **Metadata Query:** Asks for information ABOUT the dataset structure. It does NOT ask for information from inside a document.
  Examples: "What companies are in the dataset?", "Which years are available for ZION?", "List the documents for BAC in Q1 2023".
- **Content Query:** Asks for information FROM WITHIN a document, such as a summary, a specific section, or a report.
  Examples: "What were the risk factors for JPM in 2022?", "Show me the MD&A for PNC's latest 10-K", "Give me a summary of BAC in Q1 2025", "Create a detailed summary report for all sections of ZION's 2023 10-K".

**Instructions:**
1.  Analyze the user's query.
2.  If it is a **Metadata Query**:
    a. Set `query_type` to "metadata".
    b. Construct the appropriate Cypher query to answer it.
    c. Set `response_format` to "list_of_strings".
    d. Provide a brief `human_readable_answer`.
3.  If it is a **Content Query** (including requests for summaries, reports, or specific sections):
    a. Set `query_type` to "content".
    b. Leave `cypher_query`, `response_format`, and `human_readable_answer` as `null`.

**Available Schema:**
- Companies are `(:Company {name: "TICKER"})`
- Years are `(:Year {value: YYYY})`
- Quarters are `(:Quarter {label: "Q#"})`
- Documents are `(:Document {document_type: "10-K", filing_date: "YYYY-MM-DD"})`
- Relationships are `(Company)-[:HAS_YEAR]->(Year)-[:HAS_QUARTER]->(Quarter)-[:HAS_DOC]->(Document)`

You MUST provide your response as a single, valid JSON object, and nothing else.

**Example 1: Metadata Query**
- User Query: "what are the companies in the dataset?"
- JSON Output:
{
  "query_type": "metadata",
  "cypher_query": "MATCH (n:Company) RETURN DISTINCT n.name AS value ORDER BY value",
  "response_format": "list_of_strings",
  "human_readable_answer": "Here are the companies in the dataset:"
}

**Example 2: Content Query**
- User Query: "what were the risks for zion in 2023"
- JSON Output:
{
  "query_type": "content",
  "cypher_query": null,
  "response_format": null,
  "human_readable_answer": null
}

**Example 3: Content Query (summary)**
- User Query: "BAC 2025 q1 all sections, create a detailed summary report?"
- JSON Output:
{
  "query_type": "content",
  "cypher_query": null,
  "response_format": null,
  "human_readable_answer": null
}
"""

def create_focused_query_plan(llm_client, neo4j_executor, query: str) -> List[dict]:
    """
    Standalone function to create a query plan using the ImprovedQueryPlanner.
    This is for backwards compatibility with the old agent structure if needed.
    """
    planner = ImprovedQueryPlanner(llm_client, neo4j_executor)
    return planner.create_plan(query) 