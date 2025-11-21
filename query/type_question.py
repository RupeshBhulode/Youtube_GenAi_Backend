from google import genai
from google.genai import types
from chat_db.summary import summary
# ------------------------
# Gemini client (your key as provided)
# ------------------------
client = genai.Client(api_key="AIzaSyDrIJQ3H69nXpU4dQ9yco7IQgCmZhCr9EU")

s = summary()

def go(q_dev, answer_type, history_need):
    try:
        if history_need.lower() == "yes":  # <-- fixed
            s = summary()  # fetch fresh summary INSIDE the function
            
            # if summary() gives a dict, extract the summary text
            if isinstance(s, dict) and "summary" in s:
                ctx_summary = s["summary"]
            else:
                ctx_summary = str(s)

            prompt = f"""
You are given a user question and a context summary from previous chat history.

Question: {q_dev}
Context summary: {ctx_summary}

Your task:
• Understand what the user is referring to in the question.
• Use the context summary to identify the missing reference.
• Rewrite the question so that it becomes a fully independent and clear question,
  without requiring any chat history.

Example:
  Original: "Who was he?"
  Rewritten: "Who was Albert Einstein?"

  Original: "What is the use case of it?"
  Rewritten: "What is the use case of quantum computers?"

Final instruction:
→ Return only the rewritten question.
→ Do NOT change the meaning.
→ Do NOT add any extra explanation or answer.
""".strip()

            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )

            return resp.text.strip()

        # 🔴 IMPORTANT: when history is not needed → return q_dev as-is!
        return q_dev

    except Exception as e:
        print(f"Error in go(): {e}")
        return q_dev  # fallback to safety


