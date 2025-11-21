"""
vtt_processor.py - VTT file processing and cleaning
"""
from pathlib import Path
import re
from typing import List
from youtube.config import MAX_PARA_CHARS, MAX_LINES_WITHOUT_PUNCT


def vtt_to_plaintext(path: str) -> str:
    """Convert VTT file to plain text."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"VTT file not found: {path}")
    
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise RuntimeError(f"Failed to read VTT file {path}: {e}")
    
    txt = re.sub(r'^\ufeff', '', txt)
    txt = re.sub(r'^\s*WEBVTT.*\n', '', txt, flags=re.IGNORECASE)
    lines = []
    
    for line in txt.splitlines():
        s = line.strip()
        if re.fullmatch(r'\d+', s):
            continue
        if re.match(r'^\d{1,2}:\d{2}(?::\d{2})?[\.,]?\d{0,3}\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?[\.,]?\d{0,3}', s):
            continue
        if s.upper().startswith("NOTE") or s.startswith("STYLE") or s.startswith("REGION"):
            continue
        s = re.sub(r'<\d{1,2}:\d{2}(?::\d{2})?[\.,]?\d{0,3}>', '', s)
        s = re.sub(r'<\/?[^>]+>', '', s)
        if s:
            lines.append(s)
    
    plain = "\n".join(lines)
    plain = re.sub(r'\n{2,}', '\n\n', plain)
    return plain.strip()


def clean_vtt_to_paragraphs(
    vtt_path: str,
    max_para_chars: int = MAX_PARA_CHARS,
    max_lines_without_punct: int = MAX_LINES_WITHOUT_PUNCT
) -> List[str]:
    """Return a list of cleaned paragraphs from VTT file."""
    p = Path(vtt_path)
    if not p.exists():
        raise FileNotFoundError(f"VTT file not found: {vtt_path}")
    
    try:
        raw = p.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        raise RuntimeError(f"Failed to read VTT file: {e}")

    # Clean VTT formatting
    raw = re.sub(r'^\s*WEBVTT.*\n', '', raw, flags=re.IGNORECASE | re.MULTILINE)
    raw = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?[\.,]?\d{0,3}\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?[\.,]?\d{0,3}.*', '', raw)
    raw = re.sub(r'<\d{1,2}:\d{2}(?::\d{2})?[\.,]?\d{0,3}>', '', raw)
    raw = re.sub(r'<\/?[^>]+>', '', raw)
    raw = re.sub(r'align:\w+\s*', '', raw)
    raw = re.sub(r'position:\d+%','', raw)

    # Process lines
    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln and not re.fullmatch(r'\d+', ln)]
    lines = [re.sub(r'\s+', ' ', ln) for ln in lines]

    # Deduplicate consecutive identical lines
    deduped = []
    prev = None
    for ln in lines:
        if ln != prev:
            deduped.append(ln)
        prev = ln

    # Build sentences
    sentence_end_re = re.compile(r'[।\.\?\!]\s*$')
    sentences = []
    buf = ""
    lines_without_punct = 0
    
    for ln in deduped:
        if not buf:
            buf = ln
        else:
            buf = buf + " " + ln
        
        if sentence_end_re.search(ln):
            sentences.append(buf.strip())
            buf = ""
            lines_without_punct = 0
        else:
            lines_without_punct += 1
            if lines_without_punct >= max_lines_without_punct:
                sentences.append(buf.strip())
                buf = ""
                lines_without_punct = 0
    
    if buf:
        sentences.append(buf.strip())

    # Group sentences into paragraphs
    paragraphs = []
    cur_para = []
    cur_len = 0
    
    for s in sentences:
        cur_para.append(s)
        cur_len += len(s)
        if cur_len >= max_para_chars or len(cur_para) >= 3:
            paragraphs.append(" ".join(cur_para).strip())
            cur_para = []
            cur_len = 0
    
    if cur_para:
        paragraphs.append(" ".join(cur_para).strip())

    # Clean spacing before punctuation
    paragraphs = [re.sub(r'\s+([।\.\?\!,;:])', r'\1', para) for para in paragraphs]
    
    # Filter out empty paragraphs
    paragraphs = [p for p in paragraphs if p and p.strip()]
    
    print(f"Generated {len(paragraphs)} paragraphs")
    return paragraphs