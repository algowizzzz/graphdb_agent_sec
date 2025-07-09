import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def build_and_save_faiss_index(text_data_path, vector_index_path, model_name):
    """
    Builds a FAISS index from text data and saves it.
    """
    logging.info(f"Loading text data from '{text_data_path}'...")
    try:
        with open(text_data_path, 'r') as f:
            text_map = json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: Text data file not found at '{text_data_path}'. Aborting.")
        return

    if not text_map:
        logging.warning("Text data file is empty. No index will be built.")
        return

    filenames = list(text_map.keys())
    texts = list(text_map.values())

    logging.info(f"Loading sentence transformer model '{model_name}'...")
    model = SentenceTransformer(model_name)

    logging.info("Generating embeddings for the texts...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    
    if embeddings.size == 0:
        logging.error("Embedding generation resulted in an empty array. Aborting.")
        return
        
    embedding_dim = embeddings.shape[1]
    logging.info(f"Embeddings generated with dimension: {embedding_dim}")

    logging.info("Building the FAISS index...")
    index = faiss.IndexFlatL2(embedding_dim)
    index = faiss.IndexIDMap(index)
    
    ids = np.array(range(len(filenames)))
    index.add_with_ids(embeddings.astype('float32'), ids)

    logging.info(f"FAISS index built successfully with {index.ntotal} vectors.")

    # Save the index
    faiss.write_index(index, vector_index_path)
    logging.info(f"FAISS index saved to '{vector_index_path}'.")

    # Save the filename mapping
    mapping_path = os.path.splitext(vector_index_path)[0] + '_mapping.json'
    with open(mapping_path, 'w') as f:
        json.dump(filenames, f)
    logging.info(f"Filename mapping saved to '{mapping_path}'.")

def main():
    TEXT_DATA_PATH = "zion_mda_texts.json"
    VECTOR_INDEX_PATH = "faiss_index_zion_mda.bin"
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    
    logging.info("--- Starting FAISS Index Building Process ---")
    build_and_save_faiss_index(
        text_data_path=TEXT_DATA_PATH,
        vector_index_path=VECTOR_INDEX_PATH,
        model_name=MODEL_NAME
    )
    logging.info("--- FAISS Index Building Process Finished ---")

if __name__ == "__main__":
    main() 