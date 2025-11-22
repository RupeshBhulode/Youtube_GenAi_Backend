import re
import traceback
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from youtube_transcript_api import YouTubeTranscriptApi
from youtube.config import OUT_DIR, YOUTUBE_CLIENTS, MAX_CLIENTS_TRY, DEFAULT_LANGUAGES
from embedding.chunk_utils import create_chunks_from_paragraphs
from chroma.chroma_store import store_embeddings_in_chroma
from youtube.config import (
    OUT_DIR,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_PERSIST_DIR,
)
from chat_db.databse import delete_all_records
from youtube.file_utils import clear_out_dir
# whatever modules you already had:
# from your_module import (
#     DEFAULT_CHUNK_SIZE,
#     DEFAULT_CHUNK_OVERLAP,
#     DEFAULT_COLLECTION_NAME,
#     DEFAULT_PERSIST_DIR,
#     clear_out_dir,
#     delete_all_records,
# )

router = APIRouter()


# --- helper: extract video id from any youtube url or direct id ---
def extract_video_id(url_or_id: str) -> str:
    """
    Accepts full YouTube URL or plain video id and returns the video id.
    Examples:
      https://youtu.be/vuOx32ypfGY?si=...
      https://www.youtube.com/watch?v=vuOx32ypfGY&ab_channel=...
      vuOx32ypfGY
    """
    u = url_or_id.strip()

    # already looks like an id (no slash, no 'http')
    if "http://" not in u and "https://" not in u and "/" not in u:
        return u

    if "v=" in u:
        return u.split("v=")[1].split("&")[0]

    # youtu.be/ID?...
    return u.split("/")[-1].split("?")[0]


# --- main endpoint ---
@router.get(
    "/yt_url_chunks_inmemory",
    summary="My Application",
)
def yt_url_chunks_inmemory(
    url: str = Query(..., description="YouTube URL or video id"),
    langs: Optional[str] = Query("hi,en", description="Comma-separated preferred languages"),
    chunk_size: Optional[int] = Query(DEFAULT_CHUNK_SIZE, description="Words per chunk"),
    overlap: Optional[int] = Query(DEFAULT_CHUNK_OVERLAP, description="Overlapping words between chunks"),
    collection_name: str = Query(DEFAULT_COLLECTION_NAME, description="ChromaDB collection name"),
    persist_dir: str = Query(DEFAULT_PERSIST_DIR, description="ChromaDB persistence directory"),
    reset_collection: bool = Query(True, description="Reset the ChromaDB collection before inserting"),
):
    """
    Fetch YouTube transcript via youtube-transcript-api,
    clean it into paragraphs, create overlapping chunks,
    generate embeddings, and store them into ChromaDB.
    """

    # optional: if you still want to clear chat history
    delete_all_records()

    try:
        # Clean any temp/output dir you had before
        print("Cleaning output directory...")
        clear_out_dir()

        # Parse preferred languages from query
        preferred = [l.strip() for l in langs.split(",") if l.strip()]
        if not preferred:
            preferred = ["hi", "en"]

        print(f"Using preferred languages: {preferred}")

        # Validate URL / ID
        if not url.strip():
            raise HTTPException(status_code=400, detail="URL or video id is required")

        # Extract video_id
        video_id = extract_video_id(url)
        print(f"Resolved video_id = {video_id}")

        # ---- FETCH TRANSCRIPT (new logic) ----
        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=preferred)
        except Exception as e:
            print(f"Error while fetching transcript:\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=404,
                detail=f"Transcript not available: {str(e)}",
            )

        # fetched is a FetchedTranscript object (iterable of FetchedTranscriptSnippet)
        # join all text into one big string
        raw_text = " ".join(snippet.text for snippet in fetched)

        # Clean spaces / punctuation a bit
        clean_text = re.sub(r"\s+", " ", raw_text).strip()
        clean_text = re.sub(r" ([.,!?])", r"\1", clean_text)

        # ---- TURN INTO PARAGRAPHS ----
        # Simple heuristic: split on '।' (Hindi danda) and newline-like breaks.
        # You can tweak this as you like.
        paragraphs: List[str] = [
            p.strip()
            for p in re.split(r"[।\n]", clean_text)
            if p.strip()
        ]

        if not paragraphs:
            raise HTTPException(status_code=500, detail="No paragraphs generated from transcript")

        print(f"Generated {len(paragraphs)} paragraphs from transcript")

        # ---- CREATE CHUNKS & EMBEDDINGS ----
        print(f"Creating chunks and embeddings for video_id={video_id}...")

        try:
            chunk_data = create_chunks_from_paragraphs(
                paragraphs=paragraphs,
                chunk_size_words=chunk_size,
                overlap_words=overlap,
                filename=f"{video_id}.txt",
                video_id=video_id,
            )
        except Exception as e:
            print(f"Error creating chunks / embeddings:\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Chunk/embedding creation failed: {str(e)}",
            )

        if not chunk_data:
            raise HTTPException(
                status_code=500,
                detail="No chunks/embeddings generated from transcript",
            )

        # ---- STORE IN CHROMA ----
        try:
            collection = store_embeddings_in_chroma(
                all_data=chunk_data,
                collection_name=collection_name,
                persist_dir=persist_dir,
                reset_collection=reset_collection,
            )
            print(
                f"Stored {len(chunk_data)} chunks in ChromaDB collection "
                f"'{collection_name}' at '{persist_dir}'"
            )
        except Exception as e:
            print(f"Failed to store embeddings to ChromaDB:\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to persist embeddings to ChromaDB: {str(e)}",
            )

        # ---- BUILD RESPONSE ----
        # FetchedTranscript has metadata:
        caption_type = "generated" if fetched.is_generated else "manual"
        lang_code = fetched.language_code
        lang_label = fetched.language  # e.g. "Hindi (auto-generated)"

        response_data = {
            "status": "ok",
            "video_id": video_id,
            "caption_type": caption_type,
            "language": lang_code,
            "language_label": lang_label,
            "paragraphs_count": len(paragraphs),
            "chunks_created": len(chunk_data),
            "collection_name": collection_name,
            "persist_dir": persist_dir,
            "reset_collection": reset_collection,
        }

        return JSONResponse(response_data)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in endpoint:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
