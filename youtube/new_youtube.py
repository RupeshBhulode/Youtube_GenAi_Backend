import re
import time
import traceback
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

# ⛔️ OLD: direct YouTube transcript fetch (causing IP issues on Render)
# from youtube_transcript_api import YouTubeTranscriptApi
# from youtube.config import OUT_DIR, YOUTUBE_CLIENTS, MAX_CLIENTS_TRY, DEFAULT_LANGUAGES

from youtube.config import (
    OUT_DIR,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_PERSIST_DIR,
)
from embedding.chunk_utils import create_chunks_from_paragraphs
from chroma.chroma_store import store_embeddings_in_chroma
from chat_db.databse import delete_all_records
from youtube.file_utils import clear_out_dir

# ✅ NEW: Supadata transcript service (works around YouTube IP blocking)
from supadata import Supadata

# ⚠️ Hardcoded API Key — okay for now, but don't commit this to public repos
SUPADATA_API_KEY = "sd_0ae31fca72274fbc1482b0a4ff5a05ee"
supadata = Supadata(api_key=SUPADATA_API_KEY)

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
    summary="My Application Old new ",
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
    Fetch YouTube transcript via Supadata,
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

        # Extract video_id for filenames/metadata, but Supadata will use full URL
        video_id = extract_video_id(url)
        print(f"Resolved video_id = {video_id}")

        # ---- FETCH TRANSCRIPT VIA SUPADATA (new logic) ----
        try:
            # choose first preferred language if possible, fallback to 'en'
            chosen_lang = preferred[0] if preferred else "en"

            # Important: pass the original URL (not only video_id)
            transcript_result = supadata.transcript(
                url=url,
                lang=chosen_lang,
                text=True,
                mode="auto",  # 'native', 'auto', or 'generate'
            )
            print(f"Got transcript result or job ID from Supadata: {transcript_result}")
        except Exception as e:
            print(f"Error while fetching transcript from Supadata:\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=502,
                detail=f"Transcript service error: {str(e)}",
            )

        # ---- RESOLVE TRANSCRIPT TEXT FROM SUPADATA RESPONSE ----
        raw_text = ""
        status = "unknown"

        # Case 1: direct string
        if isinstance(transcript_result, str):
            status = "completed"
            raw_text = transcript_result

        # Case 2: object with 'content'
        elif hasattr(transcript_result, "content"):
            status = "completed"
            raw_text = transcript_result.content

        # Case 3: async job, we need to poll get_job_status
        elif hasattr(transcript_result, "job_id"):
            job_id = transcript_result.job_id
            print(f"Supadata returned job_id={job_id}, polling for completion...")

            # simple polling loop (up to ~20 seconds)
            for _ in range(10):
                job = supadata.transcript.get_job_status(job_id)
                status = getattr(job, "status", "unknown")
                print(f"[Supadata job poll] status={status}")

                if status == "completed":
                    raw_text = getattr(job, "content", "")
                    break
                elif status in ("failed", "error"):
                    raise HTTPException(
                        status_code=500,
                        detail=f"Transcript job failed with status: {status}",
                    )

                time.sleep(2)

            if not raw_text:
                # we didn't get a completed transcript within polling limit
                raise HTTPException(
                    status_code=504,
                    detail=f"Transcript job did not complete in time (last status: {status})",
                )

        else:
            # Fallback: just string-ify whatever Supadata returned
            status = "completed"
            raw_text = str(transcript_result)

        if not raw_text.strip():
            raise HTTPException(
                status_code=500,
                detail="Transcript text is empty from Supadata",
            )

        # ---- CLEAN TEXT ----
        # join spaces & tidy punctuation
        clean_text = re.sub(r"\s+", " ", raw_text).strip()
        clean_text = re.sub(r" ([.,!?])", r"\1", clean_text)

        # ---- TURN INTO PARAGRAPHS ----
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
        # We don't get manual/auto flags from Supadata like youtube_transcript_api,
        # so we mark them as 'unknown' / based on chosen_lang.
        caption_type = "unknown"
        lang_code = chosen_lang
        lang_label = chosen_lang

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
            "supadata_job_status": status,
        }

        return JSONResponse(response_data)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in endpoint:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

