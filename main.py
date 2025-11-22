# main.py - Main FastAPI application entry point

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from youtube.config import CORS_ORIGINS
from youtube.routes import transcript_router
from query.query import router as query_router
from chat_db.history import router as his_router
from chat_db.summary import router as sum_router
from chroma.chroma_store import clear_chromadb
from chat_db.databse import delete_all_records
from mybot.mybot import router as bot_router
from new_youtube import router as new_router
app = FastAPI(title="YouTube Captions Cleaner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(query_router, prefix="")
app.include_router(his_router, prefix="")
app.include_router(sum_router, prefix="")
app.include_router(bot_router, prefix="")
app.include_router(new_router, prefix="")

@app.get("/")
def root():
    return {"status": "ok", "message": "YouTube Captions API is running"}



@app.get("/kill_session")
def kill():
    clear_chromadb()
    delete_all_records()
