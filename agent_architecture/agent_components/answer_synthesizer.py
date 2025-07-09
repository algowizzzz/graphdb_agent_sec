import json
import logging
import time
from openai import OpenAI
import textwrap

# Define a constant for character limits to approximate token counts
# A safe buffer for a 200k model is around 180k characters (at ~4 chars/token)
MAX_CHARS_PER_CHUNK = 180000

def _split_text_into_chunks(text: str, chunk_size: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """Splits a long text into chunks of a specified size without breaking words."""
    if len(text) <= chunk_size:
        return [text]
    
    # Use textwrap to split gracefully
    return textwrap.wrap(text, width=chunk_size, break_long_words=True, replace_whitespace=False)

def _extract_table_data(client: OpenAI, text: str, tasks: list) -> str:
    """
    Specialist function to extract structured data from text that may contain tables.
    """
    if not tasks:
        return ""
        
    prompt = f"""
You are a precision data extraction bot. Your task is to analyze the provided text, which may be a messy, text-only representation of a financial document, and extract the specific data points requested.

**Data Points to Extract:**
{json.dumps(tasks, indent=2)}

**Text to Analyze:**
---
{text}
---

**Instructions:**
1.  Carefully read the "Text to Analyze".
2.  For each item in the "Data Points to Extract" list, find the corresponding value in the text.
3.  Return a single JSON object where the keys are the descriptions from the extraction list and the values are the data you found.
4.  If a specific data point is not found in the text, you MUST use the value "Not Found".
5.  Do not add any commentary, explanation, or introductory text. Your entire output must be ONLY the JSON object.

**Example Response:**
{{
  "Net Income for Q2 2025": "$7.4 billion",
  "Total Revenue for Q2 2025": "$27.4 billion",
  "Allowance for credit losses at March 31, 2025": "Not Found"
}}
"""
    try:
        response = client.chat.completions.create(
            model=client.model,
            messages=[
                {"role": "system", "content": "You are a data extraction expert that only responds with JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error during table data extraction: {e}")
        return json.dumps({task: "Extraction Error" for task in tasks})


def _summarize_narrative(client: OpenAI, text: str, tasks: list, filename: str) -> str:
    """
    Specialist function to summarize narrative prose based on a set of tasks.
    """
    if not tasks:
        return ""

    prompt = f"""
You are a financial analyst. Your task is to summarize key points from a section of a financial document based on a list of objectives.

**Document Section:** {filename}

**Objectives for this Summary:**
{json.dumps(tasks, indent=2)}

**Text to Analyze:**
---
{text}
---

**Instructions:**
1. Read the text and create a concise, point-by-point summary that directly addresses the "Objectives for this Summary".
2. Focus only on information relevant to the objectives.
3. If the text does not contain information for an objective, state that it was not found.
"""
    try:
        response = client.chat.completions.create(
            model=client.model,
            messages=[
                {"role": "system", "content": "You are an expert financial analyst."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error during narrative summarization: {e}")
        return "Could not generate narrative summary due to an error."


def map_summarize_sections(client: OpenAI, documents: list, user_query: str, extraction_checklist: list):
    """
    Processes documents using a hybrid approach. It separates extraction tasks from
    summarization tasks and uses specialized functions for each. This is the "Map" step.
    """
    batch_summaries = []
    logging.info(f"Mapping {len(documents)} document(s) with hybrid strategy...")

    # Separate the checklist into two types of tasks
    table_tasks = [item['task'] for item in extraction_checklist if item['type'] == 'table_extraction']
    narrative_tasks = [item['task'] for item in extraction_checklist if item['type'] == 'narrative_summary']

    for i, doc in enumerate(documents, 1):
        filename = doc['filename']
        text = doc['text']
        logging.info(f"  - Processing document: {filename} ({i}/{len(documents)})")

        # Add a delay to prevent rate-limiting on the API between documents
        time.sleep(1)

        chunks = _split_text_into_chunks(text)
        if len(chunks) > 1:
            logging.warning(f"    - Document '{filename}' is large ({len(text)} chars). Processing in {len(chunks)} chunks.")

        # Process each chunk with both specialists
        all_chunk_results = []
        for j, chunk in enumerate(chunks, 1):
            chunk_log_name = f"{filename} (part {j}/{len(chunks)})"
            logging.info(f"      - Analyzing chunk {j}/{len(chunks)}...")
            
            # Get structured data and narrative summary for the chunk
            table_results_json = _extract_table_data(client, chunk, table_tasks)
            
            # Add a second delay between the two API calls for the same chunk
            time.sleep(1) 
            
            narrative_summary = _summarize_narrative(client, chunk, narrative_tasks, chunk_log_name)
            
            chunk_output = ""
            if table_results_json:
                chunk_output += f"Extracted Data:\n{table_results_json}\n\n"
            if narrative_summary:
                chunk_output += f"Narrative Summary:\n{narrative_summary}"

            all_chunk_results.append(chunk_output)

        # Combine results from all chunks for the document
        final_doc_summary = "\n\n---\n\n".join(all_chunk_results)

        batch_summaries.append({
            "text": final_doc_summary,
            "filename": filename,
            "is_summary": True
        })

    return batch_summaries


def reduce_and_synthesize_answer(llm_client: OpenAI, query: str, results: list, analysis_goal: str) -> str:
    """
    Synthesizes a final, comprehensive answer from a list of structured and narrative results.
    This is the "Reduce" step.
    """
    logging.info("Synthesizing final answer from hybrid results...")
    
    if not results:
        return "No information was found that matched the query."
    
    context_parts = []
    for i, res in enumerate(results):
        text = res.get('text', '')
        filename = res.get('filename')
        context_parts.append(f"--- START: Source from '{filename}' ---\n{text}\n--- END: Source from '{filename}' ---")
    
    context = "\n\n".join(context_parts)

    prompt = f"""
You are RiskGPT, a world-class financial analyst. Your task is to write a final, comprehensive report that directly addresses the user's query and original analysis goal, using only the structured data and narrative summaries provided.

**Original User Query:**
{query}

**Overarching Analysis Goal:**
{analysis_goal}

**Provided Context (a mix of JSON data and narrative points from various documents):**
---
{context}
---

**Your Task:**
1.  **Synthesize, Do Not Summarize:** Read through all the provided context. Your primary job is to weave the extracted JSON data and the narrative summaries into a single, cohesive, and easy-to-read report that fulfills the `analysis_goal`.
2.  **Prioritize Hard Data:** When presenting figures (like Net Income, Revenue, etc.), use the specific values from the `Extracted Data` JSON objects. These are the ground truth.
3.  **Use Narrative for Context:** Use the `Narrative Summary` points to explain *why* the numbers are what they are, to describe trends, and to discuss risks.
4.  **Handle Missing Data:** If the extracted data for a key metric is "Not Found" or "Extraction Error", you MUST explicitly state that the information was not available in the documents. Do not invent data.
5.  **Structure and Format:** The final output should be a professional, well-structured report. Use markdown for headings, bullet points, and bolding to improve readability.

**Disclaimer:**
* End your entire response with the following disclaimer on a new line: "*Disclaimer: RiskGPT may hallucinate; please independently verify all insights before use in production or decision-making contexts.*"
---
Begin your response now.
"""
    response = llm_client.chat.completions.create(
        model=llm_client.model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    llm_answer = response.choices[0].message.content

    source_filenames = sorted(list(set([r.get('filename') for r in results if r.get('filename')])))
    sources_section = "\n\nSources:\n"
    if source_filenames:
        sources_section += "\n".join(f"- {name}" for name in source_filenames)
    else:
        sources_section += "- None"
        
    final_answer = llm_answer + sources_section
    return final_answer