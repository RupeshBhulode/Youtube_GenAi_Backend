"""
youtube_service.py - YouTube caption download and metadata extraction
"""
from pathlib import Path
from yt_dlp import YoutubeDL
from typing import Optional, List
import time
from youtube.config import (
    OUT_DIR,
    YOUTUBE_CLIENTS,
    MAX_CLIENTS_TRY,
    DEFAULT_LANGUAGES,
    COOKIES_FILE,      # 🔹 make sure this is defined in config.py
)


def inspect_metadata(url: str) -> dict:
    """Extract video metadata including available subtitles."""
    try:
        with YoutubeDL({
            "quiet": True,
            "no_warnings": True,
            "cookiefile": str(COOKIES_FILE),   # 🔹 use cookies for metadata too
        }) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"Error in inspect_metadata: {e}")
        raise RuntimeError(f"Failed to extract info for {url}: {e}")
    
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    vid = info.get("id") or info.get("display_id") or url.split("v=")[-1].split("&")[0]
    
    return {
        "id": vid,
        "manual": manual,
        "auto": auto,
        "full_info_sample": {
            k: info.get(k) for k in ("id", "title", "uploader")
        }
    }


def download_auto_caption(
    url: str,
    video_id: str,
    lang: str = "en",
    player_client: Optional[str] = None,
    out_dir: Path = OUT_DIR,
    wait_after: float = 0.25
) -> Optional[str]:
    """Download automatic captions for given language."""
    opts = {
        "skip_download": True,
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "writesubtitles": False,
        "writeautomaticsub": True,
        "subtitleslangs": [lang] if lang else None,
        "subtitlesformat": "vtt",
        "cookiefile": str(COOKIES_FILE),   # 🔹 use cookies for auto captions
    }
    
    if player_client:
        opts["extractor_args"] = {"youtube": f"player_client={player_client}"}
    
    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"Warning: Download failed for lang={lang}, client={player_client}: {e}")
        # You could optionally detect 429 here and bubble it up
        # if "HTTP Error 429" in str(e):
        #     raise RuntimeError("YOUTUBE_RATE_LIMIT")
        pass

    # We already know the video_id from metadata; no need to call extract_info again
    vid = video_id
    if not vid:
        print("Warning: Could not determine video ID")
        return None

    # Look for downloaded files
    candidates = []
    for ext in ("vtt", "srt"):
        candidates.append(out_dir / f"{vid}.{ext}")

    lang_safe = lang.replace("-", "_") if lang else ""
    if lang_safe:
        for ext in ("vtt", "srt"):
            candidates.append(out_dir / f"{vid}.{lang_safe}.{ext}")
            candidates.append(out_dir / f"{vid}.{lang}.{ext}")
            for suffix in ("web_html5", "web", "desktop", "android", "ios", "tv_html5"):
                candidates.append(out_dir / f"{vid}.{lang_safe}.{suffix}.{ext}")
                candidates.append(out_dir / f"{vid}.{lang}.{suffix}.{ext}")

    for p in candidates:
        if p.exists():
            print(f"Found caption file: {p}")
            return str(p)

    # Try glob patterns
    glob_patterns = [f"{vid}*.vtt", f"{vid}*.srt", f"{vid}-*.vtt", f"{vid}-*.srt"]
    for pat in glob_patterns:
        found = list(out_dir.glob(pat))
        if found:
            print(f"Found caption file via glob: {found[0]}")
            return str(found[0])

    time.sleep(wait_after)
    return None


def fetch_youtube_transcript(
    url: str,
    preferred_langs: Optional[List[str]] = None,
    max_clients_try: int = MAX_CLIENTS_TRY
) -> dict:
    """Fetch YouTube transcript with automatic or manual captions."""
    if preferred_langs is None:
        preferred_langs = DEFAULT_LANGUAGES
    
    print(f"Fetching transcript for URL: {url}")
    print(f"Preferred languages: {preferred_langs}")
    
    try:
        meta = inspect_metadata(url)
    except Exception as e:
        print(f"Error getting metadata: {e}")
        raise
    
    vid = meta["id"]
    print(f"Video ID: {vid}")
    
    auto_langs = list(meta["auto"].keys())
    print(f"Available auto captions: {auto_langs}")
    print(f"Available manual subtitles: {list(meta['manual'].keys())}")
    
    # Build ordered language list (only from available auto_langs)
    ordered = []
    for p in (preferred_langs or []):
        if p in auto_langs and p not in ordered:
            ordered.append(p)
    if not ordered:
        # fallback: try at most first 3 auto languages to avoid hammering
        ordered = auto_langs[:3]

    print(f"Languages that will actually be tried: {ordered}")

    clients = YOUTUBE_CLIENTS
    
    # Try automatic captions
    for lang in ordered:
        print(f"\nTrying language: {lang}")
        for client in clients[:max_clients_try]:
            client_label = client or "default"
            print(f"  Trying player_client={client_label}...", end=" ")
            
            # ✅ pass video_id to avoid extra extract_info calls
            path = download_auto_caption(url, video_id=vid, lang=lang, player_client=client)
            if path:
                print("SUCCESS")
                from youtube.vtt_processor import vtt_to_plaintext
                try:
                    text = vtt_to_plaintext(path)
                    return {
                        "status": "ok",
                        "type": "auto",
                        "lang": lang,
                        "player_client": client_label,
                        "file": path,
                        "text": text,
                        "id": vid
                    }
                except Exception as e:
                    print(f"Error converting VTT to text: {e}")
                    continue
            else:
                print("not found")

    # Try manual subtitles as fallback
    if meta["manual"]:
        print("\nNo auto captions found. Trying manual subtitles...")
        manual_langs = list(meta["manual"].keys()) or ordered
        tried = set()
        
        for lang_try in ([ordered[0]] if ordered else []) + manual_langs:
            if not lang_try or lang_try in tried:
                continue
            tried.add(lang_try)
            
            print(f"Trying manual subtitle: {lang_try}")
            
            opts = {
                "skip_download": True,
                "outtmpl": str(OUT_DIR / "%(id)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "writesubtitles": True,
                "writeautomaticsub": False,
                "subtitleslangs": [lang_try],
                "subtitlesformat": "vtt",
                "cookiefile": str(COOKIES_FILE),   # 🔹 use cookies for manual subs too
            }
            
            try:
                with YoutubeDL(opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                print(f"Manual subtitle download failed: {e}")
                continue
            
            from youtube.vtt_processor import vtt_to_plaintext
            
            # Check for downloaded files
            for ext in ("vtt", "srt"):
                p = OUT_DIR / f"{vid}.{lang_try}.{ext}"
                if p.exists():
                    try:
                        text = vtt_to_plaintext(str(p))
                        return {
                            "status": "ok",
                            "type": "manual",
                            "lang": lang_try,
                            "file": str(p),
                            "text": text,
                            "id": vid
                        }
                    except Exception as e:
                        print(f"Error converting manual VTT to text: {e}")
                        continue
            
            # Check base filename
            for ext in ("vtt", "srt"):
                p2 = OUT_DIR / f"{vid}.{ext}"
                if p2.exists():
                    try:
                        text = vtt_to_plaintext(str(p2))
                        return {
                            "status": "ok",
                            "type": "manual",
                            "lang": lang_try,
                            "file": str(p2),
                            "text": text,
                            "id": vid
                        }
                    except Exception as e:
                        print(f"Error converting manual VTT to text: {e}")
                        continue
    
    return {
        "status": "none",
        "message": "No downloadable automatic or manual captions found.",
        "available_auto": auto_langs,
        "available_manual": list(meta["manual"].keys())
    }
