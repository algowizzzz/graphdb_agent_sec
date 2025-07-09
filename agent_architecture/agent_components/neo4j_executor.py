from neo4j import GraphDatabase
import logging

class Neo4jExecutor:
    def __init__(self, uri: str, user: str, password: str):
        """
        Initializes the Neo4jExecutor.

        Args:
            uri (str): The Neo4j database URI.
            user (str): Database username.
            password (str): Database password.
        """
        print(f"Initializing Neo4jExecutor with URI: {uri}")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Neo4j driver created.")

    def run_cypher_query(self, query, params={}):
        """
        Executes a Cypher query with optional parameters.

        Args:
            query (str): The Cypher query string to execute.
            params (dict): A dictionary of parameters for the query.

        Returns:
            A list of result records.
        """
        print(f"\n--- EXECUTING CYPHER QUERY ---\n{query}\nwith params: {params}\n-----------------------------")
        try:
            with self.driver.session() as session:
                result = session.run(query, params)
                result_list = [record.data() for record in result]
                print(f"Query returned {len(result_list)} results.")
                
                # --- START OF NEW LOGGING ---
                # Unconditionally print the first result to inspect its raw structure.
                if result_list:
                    print("--- RAW FIRST RESULT ---")
                    print(result_list[0])
                    print(f"(Type: {type(result_list[0])})")
                    print("------------------------")
                # --- END OF NEW LOGGING ---

                return result_list
        except Exception as e:
            print(f"An error occurred while executing Cypher query: {e}")
            # In case of an error, return an empty list or handle as appropriate
            return []

    def get_graph_schema(self):
        """
        Fetches distinct values for key node properties using Cypher.
        """
        print("Fetching graph schema from Neo4j...")
        queries = {
            "companies": "MATCH (c:Company) RETURN DISTINCT c.name AS name",
            "years": "MATCH (y:Year) RETURN DISTINCT y.value AS name",
            "quarters": "MATCH (q:Quarter) RETURN DISTINCT q.label AS name",
            "sections": "MATCH (s:Section) RETURN DISTINCT s.section AS name"
        }
        details = {}
        for key, query in queries.items():
            result = self.run_cypher_query(query)
            # Extract the values from the result records
            if result:
                details[key] = sorted([record["name"] for record in result])
            else:
                details[key] = []
        
        print("Graph schema loaded.")
        return details

    def get_unique_values_for_property(self, label: str, prop: str) -> list:
        """
        Gets all unique non-null values for a given property of a given node label.
        """
        query = f"MATCH (n:{label}) RETURN DISTINCT n.{prop} AS value"
        try:
            results = self.run_cypher_query(query)
            return [record["value"] for record in results if record["value"] is not None]
        except Exception as e:
            print(f"Failed to get unique values for {label}.{prop}: {e}")
            return []

    def close(self):
        """Closes the connection to the Neo4j database."""
        self.driver.close()
        print("Neo4j connection closed.")


def run_cypher_query(driver, cypher_query, params={}):
    """
    Legacy function for backward compatibility.
    Executes a Cypher query against the Neo4j database using a provided driver.
    
    Args:
        driver: The Neo4j database driver instance.
        cypher_query (str): The Cypher query string to execute.
        params (dict): A dictionary of parameters for the query.

    Returns:
        A list of result records.
    """
    with driver.session() as session:
        result = session.run(cypher_query, params)
        return [record.data() for record in result]