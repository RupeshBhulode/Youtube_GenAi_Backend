# app/query.py  (SIMPLE & CLEAN VERSION – ONLY RETURNS TOP 4 CLOSEST MATCHES)

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from google import genai
from google.genai import types
from query.question import get_actual_question
from chroma.chroma_store import _make_chroma_client  # Same function you already have!
from query.answer import bot_answer,english
from chat_db.databse import create_database,append_data

router = APIRouter()

# SAME GEMINI MODEL USED DURING CHUNKING
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768
client = genai.Client(api_key="AIzaSyAWF7AtLA7jC2j8GfxJS6thasdxiQa1X7Y")  # IMPORTANT: REPLACE YOUR KEY!

create_database()

def translate_query_to_hinglish(query: str) -> str:
    """ Translate English query to Hinglish (Devanagari) for better matching with Hindi chunks. """ 
    try:
        prompt = f""" Convert this English question into natural Hinglish written in Devanagari script.
          Keep technical terms in English but write them phonetically in Devanagari. 
          Make it sound like natural spoken Hindi-English mix. 
          English question: {query} Return ONLY the Hinglish translation in Devanagari, nothing else.
           ex- query - what is cyborg? the response - साइबॉर्ग क्या होता है?  
           text texual respoce should be in hindi devnagri representation only""" 
        response = client.models.generate_content( 
            model="gemini-2.0-flash",
            contents=prompt 
            ) 
        hinglish_query = response.text.strip() 
        
        return hinglish_query 
    except Exception as e: print(f"Translation failed: {e}, using original query") 
    return query



def get_query_embedding(text: str):
    """Embed text using Gemini."""
    try:
        res = client.models.embed_content(
            model=EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM)
        )
        return res.embeddings[0].values
    except Exception as e:
        raise RuntimeError(f"Gemini embedding failed: {e}")


@router.get("/query_chunks", summary="Get top 4 most relevant chunks")
def query_chunks(
    q: str = Query(..., description="Search query"),
    collection_name: str = Query("video_chunks", description="ChromaDB collection name"),
    persist_dir: str = Query("chromadb_store", description="ChromaDB folder")
):
    """
    Return ONLY top 4 most similar chunks from ChromaDB.
    No multi-query, no RAG, no history.
    """
    try:
        if not q.strip():
            raise HTTPException(status_code=400, detail="Query text is empty")

        # === Load ChromaDB ===
        client_db = _make_chroma_client(persist=True, persist_dir=persist_dir)
        collection = client_db.get_collection(collection_name)

        # === Embed Query ===
        q_hinglish=translate_query_to_hinglish(q)


        q_dev, answer_type, history_need=get_actual_question(q_hinglish)

        
        append_data("user",q)
  

        
        q_emb = get_query_embedding(q_dev)

        # === Query ChromaDB (Top-4 only) ===
        result = collection.query(
            query_embeddings=[q_emb],
            n_results=4  # ← FIXED TO ONLY 4 RESULTS
        )





        docs = result.get("documents", [[]])[0]
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0] 


        if docs:
            data = " | ".join(docs[:4])   # up to 4 chunks
        else:
            data = ""

        answer_h=bot_answer(q_dev,answer_type,history_need,data)  
        answer=english(answer_h)
        append_data("bot", answer)
        return JSONResponse({
             
            "question":q_dev,
            "type":answer_type,
            "history":history_need,                
            
            "answer":answer
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
