"""
file_utils.py - File system utility functions
"""
from pathlib import Path
from youtube.config import OUT_DIR


def clear_out_dir():
    """Clear all files in OUT_DIR but keep the directory."""
    try:
        for p in OUT_DIR.iterdir():
            try:
                if p.is_file():
                    p.unlink()
            except Exception as e:
                print(f"Warning: Could not delete {p}: {e}")
    except Exception as e:
        print(f"Warning: Could not clear OUT_DIR: {e}")


def cleanup_temp_files():
    """Remove all files in OUT_DIR (keep directory only)."""
    try:
        for p in OUT_DIR.iterdir():
            try:
                if p.is_file():
                    p.unlink()
            except Exception as e:
                print(f"Warning: Could not delete {p}: {e}")
    except Exception as e:
        print(f"Warning: Could not cleanup OUT_DIR: {e}")