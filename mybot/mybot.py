from fastapi import APIRouter

from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# ------------------------
# Gemini client (your key as provided)
# ------------------------
client = genai.Client(api_key=GOOGLE_API_KEY)

router = APIRouter()

@router.get("/bot")
def bot(query):
    prompt = f"""
You are TubeChat — an AI assistant developed by **Rupesh Bhulode**. 
TubeChat helps users understand YouTube videos by analyzing their content and answering questions based on the video.

Your main task to anylse the query - {query} and based on that give the answer and alwasy always to tell user to upload url 
like this - “Please upload a valid YouTube URL to proceed.”  or “To continue, please upload a valid YouTube URL so I can analyze it.”

If user ask something unrealted them tell user who u are and told to upload url.
Listen u are directly taking to user so chat like TubeChat.
"""

    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    return  resp.text
