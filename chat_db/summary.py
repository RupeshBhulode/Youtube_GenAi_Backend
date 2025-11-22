from fastapi import APIRouter
from chat_db.databse import get_last_n_records   # verify the import path

from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# ------------------------
# Gemini client (your key as provided)
# ------------------------
client = genai.Client(api_key=GOOGLE_API_KEY)

router = APIRouter()

@router.get("/summary")
def summary():
    d = get_last_n_records(4)  # Fetch inside the function
    formatted_list = [f"{row[1]} - {row[2]}" for row in d]

    prompt = f"""
    The following are the most recent user–assistant interactions.
    Your task is to produce a short context summary that captures:
    • The main subject being discussed (focus on WHAT the conversation is about)
    • Any names, events, or important details mentioned
    • The overall intent of the user
    • Give MORE importance to the last user and assistant messages because they are fresh.
    • DO NOT repeat sentences exactly — only capture the essence.

    If future questions refer to “he”, “they”, “what is it?”, or “this”, the summary should help identify what the user is referring to.
    Return only a single paragraph summary.

    Here is the recent conversation:
    {formatted_list}
    """

    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    return  {"summary":resp.text}
