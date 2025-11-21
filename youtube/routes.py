"""
routes.py - API endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional
import traceback
from chat_db.databse import delete_all_records
from youtube.file_utils import clear_out_dir
from youtube.youtube_service import fetch_youtube_transcript
from youtube.vtt_processor import clean_vtt_to_paragraphs
from youtube.config import (
    OUT_DIR,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_PERSIST_DIR,
)

from embedding.chunk_utils import create_chunks_from_paragraphs
from chroma.chroma_store import store_embeddings_in_chroma

transcript_router = APIRouter()


@transcript_router.get(
    "/yt_url_chunks_inmemory",
    summary="Download, clean, chunk and store embeddings in ChromaDB"
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
    Fetch YouTube captions, clean them into paragraphs, create overlapping chunks,
    generate Gemini embeddings, and store them into ChromaDB.
    """

    delete_all_records()

    try:
        # Clean temp directory
        print("Cleaning output directory...")
        clear_out_dir()

        # Parse preferred languages
        preferred = [l.strip() for l in langs.split(",") if l.strip()]
        if not preferred:
            preferred = ["hi", "en"]

        print(f"Using preferred languages: {preferred}")

        # Validate URL
        if not (url.startswith("http://") or url.startswith("https://") or "youtu" in url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        # Fetch captions
        print("Fetching captions...")
        try:
            res = fetch_youtube_transcript(url, preferred_langs=preferred)
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"Unexpected error fetching transcript: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch captions: {str(e)}")

        if res.get("status") != "ok":
            error_msg = res.get("message", "No captions found")
            available = {
                "auto": res.get("available_auto", []),
                "manual": res.get("available_manual", [])
            }
            raise HTTPException(
                status_code=404,
                detail=f"{error_msg}. Available: {available}"
            )

        print(f"Caption type: {res.get('type')}, Language: {res.get('lang')}")

        # Get VTT file path
        file_path = Path(res["file"])
        vtt_candidate = None

        if str(file_path).lower().endswith(".vtt"):
            vtt_candidate = str(file_path)
            print(f"Using VTT file: {vtt_candidate}")
        else:
            sibling = file_path.with_suffix('.vtt')
            if sibling.exists():
                vtt_candidate = str(sibling)
                print(f"Using sibling VTT file: {vtt_candidate}")

        if not vtt_candidate:
            # Fallback: write provided plain text into a temporary vtt file
            print("Creating temporary VTT file from text...")
            tmp_vtt = OUT_DIR / "tmp_for_cleaning.vtt"
            tmp_vtt.write_text(res.get("text", ""), encoding="utf-8")
            vtt_candidate = str(tmp_vtt)

        # Produce cleaned paragraphs
        print("Cleaning captions into paragraphs...")
        try:
            paragraphs = clean_vtt_to_paragraphs(vtt_candidate)
        except FileNotFoundError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            print(f"Error cleaning captions: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to clean captions: {str(e)}")

        if not paragraphs:
            raise HTTPException(status_code=500, detail="No paragraphs generated from captions")

        # Create chunks + embeddings using chunk_utils
        video_id = res.get("id", "video")
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
            print(f"Error creating chunks / embeddings: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Chunk/embedding creation failed: {str(e)}")

        if not chunk_data:
            raise HTTPException(status_code=500, detail="No chunks/embeddings generated from captions")

        # Store in ChromaDB
        try:
            collection = store_embeddings_in_chroma(
                all_data=chunk_data,
                collection_name=collection_name,
                persist_dir=persist_dir,
                reset_collection=reset_collection,
            )
            print(f"Stored {len(chunk_data)} chunks in ChromaDB collection '{collection_name}' at '{persist_dir}'")
        except Exception as e:
            print(f"Failed to store embeddings to ChromaDB: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to persist embeddings to ChromaDB: {str(e)}")

        # Return summary instead of file
        response_data = {
            "status": "ok",
            "video_id": video_id,
            "caption_type": res.get("type"),
            "language": res.get("lang"),
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
        print(f"Unexpected error in endpoint: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
