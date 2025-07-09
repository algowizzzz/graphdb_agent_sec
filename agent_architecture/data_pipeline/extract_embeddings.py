import json
from neo4j import GraphDatabase

class EmbeddingExtractor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Connected to Neo4j.")

    def close(self):
        self.driver.close()
        print("Neo4j connection closed.")

    def fetch_and_save_section_texts(self, output_file='section_texts.json'):
        """
        Fetches all section texts from Neo4j and saves them to a JSON file.
        """
        text_map = {}
        query = "MATCH (s:Section) RETURN s.filename AS filename, s.text AS text"

        with self.driver.session() as session:
            print("Querying Neo4j for section filenames and text...")
            result = session.run(query)
            records = list(result)
            for record in records:
                filename = record["filename"]
                text = record["text"]
                if filename and text:
                    text_map[filename] = text
        
        print(f"Successfully fetched text for {len(text_map)} sections.")

        if text_map:
            with open(output_file, 'w') as f:
                json.dump(text_map, f, indent=2)
            print(f"Section texts saved to '{output_file}'.")
        else:
            print("No text data found or retrieved.")

if __name__ == "__main__":
    # --- Connection Details ---
    URI = "neo4j://localhost:7687"
    USER = "neo4j"
    PASSWORD = "newpassword"
    
    # --- Output File ---
    OUTPUT_FILE = "zion_mda_texts.json"

    extractor = EmbeddingExtractor(URI, USER, PASSWORD)
    extractor.fetch_and_save_section_texts(output_file=OUTPUT_FILE)
    extractor.close()