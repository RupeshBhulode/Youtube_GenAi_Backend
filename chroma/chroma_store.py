"""
chroma_store.py - Store chunk embeddings into ChromaDB (new client API)
"""
from typing import List, Dict, Any
from pathlib import Path
import chromadb

def _make_chroma_client(persist: bool = True, persist_dir: str = "chromadb_store"):
    """
    Create a Chroma client.

    If persist=True: use PersistentClient (data saved on disk).
    If persist=False: use in-memory Client (data lost when process stops).
    """
    persist_path = Path(persist_dir)
    persist_path.mkdir(parents=True, exist_ok=True)

    if persist:
        return chromadb.PersistentClient(path=str(persist_path))
    else:
        return chromadb.Client()
    
    
def store_embeddings_in_chroma(
    all_data: List[Dict[str, Any]],
    collection_name: str = "video_chunks",
    persist_dir: str = "chromadb_store",
    reset_collection: bool = True,
):
    """
    Store chunk embeddings into a ChromaDB collection.

    all_data: list of dicts from create_chunks_from_paragraphs()
              each item must have: text, embedding, chunk_id, video_id, filename, model
    """
    # Ensure persist directory exists
    persist_path = Path(persist_dir)
    persist_path.mkdir(parents=True, exist_ok=True)

    # ✅ NEW: use PersistentClient instead of Client + Settings
    client = chromadb.PersistentClient(path=str(persist_path))

    # Optionally reset collection
    if reset_collection:
        try:
            client.delete_collection(collection_name)
        except Exception:
            # Ignore if collection does not exist
            pass

    # No embedding_function because we supply embeddings manually
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=None,
    )

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for d in all_data:
        vid = d.get("video_id", "video")
        cid = d.get("chunk_id", 0)

        ids.append(f"{vid}_chunk_{cid}")
        documents.append(d["text"])
        embeddings.append(d["embedding"])
        metadatas.append({
            "chunk_id": cid,
            "video_id": vid,
            "filename": d.get("filename", ""),
            "model": d.get("model", ""),
        })

    if ids:
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    # ✅ In new API, PersistentClient persists automatically – no client.persist()
    return collection




def clear_chromadb(persist_dir: str = "chromadb_store"):
    
    persist_path = Path(persist_dir)
    persist_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_path))

    # Get all existing collections
    collections = client.list_collections()

    for col in collections:
        client.delete_collection(col.name)

    return f"Deleted {len(collections)} collections from ChromaDB."
