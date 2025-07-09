# GraphDB SEC Agent

This repository contains a sophisticated agent-based system for querying and analyzing SEC filings. The system leverages a knowledge graph and vector embeddings to provide intelligent, context-aware answers to complex financial questions. It is designed to be a powerful tool for financial analysts, researchers, and developers who need to extract actionable insights from large volumes of unstructured SEC data.

The architecture is divided into three core stages: Data Ingestion, Data Pipeline, and a multi-agent system for query execution.

## Project Setup

Follow these steps to set up and run the project locally.

### 1. Clone the Repository

```bash
git clone https://github.com/algowizzzz/graphdb_agent_sec.git
cd graphdb_agent_sec
```

### 2. Install Dependencies

It is recommended to use a virtual environment.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root and add your API keys. This file is ignored by Git, so your keys will remain private.

```env
OPENAI_API_KEY="your-openai-api-key"
ANTHROPIC_API_KEY="your-anthropic-api-key"
NEO4J_URI="your-neo4j-uri"
NEO4J_USERNAME="your-neo4j-username"
NEO4J_PASSWORD="your-neo4j-password"
```

---

## Technical Documentation

This section provides a detailed overview of the core components, their roles, and how they interact.

### 1. `final_data_ingestion_standardisation`

This module is responsible for downloading SEC filings from the Edgar API and standardizing them into a consistent JSON format.

-   **Input**: `tickers.txt` - A list of company tickers to process.
-   **Output**: `output_sec_api/` - A directory containing the downloaded and standardized SEC filings in JSON format.

#### Key Scripts:

-   `main.py`: The entry point for the data ingestion process. It orchestrates the downloading and processing of filings.
-   `discover_filings.py`: Queries the Edgar API to discover available filings for the specified tickers and date ranges.
-   `process_filing.py`: Takes the discovered filings, downloads the full content, extracts relevant sections (like "Item 1A. Risk Factors"), and saves them as structured JSON files.

### 2. `data_pipeline`

This module processes the standardized JSON filings to build the knowledge graph and generate vector embeddings for semantic search.

-   **Input**: `zion_10k_md&a_chunked/` - This directory contains pre-processed and chunked sections of 10-K filings, which are used as the source for building the graph and embeddings.
-   **Output**:
    -   Neo4j Database: Populated with nodes and relationships representing the financial data.
    -   `faiss_index.bin` and `faiss_index_zion_mda_mapping.json`: The FAISS vector index and its corresponding mapping file for fast semantic search.

#### Key Scripts:

-   `chunker.py`: Chunks the large text sections from the filings into smaller, more manageable pieces for embedding.
-   `extract_embeddings.py`: Generates vector embeddings for the text chunks using a pre-trained language model.
-   `create_graph_v3.py`: Constructs the knowledge graph by creating nodes (e.g., Company, Document, Section) and relationships from the structured data.
-   `build_faiss_index.py`: Builds a FAISS index from the generated embeddings to enable efficient similarity searches.

### 3. Core Agents and Components (`core_agents` & `agent_components`)

This is the brain of the system, where user queries are interpreted, planned, and executed. It uses a multi-agent approach to handle different aspects of the query process.

#### Agent Components (`agent_components`):

-   `unified_llm_client.py`: A centralized client for interacting with different LLMs (e.g., OpenAI, Anthropic).
-   `vector_db.py`: Manages interactions with the FAISS vector database to find contextually relevant text chunks.
-   `cypher_builder.py`: Constructs complex Cypher queries to be executed against the Neo4j knowledge graph based on the user's question.
-   `neo4j_executor.py`: Executes the generated Cypher queries on the Neo4j database and retrieves the results.
-   `improved_query_planner.py`: The central planner that decomposes a user's query into a sequence of steps. It decides whether to query the vector database, the knowledge graph, or both.
-   `answer_synthesizer.py`: Synthesizes the final answer by combining the information retrieved from the vector database and the knowledge graph into a coherent, human-readable response.
-   `answer_critic.py`: Reviews the synthesized answer for accuracy, completeness, and relevance before presenting it to the user.
-   `output_formatter.py`: Formats the final output.

#### Core Agents (`core_agents`):

-   `scout_agent.py`: The first point of contact for a user query. It performs an initial analysis of the question and the available data to determine the best path for answering it.
-   `query_agent.py`: The main agent that orchestrates the entire query process. It uses the `improved_query_planner` to create a plan, executes the plan using the various components, and then uses the `answer_synthesizer` and `answer_critic` to generate the final response.

### High-Level Agent Workflow:

1.  A user submits a query (e.g., "What are the main risk factors for Bank of America in 2023?").
2.  The `Query Agent` receives the query.
3.  The `Improved Query Planner` breaks down the query into a multi-step plan. This might involve:
    a.  First, searching the `Vector DB` to find relevant text chunks from SEC filings.
    b.  Then, using the retrieved context to build a precise Cypher query with the `Cypher Builder`.
4.  The `Neo4j Executor` runs the Cypher query against the knowledge graph to get structured data.
5.  The `Answer Synthesizer` combines the results from the vector search and the graph query to formulate a comprehensive answer.
6.  The `Answer Critic` evaluates the answer for quality.
7.  The final, formatted answer is returned to the user. 