import json
import glob
import re
import os
from collections import defaultdict
from neo4j import GraphDatabase

class Neo4jGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def clear_database(self):
        with self.driver.session() as session:
            session.execute_write(self._clear_db)

    @staticmethod
    def _clear_db(tx):
        tx.run("MATCH (n) DETACH DELETE n")

    def create_constraints_and_indexes(self):
        with self.driver.session() as session:
            session.execute_write(self._create_constraints_and_indexes_tx)

    @staticmethod
    def _create_constraints_and_indexes_tx(tx):
        # Uniqueness constraints for entities
        tx.run("CREATE CONSTRAINT unique_domain IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE")
        tx.run("CREATE CONSTRAINT unique_subdomain IF NOT EXISTS FOR (s:Subdomain) REQUIRE s.name IS UNIQUE")
        tx.run("CREATE CONSTRAINT unique_company IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE")
        
        # Composite uniqueness constraints for contextual entities
        tx.run("CREATE CONSTRAINT unique_year IF NOT EXISTS FOR (y:Year) REQUIRE (y.company, y.value) IS UNIQUE")
        tx.run("CREATE CONSTRAINT unique_quarter IF NOT EXISTS FOR (q:Quarter) REQUIRE (q.company, q.year, q.label) IS UNIQUE")
        
        # Uniqueness for documents and sections
        tx.run("CREATE CONSTRAINT unique_document IF NOT EXISTS FOR (d:Document) REQUIRE d.filename IS UNIQUE")
        tx.run("CREATE CONSTRAINT unique_section IF NOT EXISTS FOR (s:Section) REQUIRE s.filename IS UNIQUE")
        
        # Recommended composite index for efficient lookups
        tx.run("""
        CREATE INDEX doc_lookup IF NOT EXISTS FOR (d:Document) 
        ON (d.company, d.year, d.quarter, d.document_type)
        """)

    def build_graph_from_files(self, data_dir, file_pattern):
        path = os.path.join(data_dir, file_pattern)
        files = glob.glob(path)
        
        grouped_files = defaultdict(list)
        # Regex to parse the new filename format, now handling optional "_part_X"
        pattern = re.compile(r"external_SEC_([A-Z]+)_([0-9A-Z-]+)_(\d{4})_(q\d)_(.*?)(_part_\d+)?\.json", re.IGNORECASE)

        for f_path in files:
            basename = os.path.basename(f_path)
            match = pattern.search(basename)
            if match:
                company, doc_type, year, quarter, _, _ = match.groups()
                # Normalize key components for consistent grouping
                key = (company.upper(), doc_type.upper(), year, quarter.upper())
                grouped_files[key].append(f_path)
        
        with self.driver.session() as session:
            for (company, doc_type, year, quarter), filenames in grouped_files.items():
                # Define the parent Document's unique filename
                document_filename = f"SEC_{company}_{year}_{quarter}_{doc_type}"
                
                # Use metadata from the first file in the group to create the parent doc
                with open(filenames[0], 'r') as f:
                    record = json.load(f)
                    
                    # Prepare a clean parameter map for the document query
                    doc_params = {
                        "domain": record.get("domain"),
                        "subdomain": record.get("subdomain"),
                        "company": company,
                        "year": int(year),
                        "quarter_label": quarter,
                        "doc_type": doc_type,
                        "filename": document_filename
                    }
                
                # Create the hierarchy up to the Document node
                session.execute_write(self._create_document_tx, doc_params)

                # Process each file in the group as a Section
                for f_path in filenames:
                    with open(f_path, 'r') as f:
                        record = json.load(f)
                        basename = os.path.basename(f_path)
                        
                        # Prepare a clean parameter map for the section query
                        section_params = {
                            "doc_filename": document_filename,
                            "section_filename": basename,
                            "section_name": record.get("section", "Unnamed Section"),
                            "text": record.get("text", "")
                        }
                        session.execute_write(self._create_section_tx, section_params)

    @staticmethod
    def _create_document_tx(tx, params):
        query = """
        MERGE (domain:Domain {name: $domain})
        MERGE (domain)-[:HAS_SUBDOMAIN]->(subdomain:Subdomain {name: $subdomain})
        MERGE (subdomain)-[:HAS_COMPANY]->(company:Company {name: $company})
        MERGE (company)-[:HAS_YEAR]->(year:Year {company: $company, value: $year, name: toString($year)})
        MERGE (year)-[:HAS_QUARTER]->(quarter:Quarter {company: $company, year: $year, label: $quarter_label, name: $quarter_label})
        
        MERGE (quarter)-[:HAS_DOC]->(doc:Document {filename: $filename})
        ON CREATE SET
            doc.name = $doc_type,
            doc.document_type = $doc_type,
            doc.company = $company,
            doc.year = $year,
            doc.quarter = $quarter_label
        """
        tx.run(query, **params)

    @staticmethod
    def _create_section_tx(tx, params):
        # Clean the text by replacing newlines with spaces
        clean_text = params.get("text", "").replace('\n', ' ')

        query = """
        MATCH (doc:Document {filename: $doc_filename})
        MERGE (section:Section {filename: $section_filename})
        ON CREATE SET
            section.name = $section_name,
            section.section = $section_name,
            section.text = $clean_text
        ON MATCH SET
            section.text = $clean_text
        MERGE (doc)-[:HAS_SECTION]->(section)
        """
        # Add the cleaned text to the parameters
        params["clean_text"] = clean_text
        tx.run(query, **params)

    def create_horizontal_links(self):
        with self.driver.session() as session:
            session.execute_write(self._create_horizontal_links_tx)
    
    @staticmethod
    def _create_horizontal_links_tx(tx):
        # Link Years chronologically for each company
        tx.run("""
        MATCH (c:Company)-[:HAS_YEAR]->(y:Year)
        WITH c, y ORDER BY y.value
        WITH c, collect(y) AS years
        UNWIND range(0, size(years) - 2) AS i
        WITH years[i] AS y1, years[i+1] AS y2
        MERGE (y1)-[:NEXT_YEAR]->(y2)
        """)

        # Link Quarters chronologically for each Year
        tx.run("""
        MATCH (y:Year)-[:HAS_QUARTER]->(q:Quarter)
        WITH y, q ORDER BY q.label
        WITH y, collect(q) AS quarters
        UNWIND range(0, size(quarters) - 2) AS i
        WITH quarters[i] AS q1, quarters[i+1] AS q2
        MERGE (q1)-[:NEXT_QUARTER]->(q2)
        """)

        # Link similar Documents across companies (same period and type)
        tx.run("""
        MATCH (d:Document)
        WITH d.year AS year, d.quarter AS quarter, d.document_type as doc_type, collect(d) AS documents
        WHERE size(documents) > 1
        UNWIND range(0, size(documents) - 2) AS i
        WITH documents[i] AS d1, documents[i+1] AS d2
        MERGE (d1)-[:SIMILAR_DOC]->(d2)
        """)


if __name__ == "__main__":
    # --- Connection details ---
    URI = "neo4j://localhost:7687"
    USER = "neo4j"
    PASSWORD = "newpassword"

    # --- Data location ---
    DATA_DIRECTORY = "zion_10k_md&a_chunked"
    FILE_PATTERN = "*.json"

    graph = Neo4jGraph(URI, USER, PASSWORD)

    print("Clearing the database...")
    graph.clear_database()
    
    print("Creating constraints and indexes...")
    graph.create_constraints_and_indexes()

    print(f"Building graph from files in '{DATA_DIRECTORY}'...")
    graph.build_graph_from_files(DATA_DIRECTORY, FILE_PATTERN)

    print("Creating horizontal links (time-series and comparative)...")
    graph.create_horizontal_links()

    print("Graph creation complete.")
    graph.close()