import os
import requests
from datetime import datetime
from logging_setup import setup_logger
from settings import CAMERA_SNAPSHOT_URL, SNAPSHOT_DIR, HLS_PLAYLIST

logger = setup_logger("cam_utils")


def capture_snapshot():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    today_dir = os.path.join(SNAPSHOT_DIR, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(today_dir, exist_ok=True)
    filename = datetime.now().strftime("%H%M%S") + ".jpg"
    filepath = os.path.join(today_dir, filename)
    try:
        resp = requests.get(CAMERA_SNAPSHOT_URL, timeout=10)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        logger.info(f"Snapshot saved: {filepath} ({len(resp.content)} bytes)")
        return filepath
    except Exception as e:
        logger.error(f"Snapshot capture failed: {e}")
        return None


def check_hls_health():
    if not os.path.exists(HLS_PLAYLIST):
        return {"status": "offline", "reason": "playlist_missing"}
    try:
        mtime = os.path.getmtime(HLS_PLAYLIST)
        age = (datetime.now().timestamp() - mtime)
        if age > 30:
            return {"status": "stale", "reason": "playlist_stale", "age_seconds": round(age)}
        with open(HLS_PLAYLIST, "r") as f:
            lines = f.readlines()
        segment_count = sum(1 for l in lines if l.strip().endswith(".ts"))
        return {"status": "live", "segments": segment_count, "age_seconds": round(age)}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def check_camera_health():
    try:
        resp = requests.get(CAMERA_SNAPSHOT_URL, timeout=5)
        resp.raise_for_status()
        return {"status": "online", "content_length": len(resp.content)}
    except Exception as e:
        return {"status": "offline", "reason": str(e)}
