import os
import json
import tiktoken
import re

def chunk_text_by_tokens(text, max_tokens):
    """Splits text into chunks of a maximum token size."""
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)

    chunks = []
    current_chunk = []
    current_count = 0

    for token in tokens:
        current_chunk.append(token)
        current_count += 1
        if current_count >= max_tokens:
            chunks.append(encoding.decode(current_chunk))
            current_chunk = []
            current_count = 0

    if current_chunk:
        chunks.append(encoding.decode(current_chunk))

    return chunks

def process_files(input_dir, output_dir, max_tokens=20000):
    """
    Processes JSON files from input_dir, splits them if they exceed max_tokens,
    and saves the results in output_dir.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if not filename.endswith('.json'):
            continue

        input_path = os.path.join(input_dir, filename)
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        text = data.get("text", "")
        encoding = tiktoken.get_encoding("cl100k_base")
        token_count = len(encoding.encode(text))

        if token_count > max_tokens:
            chunks = chunk_text_by_tokens(text, max_tokens)
            base_name = filename[:-5] # Remove .json

            for i, chunk_text in enumerate(chunks):
                new_data = data.copy()
                new_data["text"] = chunk_text

                # Update section name to reflect chunking
                original_section = new_data.get("section", "Unnamed Section")
                new_data["section"] = f"{original_section} (Part {i+1}/{len(chunks)})"

                new_filename = f"{base_name}_part_{i+1}.json"
                output_path = os.path.join(output_dir, new_filename)

                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, indent=4)
            print(f"Split {filename} into {len(chunks)} parts.")
        else:
            output_path = os.path.join(output_dir, filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"Copied {filename} as is.")

if __name__ == '__main__':
    # --- Configuration ---
    # INPUT_DIRECTORY = "zion_10k_md&a"
    INPUT_DIRECTORY = "zion_10k_md&a"
    OUTPUT_DIRECTORY = f"{INPUT_DIRECTORY}_chunked"
    MAX_TOKEN_LIMIT = 20000

    process_files(INPUT_DIRECTORY, OUTPUT_DIRECTORY, MAX_TOKEN_LIMIT)
    print(f"Processing complete. Chunked files are in '{OUTPUT_DIRECTORY}'.")
