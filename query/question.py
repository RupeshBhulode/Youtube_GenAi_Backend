import traceback
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types
from query.type_question import go
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# ------------------------
client = genai.Client(api_key=GOOGLE_API_KEY)



def frame_question(question: str) -> Tuple[str, str, str]:
    """
    Convert English question into Devanagari Hinglish and predict answer_type and history_need.
    Returns: (question_dev, answer_type, history_need)
    """
    prompt = f"""
You are an intelligent conversation analyzer. Analyze the given question and determine three things:

1. Refined Question: Rewrite the question for clarity (keep it concise)
2. Answer Type: What type of answer does this question need?
3. History Needed: Does this question reference previous conversation context?

---

## HISTORY DETECTION RULES (MOST IMPORTANT):

**Answer "yes" for history if the question:**
- Uses pronouns: "it", "that", "this", "these", "those", "he", "she", "they", "them"
- Uses possessive pronouns: "its", "his", "her", "their"
- References previous topics: "the one we discussed", "as you mentioned", "from before"
- Contains words: "also", "too", "additionally", "furthermore", "moreover"
- Asks for "more details", "elaborate", "explain further", "tell me more"
- Uses demonstratives without clear context: "what about that?", "how does it work?"
- Continues a topic: "and what about...", "what else...", "any other..."
- Asks follow-up questions: "why?", "how?", "when?" without a clear subject

**Answer "no" for history if the question:**
- Is completely self-contained with all necessary context
- Starts a new topic with full context provided
- Contains specific names, terms, or complete subjects
- Is a greeting or standalone query: "hello", "what is X", "explain Y"

---

## ANSWER TYPE CLASSIFICATION:

- "short": Quick factual answer (1 line)
  - "What year did...", "Who is...", "How many..."
  
- "detailed": Comprehensive explanation (paragraph form)
  - "Explain how...", "Why does...", "What are the implications of..."
  
- "list": Multiple items or points
  - "What are the types of...", "List the...", "Give me examples of..."
  
- "yes/no": Binary question with brief explanation
  - "Is it...", "Can we...", "Does this..."
  
- "definition": Concise definition
  - "What is...", "Define...", "What does X mean..."
  
- "step-by-step": Sequential instructions or process
  - "How to...", "Steps for...", "Process of...", "How do I..."

---

## OUTPUT FORMAT:

Return ONLY a single string with three parts separated by ' | ':
refined_question | answer_type | history_needed

Example outputs:
- "What is machine learning | definition | no"
- "How does it work internally | detailed | yes"
- "What are its main features | list | yes"
- "Explain quantum computing | detailed | no"
- "Can you elaborate on that | detailed | yes"

Input question (English):
{question}
""".strip()

    try:
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        raw = resp.text.strip()
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("“") and raw.endswith("”")):
            raw = raw[1:-1].strip()

        # 2) Split and also strip quotes from each part
        parts = [p.strip().strip('"').strip('“”') for p in raw.split("|")]
        parts = [p.strip() for p in raw.split("|")]

        q_dev = parts[0] if len(parts) > 0 and parts[0] else raw
        answer_type = parts[1] if len(parts) > 1 and parts[1] else "detailed"
        history_need = parts[2] if len(parts) > 2 and parts[2] else "no"
        
        

        return q_dev, answer_type, history_need
    except Exception as e:
        print(f"Error in frame_question: {e}")
        # Fallback to original question
        return question, "detailed", "no"
    


    
def get_actual_question(question: str) -> Tuple[str, str, str]:
    
    q_dev, answer_type, history_need = frame_question(question)

    try:
        final_q = go(q_dev, answer_type, history_need)
    except Exception as e:
        print(f"Error in get_actual_question/go: {e}")
        final_q = q_dev  # fallback

    return final_q, answer_type, history_need

    
