import os
import re
import json
import requests
import shutil
import datetime
import csv
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# --- Configuration ---
# We no longer need hardcoded values here, as they will come from the CSV.


def sanitize_for_filename(name):
    """
    Takes a string and returns a safe version for a filename,
    using PascalCase for spaces.
    """
    # Capitalize the first letter of each word and join them together
    # e.g., "ITEM 1A. RISK FACTORS" -> "Item1a.RiskFactors"
    pascal_case_name = ''.join(word.capitalize() for word in name.split())
    
    # Remove any remaining characters that are invalid in filenames
    safe_name = re.sub(r'[\\/*?:"<>|]', "", pascal_case_name)
    return safe_name[:100]


def extract_toc_titles(soup):
    """
    Finds the Table of Contents in the document and returns a clean list of section titles.
    """
    toc_titles = set()
    # Heuristic: Find tables that contain links to internal anchors, which is characteristic of a ToC.
    for table in soup.find_all('table'):
        links = table.find_all('a', href=lambda href: href and href.startswith('#'))
        if len(links) > 5: # A table with more than 5 internal links is likely a ToC.
            for link in links:
                # Clean up the text to use for matching later
                clean_title = re.sub(r'\s+', ' ', link.get_text(strip=True)).lower()
                toc_titles.add(clean_title)
    return list(toc_titles)


def get_quarter(filing_date_str):
    """
    Determines the financial quarter (q1, q2, q3, q4) from a YYYY-MM-DD date string.
    """
    filing_date = datetime.datetime.strptime(filing_date_str, "%Y-%m-%d").date()
    quarter = (filing_date.month - 1) // 3 + 1
    return f"q{quarter}"


def _extract_and_structure_tables(html_content):
    """
    Finds all tables in a chunk of HTML, intelligently converting them to a
    structured list of JSON objects using pandas.
    """
    if not html_content:
        return [], None

    soup = BeautifulSoup(html_content, 'html.parser')
    all_tables_structured = []

    # Use a copy of the soup to find tables to prevent modification issues
    soup_for_tables = BeautifulSoup(html_content, 'html.parser')

    for i, table in enumerate(soup_for_tables.find_all('table')):
        try:
            # 1. Extract a potential name for the table
            name = f"Table {i + 1}"
            caption = table.find('caption')
            if caption:
                name = ' '.join(caption.get_text(strip=True).split())
            else:
                # Look for a bolded heading just before the table
                prev_tag = table.find_previous_sibling()
                if prev_tag and prev_tag.name in ['p', 'div'] and prev_tag.find('b'):
                    text = ' '.join(prev_tag.get_text(strip=True).split())
                    if 0 < len(text) < 150:
                        name = text

            # 2. Use pandas to parse the HTML table into a DataFrame
            # This robustly handles most complex headers and merged cells
            df_list = pd.read_html(StringIO(str(table)), flavor='bs4')
            if not df_list:
                continue
            
            df = df_list[0]

            # 3. Clean and flatten column headers
            # Pandas creates a MultiIndex for complex headers, we need to flatten it
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ['_'.join(map(str, col)).strip() for col in df.columns.values]
            else:
                df.columns = [str(col) for col in df.columns]

            # Replace generic "Unnamed" columns with more descriptive names
            df.columns = [f"Column_{j}" if 'Unnamed' in col else col for j, col in enumerate(df.columns)]
            
            # Remove rows that are entirely empty
            df.dropna(how='all', inplace=True)
            df.reset_index(drop=True, inplace=True)

            # Convert all data to string to ensure JSON compatibility
            df = df.astype(str)

            # 4. Convert the cleaned DataFrame to the desired JSON structure
            if not df.empty:
                table_object = {
                    "name": name,
                    "columns": df.columns.tolist(),
                    "rows": df.to_dict(orient='records')
                }
                all_tables_structured.append(table_object)

        except Exception as e:
            # Ignore tables that fail to parse, as some are just for layout
            # print(f"Skipping a table that failed to parse: {e}")
            continue
            
    # Decompose tables from the original soup to get clean text
    for table in soup.find_all('table'):
        table.decompose()
        
    return all_tables_structured, soup


def fetch_and_process_filing(cik, accession_number, company_name, output_dir, headers):
    """
    Fetches, parses, and saves a filing into individual section files in the specified directory.
    """
    try:
        # 1. Get the filing index page
        accession_no_dashes = accession_number.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{accession_number}-index.html"
        
        response = requests.get(index_url, headers=headers)
        response.raise_for_status()
        index_soup = BeautifulSoup(response.content, 'html.parser')

        # 2. Extract metadata
        form_name_tag = index_soup.find('div', id='formName')
        form_type = form_name_tag.find('strong').text.strip() if form_name_tag and form_name_tag.find('strong') else "UNKNOWN_FORM"

        filing_date_tag = index_soup.find('div', class_='infoHead', string='Filing Date')
        filing_date = filing_date_tag.find_next_sibling('div').text.strip() if filing_date_tag and filing_date_tag.find_next_sibling('div') else "UNKNOWN_DATE"

        metadata = {
            "accession_number": accession_number,
            "cik": cik,
            "company": company_name,
            "filing_date": filing_date,
            "form_type": form_type
        }

        # 3. Find and fetch the primary document
        file_table = index_soup.find('table', class_='tableFile')
        if not file_table:
            raise ValueError("Could not find the file table in the index file.")

        primary_doc_link_tag = None
        for row in file_table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) > 3 and cells[3].text.strip() in metadata['form_type']:
                primary_doc_link_tag = cells[2].find('a')
                if primary_doc_link_tag:
                    break
        
        if not primary_doc_link_tag or not primary_doc_link_tag.has_attr('href'):
            raise ValueError(f"Could not find a valid link for Form Type '{metadata['form_type']}' in the index file.")
        
        doc_path = primary_doc_link_tag['href']
        if "?doc=" in doc_path:
            doc_path = doc_path.split('?doc=')[-1]
        doc_url = "https://www.sec.gov" + doc_path
        
        doc_response = requests.get(doc_url, headers=headers)
        doc_response.raise_for_status()

        # 4. Parse the primary HTML document for sections
        print("Parsing HTML for sections...")
        filing_soup = BeautifulSoup(doc_response.content, 'html.parser')

        sections = []
        section_pattern = re.compile(r'item\s*\d+[a-z]?\.?', re.IGNORECASE)
        potential_headers = filing_soup.find_all(['p', 'b', 'strong', 'div'])

        headers_found = []
        for p in potential_headers:
            if p.find_parent('table') or p.find_parent('a'):
                continue
            text = p.get_text(strip=True)
            if section_pattern.match(text):
                headers_found.append(p)
        
        for i, header in enumerate(headers_found):
            section_title = header.get_text(strip=True)
            section_content_tags = []
            for sibling in header.find_next_siblings():
                if sibling in headers_found:
                    break
                section_content_tags.append(str(sibling))
            content_html = "".join(section_content_tags)
            sections.append({'name': section_title, 'content': content_html})

        # 5. Filter and Save each valid section
        print(f"Found {len(sections)} potential sections. Filtering and saving...")

        min_content_length = 250
        sections = [s for s in sections if len(s['content']) > min_content_length]

        title_only_pattern = re.compile(r'^\s*item\s*\d+[a-z]?\.?\s*$', re.IGNORECASE)
        sections = [s for s in sections if not title_only_pattern.match(s['name'])]

        saved_count = 0
        for section in sections:
            title = section['name']
            content_html = section['content']
            
            tables, soup_without_tables = _extract_and_structure_tables(content_html)
            
            clean_markdown = md(str(soup_without_tables), heading_style="ATX") if soup_without_tables else ""
            year = metadata['filing_date'].split('-')[0]
            quarter = get_quarter(metadata['filing_date'])
            doc_type = metadata['form_type'].replace('Form ', '')

            structured_data = {
                "domain": "external", "subdomain": "SEC", "Company": company_name,
                "Document type": doc_type, "year": year, "quarter": quarter,
                "section": title, "accession_number": accession_number, "cik": cik,
                "filing_date": metadata['filing_date'], "text": clean_markdown,
                "tables": tables
            }

            safe_section_title = sanitize_for_filename(title)
            filename_parts = [
                structured_data['domain'], structured_data['subdomain'], structured_data['Company'],
                structured_data['Document type'], structured_data['year'], structured_data['quarter'],
                safe_section_title
            ]
            filename = "_".join(filename_parts) + ".json"
            output_path = os.path.join(output_dir, filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, indent=4)
            
            saved_count += 1

        print(f"Successfully saved {saved_count} valid sections.")

    except Exception as e:
        print(f"An error occurred while processing {accession_number}: {e}")


def batch_process_filings(input_csv_path, output_dir, headers):
    """
    Reads a CSV file of filings and processes each one.
    """
    try:
        if os.path.exists(output_dir):
            print(f"Cleaning output directory: {output_dir}")
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)

        with open(input_csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                accession_with_dashes = f"{row['accession_number'][:10]}-{row['accession_number'][10:12]}-{row['accession_number'][12:]}"
                
                print("\n" + "="*80)
                print(f"Processing {row['ticker']} {row['form_type']} filing from {row['filing_date']}...")
                print("="*80 + "\n")
                
                fetch_and_process_filing(
                    cik=row['cik'],
                    accession_number=accession_with_dashes,
                    company_name=row['ticker'],
                    output_dir=output_dir,
                    headers=headers
                )
        
        print("\nBatch processing complete.")

    except FileNotFoundError:
        print(f"Error: Input CSV file not found at '{input_csv_path}'.")
        print("Please run the discovery script first to generate the file.")
    except Exception as e:
        print(f"An unexpected error occurred during batch processing: {e}")


if __name__ == "__main__":
    # This allows the script to be run standalone for testing
    TEST_HEADERS = {"User-Agent": "test@example.com"}
    INPUT_CSV = "filings_to_process.csv"
    OUTPUT_DIR = "output_sec_api"
    batch_process_filings(INPUT_CSV, OUTPUT_DIR, TEST_HEADERS) 