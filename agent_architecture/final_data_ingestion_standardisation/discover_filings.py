import os
import requests
import datetime
import csv
import time

# --- Configuration for Testing ---
# For the initial test, we'll focus on a single bank and a shorter time frame.
COMPANIES_TO_SEARCH = ["BAC"] # Now using Ticker Symbols
YEARS_TO_SEARCH = 1 
FORMS_TO_SEARCH = ["10-K", "10-Q"]

# --- Constants ---
# Correct, reliable URL for Ticker -> CIK mapping
CIK_LOOKUP_URL = "https://www.sec.gov/files/company_tickers.json"
OUTPUT_CSV_FILE = "filings_to_process.csv"

def get_cik_map(headers):
    """
    Downloads the official SEC ticker/CIK mapping and returns a dictionary
    mapping uppercase tickers to their zero-padded CIK.
    """
    print("Downloading SEC company ticker-CIK map...")
    response = requests.get(CIK_LOOKUP_URL, headers=headers)
    response.raise_for_status()
    all_companies = response.json()
    
    # The JSON is a dictionary of dictionaries. The key is a counter, the value has the company info.
    # We create a map of {ticker: CIK} for efficient lookup.
    cik_map = {
        company['ticker']: str(company['cik_str']).zfill(10) 
        for company in all_companies.values() if 'ticker' in company
    }
    print("Successfully created CIK map.")
    return cik_map

def fetch_filings_for_cik(cik, years_to_check, headers):
    """
    Fetches the submission history for a CIK and filters for recent 10-K/10-Q filings.
    """
    print(f"Fetching filing history for CIK: {cik}...")
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(submissions_url, headers=headers)
    response.raise_for_status()
    submissions = response.json()

    recent_filings = []
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=years_to_check * 365)

    if 'filings' in submissions and 'recent' in submissions['filings']:
        filings = submissions['filings']['recent']
        for i in range(len(filings['accessionNumber'])):
            filing_date_str = filings['filingDate'][i]
            filing_date = datetime.datetime.strptime(filing_date_str, '%Y-%m-%d')
            form_type = filings['form'][i]

            if filing_date >= cutoff_date and form_type in ['10-K', '10-Q']:
                recent_filings.append({
                    'accession_number': filings['accessionNumber'][i].replace('-', ''),
                    'filing_date': filing_date_str,
                    'form_type': form_type,
                })
    return recent_filings

def discover_and_save_filings(tickers, years_to_check, headers, output_csv_path="filings_to_process.csv"):
    """
    Main function to discover and save filings for a list of tickers.
    """
    all_filings_to_process = []
    cik_map = get_cik_map(headers)
    
    for ticker in tickers:
        ticker_upper = ticker.upper()
        print(f"\n--- Processing ticker: {ticker_upper} ---")
        
        cik = cik_map.get(ticker_upper)
        if not cik:
            print(f"Could not find CIK for ticker: {ticker_upper}. Skipping.")
            continue
            
        filings = fetch_filings_for_cik(cik, years_to_check, headers)
        
        for filing in filings:
            all_filings_to_process.append({
                "ticker": ticker_upper,
                "cik": cik,
                **filing
            })
        
        # Adding a small delay to respect SEC rate limits
        time.sleep(0.5)

    if not all_filings_to_process:
        print("No relevant filings found for the given tickers and time period.")
        return

    print(f"\nWriting {len(all_filings_to_process)} filings to '{output_csv_path}'...")
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "cik", "accession_number", "filing_date", "form_type"])
        writer.writeheader()
        writer.writerows(all_filings_to_process)
        
    print("Discovery complete.")

if __name__ == "__main__":
    # This allows the script to be run standalone for testing
    TEST_HEADERS = {"User-Agent": "test@example.com"}
    TICKERS_TO_PROCESS = ["BAC", "AAPL", "MSFT"] 
    YEARS_TO_CHECK = 1
    discover_and_save_filings(TICKERS_TO_PROCESS, YEARS_TO_CHECK, TEST_HEADERS) 