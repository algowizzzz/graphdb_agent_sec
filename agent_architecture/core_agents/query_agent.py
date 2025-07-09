import os
import json
import logging
import sys
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
from typing import List

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from our unified system
from config import get_config, ConfigManager
from agent_components.unified_llm_client import UnifiedLLMClient
from agent_components.neo4j_executor import Neo4jExecutor
from agent_components.improved_query_planner import ImprovedQueryPlanner
from agent_components.answer_synthesizer import map_summarize_sections, reduce_and_synthesize_answer
from agent_components.answer_critic import evaluate_and_suggest_improvements
from agent_components.cypher_builder import CypherQueryBuilder
from agent_components.vector_db import VectorDB

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Neo4jQueryAgent:
    """
    Clean, production-ready Neo4j Query Agent with streamlined architecture.
    Uses the new ImprovedQueryPlanner for efficient, single-step planning and metadata queries.
    """

    def __init__(self, config=None, llm_client=None):
        """
        Initialize the Neo4jQueryAgent.
        """
        logging.info("Initializing Neo4jQueryAgent with ImprovedQueryPlanner")
        
        self.config = config or get_config()
        if not ConfigManager.validate_config(self.config):
            raise ValueError("Invalid configuration provided")
        
        self.llm_client = llm_client or UnifiedLLMClient(self.config.llm)
        self.model = SentenceTransformer(self.config.embedding_model)
        self.vector_db = VectorDB()
        self.cypher_builder = CypherQueryBuilder(model=self.model, vector_db=self.vector_db)
        self.neo4j_executor = Neo4jExecutor(
            uri=self.config.database.uri, 
            user=self.config.database.user, 
            password=self.config.database.password
        )
        self.query_planner = ImprovedQueryPlanner(self.llm_client, self.neo4j_executor)
        
        logging.info("Neo4jQueryAgent initialized successfully")

    def run(self, query: str) -> str:
        """
        Execute the streamlined workflow using the versatile ImprovedQueryPlanner.
        Handles both metadata queries and content-focused queries using a dynamic,
        grounded extraction plan.
        """
        logging.info(f"🚀 Processing query with dynamic extraction plan: '{query}'")
        
        try:
            # === STAGE 1: DYNAMIC PLAN GENERATION ===
            # The new planner returns a single, comprehensive JSON object that guides the entire process.
            plan = self.query_planner.create_plan(query)

            if not plan:
                return "I'm sorry, I couldn't create a plan to answer your query. This could be because no relevant documents were found for the entities you mentioned. Please try rephrasing."

            # === STAGE 2: EXECUTE PLAN ===
            plan_type = plan.get('plan_type')
            logging.info(f"--- Executing Plan (Type: {plan_type}) ---")

            # Case 1: The plan is a direct metadata query.
            if plan_type == "metadata":
                cypher_query = plan.get("cypher_query")
                if not cypher_query:
                    logging.warning("Metadata plan is missing the cypher_query.")
                    return "I identified this as a metadata query, but failed to construct the database query."
                
                # Execute and get raw results, which are the final answer.
                results = self.neo4j_executor.run_cypher_query(cypher_query, {})
                return json.dumps(results, indent=2)

            # Case 2: The plan is a content extraction workflow.
            elif plan_type == "content_extraction":
                section_ids = plan.get("sections_to_retrieve")
                if not section_ids:
                    logging.warning("Content extraction plan has no sections to retrieve.")
                    return "I created a plan, but it did not specify which document sections to analyze. Please try your query again."
                
                # Retrieve the full text for the specified sections
                logging.info(f"Retrieving text for {len(section_ids)} specified section(s)...")
                # This query assumes `s.text` holds the text and `s.name` the section name.
                # It's crucial this matches your graph schema.
                cypher_query = """
                MATCH (s:Section) WHERE id(s) IN $section_ids
                RETURN s.text AS text, s.name as filename
                """
                results = self.neo4j_executor.run_cypher_query(cypher_query, params={"section_ids": section_ids})

                if not results:
                    logging.warning("No text could be retrieved for the specified section IDs.")
                    return "I found the right documents, but I couldn't extract any text from them. The data might be missing or in an unexpected format."

                # === STAGE 3: SYNTHESIZE FINAL ANSWER (with Map-Reduce and Guided Extraction) ===
                logging.info("--- Preparing for Final Answer Synthesis ---")
                
                # The extraction checklist and analysis goal come directly from our dynamic plan
                extraction_checklist = plan.get("extraction_checklist")
                analysis_goal = plan.get("analysis_goal")

                # The map-reduce logic remains, but it's now guided by the extraction checklist
                synthesis_input = self._guided_map_reduce(results, query, extraction_checklist)

                # The final synthesis step is now guided by the analysis goal
                final_answer = reduce_and_synthesize_answer(
                    llm_client=self.llm_client,
                    query=query,
                    results=synthesis_input,
                    analysis_goal=analysis_goal
                )
                
                logging.info("Query processed successfully")
                return final_answer
            
            else:
                logging.error(f"Unknown plan type encountered: {plan_type}")
                return "I encountered an unknown plan type and could not proceed."
            
        except Exception as e:
            logging.error(f"Error processing query: {e}", exc_info=True)
            return f"I encountered an unexpected error while processing your query: {str(e)}"

    def _guided_map_reduce(self, documents: List[dict], user_query: str, extraction_checklist: List[dict]) -> List[dict]:
        """
        Performs the map-reduce process, passing the dynamic extraction checklist
        to the mapping function.
        """
        TOKEN_ESTIMATE_PER_CHAR = 4
        MAX_CONTEXT_CHARACTERS = 180000 

        # Robustly calculate total characters, handling None values for text
        total_chars = sum(len(doc.get('text') or '') for doc in documents)
        
        # If context is too large, perform the "Map" step with the checklist
        if total_chars > MAX_CONTEXT_CHARACTERS:
            logging.warning(f"Context size ({total_chars} chars) exceeds threshold. Applying guided map-reduce summarization.")
            # Pass the checklist to the summarizer
            return map_summarize_sections(
                client=self.llm_client,
                documents=documents,
                user_query=user_query,
                extraction_checklist=extraction_checklist
            )
        
        logging.info("Context size is within limits. Proceeding with direct synthesis.")
        # If not too large, we still need to process it to get structured data
        return map_summarize_sections(
            client=self.llm_client,
            documents=documents,
            user_query=user_query,
            extraction_checklist=extraction_checklist
        )

    def close(self):
        """Close the connection to the Neo4j database."""
        if hasattr(self, 'neo4j_executor'):
            self.neo4j_executor.close()
            logging.info("Neo4j connection closed")

    def get_config_info(self) -> dict:
        """Get information about current configuration"""
        return {
            'llm_provider': self.config.llm.provider,
            'llm_model': self.config.llm.model,
            'embedding_model': self.config.embedding_model,
            'database_uri': self.config.database.uri,
            'llm_info': self.llm_client.get_provider_info()
        }


# Legacy compatibility wrapper
class QueryAgent:
    """
    Legacy compatibility wrapper for the new streamlined agent.
    """
    def __init__(self, neo4j_uri=None, neo4j_user=None, neo4j_password=None, 
                 openai_api_key=None, model_name=None, prompt_file=None, 
                 provider=None, model_tier='default'):
        
        config = get_config(provider, model_tier)
        
        if neo4j_uri: config.database.uri = neo4j_uri
        if neo4j_user: config.database.user = neo4j_user
        if neo4j_password: config.database.password = neo4j_password
        if openai_api_key and config.llm.provider == 'openai': config.llm.api_key = openai_api_key
        if model_name: config.embedding_model = model_name
        
        self.agent = Neo4jQueryAgent(config)
        logging.info(f"Legacy QueryAgent wrapper initialized with provider: {config.llm.provider}")

    def analyze_query(self, user_query, iteration_history=None):
        """Legacy method that uses the new streamlined workflow"""
        return self.agent.run(user_query)

    def close(self):
        self.agent.close()
        
    def get_config_info(self) -> dict:
        return self.agent.get_config_info()