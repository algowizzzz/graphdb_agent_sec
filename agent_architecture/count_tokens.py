import os
import json
import tiktoken

def count_tokens_in_files():
    """
    Counts the tokens in each JSON file in the 'BAC_2025' directory
    and saves the results to a text file.
    """
    dir_path = 'BAC_2025'
    output_file = 'BAC_2025_token_counts.txt'
    
    try:
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
    except FileNotFoundError:
        print(f"Error: Directory '{dir_path}' not found.")
        return

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        print(f"Error initializing tiktoken: {e}")
        # As a fallback, let's use a simple word count.
        encoding = None

    token_counts = {}

    for file_name in files:
        file_path = os.path.join(dir_path, file_name)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                text = data.get("text", "")
                if encoding:
                    token_count = len(encoding.encode(text))
                else:
                    token_count = len(text.split())
                token_counts[file_name] = token_count
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from {file_name}. Skipping.")
        except Exception as e:
            print(f"Error processing file {file_name}: {e}")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for file_name, count in sorted(token_counts.items()):
                f.write(f"{file_name}: {count} tokens\n")
        print(f"Token counts saved to {output_file}")
    except Exception as e:
        print(f"Error writing to output file: {e}")

if __name__ == "__main__":
    count_tokens_in_files() 