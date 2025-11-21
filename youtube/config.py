"""
config.py - Application configuration
"""
from pathlib import Path

# CORS origins
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "*"
]

# Directory for temporary subtitle files
OUT_DIR = Path("subs_temp")
OUT_DIR.mkdir(exist_ok=True)

# Caption processing defaults
MAX_PARA_CHARS = 300
MAX_LINES_WITHOUT_PUNCT = 4

# YouTube-DL settings
YOUTUBE_CLIENTS = [None, "web_html5", "web", "desktop", "android", "ios", "tv_html5"]
MAX_CLIENTS_TRY = 7

# Default preferred languages
DEFAULT_LANGUAGES = ["en", "hi", "en-US", "en-GB"]

# Chunk processing defaults
DEFAULT_CHUNK_SIZE = 300
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_OUTPUT_DIR = "chunks"

# ChromaDB defaults
DEFAULT_COLLECTION_NAME = "video_chunks"
DEFAULT_PERSIST_DIR = "chromadb_store"