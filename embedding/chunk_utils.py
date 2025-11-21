# chunk_utils.py
from pathlib import Path
from typing import List, Dict, Any
import json
from google import genai
from google.genai import types

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768

# Initialize Gemini client
client = genai.Client(api_key="AIzaSyAWF7AtLA7jC2j8GfxJS6thasdxiQa1X7Y")

def create_chunks_from_paragraphs(
    paragraphs: List[str],
    chunk_size_words: int = 300,
    overlap_words: int = 50,
    filename: str = "",
    video_id: str = ""
) -> List[Dict[str, Any]]:
    """
    Creates overlapping text chunks from paragraphs and generates embeddings.
    
    Args:
        paragraphs: List of paragraph strings
        chunk_size_words: Number of words per chunk
        overlap_words: Number of overlapping words between chunks
        filename: Optional filename for metadata
        video_id: Optional video ID for metadata
    
    Returns:
        List of dictionaries containing chunk data with embeddings
    """
    # Normalize and join paragraphs
    normalized_text = "\n\n".join(
        p.strip() for p in paragraphs if p and p.strip()
    )

    words = normalized_text.split()
    if not words:
        return []

    # Validate parameters
    if overlap_words >= chunk_size_words:
        raise ValueError("overlap_words must be less than chunk_size_words")
    if overlap_words < 0:
        overlap_words = 0

    step = chunk_size_words - overlap_words
    all_chunks = []
    start_idx = 0
    chunk_id = 1

    # Create overlapping chunks
    while start_idx < len(words):
        end_idx = min(start_idx + chunk_size_words, len(words))
        chunk_text = " ".join(words[start_idx:end_idx])

        # Generate embedding for this chunk
        result = client.models.embed_content(
            model=EMBED_MODEL,
            contents=chunk_text,
            config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM)
        )
        
        embedding = result.embeddings[0].values
        
        # Store chunk with all necessary information
        chunk_data = {
            "chunk_id": chunk_id,
            "text": chunk_text,  # CRITICAL: Store the actual text
            "embedding": embedding,
            "embedding_dim": len(embedding),
            "model": EMBED_MODEL,
            "filename": filename,
            "video_id": video_id
        }
        
        all_chunks.append(chunk_data)
        chunk_id += 1
        start_idx += step

        if end_idx >= len(words):
            break

    return all_chunks


def save_embeddings_json(all_data: List[Dict[str, Any]], out_file: str = "embeddings.json") -> str:
    """
    Saves embedding data to a JSON file.
    
    Args:
        all_data: List of chunk dictionaries
        out_file: Output file path
    
    Returns:
        Absolute path to the saved file
    """
    Path(out_file).write_text(
        json.dumps(all_data, ensure_ascii=False, indent=2), 
        encoding="utf-8"
    )
    return str(Path(out_file).resolve())