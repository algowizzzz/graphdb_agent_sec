import logging
from openai import OpenAI
import json

def evaluate_and_suggest_improvements(llm_client: OpenAI, user_query: str, answer: str, context: str) -> dict:
    """
    Evaluates the answer's faithfulness to the provided context and its relevance to the user query.
    """
    logging.info("Critic is evaluating the answer...")
    
    prompt = f"""
Your role is to act as a strict, constructive critic. Your primary goal is to ensure the "Synthesized Answer" is a faithful and comprehensive summary of the "Provided Context" in relation to the "User Query".

**User Query:**
{user_query}

**Provided Context:**
{context}

**Synthesized Answer:**
{answer}

**Your Task:**
Critically evaluate the answer based ONLY on the provided context. Your response MUST be a JSON object with two keys:
1.  "decision": A single word, either "ACCEPT" or "REFINE".
    -   Choose "ACCEPT" if the answer is a good and faithful summary of the provided context, even if the context itself is insufficient to fully answer the user's query.
    -   Choose "REFINE" only if the answer misrepresents the context, hallucinates information not present, or poorly synthesizes the provided information.
2.  "feedback": A concise, one-sentence explanation.
    -   If the decision is "ACCEPT" but the context seems insufficient, state that. For example: "The answer correctly summarizes the retrieved documents, but they lack specific quantitative stress testing results."
    -   If the decision is "REFINE", explain what was wrong with the synthesis. For example: "The answer incorrectly claims a 10% net income increase, but the context states it was 5%."

Example of ACCEPT (with insufficient context):
{{
  "decision": "ACCEPT",
  "feedback": "The answer is a good summary of the available information, but the documents do not contain specific details about stress testing."
}}

Example of REFINE:
{{
  "decision": "REFINE",
  "feedback": "The answer fails to incorporate the details about the CET1 ratio, which were present in the context."
}}

Provide your JSON response now.
"""
    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a critical AI evaluator that responds in JSON format."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        evaluation_str = response.choices[0].message.content
        logging.info(f"Critic evaluation: {evaluation_str}")
        evaluation = json.loads(evaluation_str)
        return evaluation
    except Exception as e:
        logging.error(f"An error occurred during critic evaluation: {e}")
        # Fallback in case of error to prevent a crash
        return {"decision": "ACCEPT", "feedback": "Critic failed to evaluate, accepting by default."} 