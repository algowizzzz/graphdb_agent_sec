import os
import json
import discover_filings
import process_filing

def load_config(config_path):
    """Loads the JSON configuration file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{config_path}'.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in configuration file at '{config_path}'.")
        return None

def read_tickers_from_file(file_path):
    """Reads tickers from a file, one per line, ignoring empty lines and comments."""
    try:
        with open(file_path, 'r') as f:
            # Read lines, strip whitespace, and filter out empty lines and comments
            tickers = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        if not tickers:
            print(f"Warning: Ticker file '{file_path}' is empty or contains no valid tickers.")
            return []
        return tickers
    except FileNotFoundError:
        print(f"Error: Ticker file not found at '{file_path}'.")
        print("Please create the file with one ticker symbol per line.")
        return None

def main():
    """
    Main orchestration script.
    - Reads all configuration from config.json.
    - Calls the discovery script to find filings.
    - Calls the processing script to parse and save the filings.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.json")
    
    config = load_config(config_path)
    if not config:
        return

    # --- Configuration ---
    YEARS_TO_CHECK = config.get("years_to_check", 1)
    TICKER_FILENAME = config.get("ticker_file", "tickers.txt")
    HEADERS = {"User-Agent": config.get("user_agent_email", "Default User-Agent <email@example.com>")}
    
    ticker_file_path = os.path.join(base_dir, TICKER_FILENAME)
    output_dir = os.path.join(base_dir, "eternal_sec")
    temp_csv_path = os.path.join(base_dir, "temp_filings_to_process.csv")

    TICKERS_TO_PROCESS = read_tickers_from_file(ticker_file_path)
    if TICKERS_TO_PROCESS is None:
        return
    if not TICKERS_TO_PROCESS:
        print("Exiting: No tickers to process.")
        return

    print("="*50)
    print(f"Starting process for tickers: {', '.join(TICKERS_TO_PROCESS)}")
    print(f"Years to check: {YEARS_TO_CHECK}")
    print(f"User-Agent: {HEADERS['User-Agent']}")
    print("="*50)

    # --- Step 1: Discover Filings ---
    print("\n[Step 1/2] Discovering filings...")
    discover_filings.discover_and_save_filings(
        tickers=TICKERS_TO_PROCESS,
        years_to_check=YEARS_TO_CHECK,
        headers=HEADERS,
        output_csv_path=temp_csv_path
    )
    print("[Step 1/2] Discovery complete.")

    # --- Step 2: Process Filings ---
    if os.path.exists(temp_csv_path) and os.path.getsize(temp_csv_path) > 100:
        print("\n[Step 2/2] Processing discovered filings...")
        process_filing.batch_process_filings(
            input_csv_path=temp_csv_path,
            output_dir=output_dir,
            headers=HEADERS
        )
        print("[Step 2/2] Processing complete.")
    else:
        print("\n[Step 2/2] No filings were found to process. Skipping.")

    # --- Step 3: Cleanup ---
    if os.path.exists(temp_csv_path):
        os.remove(temp_csv_path)
        print(f"\nCleaned up temporary file: {temp_csv_path}")

    print("\n" + "="*50)
    print("Workflow finished.")
    print(f"Output files are located in: {output_dir}")
    print("="*50)

if __name__ == "__main__":
    main() 