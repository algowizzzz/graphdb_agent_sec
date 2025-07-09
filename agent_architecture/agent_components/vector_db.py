import faiss
import numpy as np
import os
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VectorDB:
    """A FAISS-based vector database for similarity search."""

    def __init__(self):
        """Initializes the VectorDB."""
        self.index_path = "faiss_index_zion_mda.bin"
        self.id_map_path = "faiss_index_zion_mda_mapping.json"
        self.index = None
        self.index_to_vertex_id = []
        # Automatically load the index upon initialization
        self.load_index()

    def build_index(self, section_data: list):
        """
        Builds and saves a new FAISS index from section data.
        """
        if not section_data:
            logging.error("Cannot build index: provided section data is empty.")
            return

        logging.info(f"Building FAISS index with {len(section_data)} vectors...")
        
        embeddings = np.array([item['embedding'] for item in section_data]).astype('float32')
        dimension = embeddings.shape[1]
        
        self.index = faiss.IndexFlatL2(dimension)
        self.index_to_vertex_id = [item['id'] for item in section_data]
        self.index.add(embeddings)
        
        logging.info(f"FAISS index built successfully. Total vectors indexed: {self.index.ntotal}")
        self.save_index()

    def save_index(self):
        """Saves the FAISS index and the ID map to disk."""
        logging.info(f"Saving FAISS index to {self.index_path}")
        faiss.write_index(self.index, self.index_path)
        
        with open(self.id_map_path, 'w') as f:
            json.dump(self.index_to_vertex_id, f)
        logging.info("Index and ID map saved.")

    def load_index(self):
        """Loads the FAISS index and ID map from disk."""
        try:
            logging.info(f"Loading FAISS index from {self.index_path}")
            self.index = faiss.read_index(self.index_path)
            
            with open(self.id_map_path, 'r') as f:
                self.index_to_vertex_id = json.load(f)
            
            logging.info(f"FAISS index with {self.index.ntotal} vectors loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load FAISS index: {e}")
            self.index = None
            self.index_to_vertex_id = []

    def search(self, query_embedding: np.ndarray, k: int) -> tuple[list, list]:
        """
        Searches the FAISS index for the k-nearest neighbors to the query embedding.
        """
        if self.index is None:
            logging.error("Cannot search: FAISS index is not loaded or built.")
            return [], []

        query_embedding = np.array([query_embedding]).astype('float32')
        distances, indices = self.index.search(query_embedding, k)
        
        # Also, FAISS can return -1 for indices if it can't find k neighbors.
        valid_indices = indices[0][indices[0] != -1]
        
        # Map the FAISS indices back to our original vertex IDs
        # Use .size to check for emptiness in a numpy array
        if valid_indices.size > 0:
            section_ids = [self.index_to_vertex_id[i] for i in valid_indices]
            return distances[0][indices[0] != -1].tolist(), section_ids
        else:
            return [], [] 