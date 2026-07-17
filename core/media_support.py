import os
from typing import Iterable, Tuple

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
VIDEO_EXTS = {".gif", ".mp4", ".mov", ".avi", ".mkv"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS


def is_supported_media_file(path: str) -> bool:
    p = (path or "").strip()
    if not p:
        return False
    ext = os.path.splitext(p)[1].lower()
    return ext in SUPPORTED_EXTS


def classify_media(path: str) -> Tuple[str, str]:
    ext = os.path.splitext((path or "").strip())[1].lower()
    if ext in IMAGE_EXTS:
        return "image", ext
    if ext in VIDEO_EXTS:
        return "video", ext
    return "unknown", ext


def list_supported_media_files(directory: str) -> Iterable[str]:
    if not directory:
        return []
    try:
        names = sorted(os.listdir(directory))
    except Exception:
        return []
    out = []
    for name in names:
        p = os.path.join(directory, name)
        if os.path.isfile(p) and is_supported_media_file(p):
            out.append(p)
    return out
