import os
import glob
import subprocess
import requests
from datetime import datetime
from logging_setup import setup_logger
from settings import CAMERA_SNAPSHOT_URL, SNAPSHOT_DIR, HLS_PLAYLIST, HLS_DIR, CAMERAS

logger = setup_logger("cam_utils")


def capture_snapshot():
    if not CAMERAS:
        return _capture_from_hls(HLS_DIR, SNAPSHOT_DIR)
    results = []
    for cam in CAMERAS:
        results.append(_capture_from_hls(cam["hls_dir"], cam["snapshot_dir"], cam["label"]))
    return results


def _capture_from_hls(hls_dir, base_dir, label=""):
    """Extract a frame from the latest HLS segment (already processed with lagfun/tmedian/color correction)."""
    os.makedirs(base_dir, exist_ok=True)
    today_dir = os.path.join(base_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(today_dir, exist_ok=True)
    filename = datetime.now().strftime("%H%M%S") + ".jpg"
    filepath = os.path.join(today_dir, filename)
    segments = glob.glob(os.path.join(hls_dir, "segment_*.ts"))
    if not segments:
        logger.warning(f"No HLS segments found in {hls_dir}{' [' + label + ']' if label else ''}")
        return None
    latest_segment = max(segments, key=os.path.getmtime)
    try:
        result = subprocess.run(["ffmpeg", "-y", "-i", latest_segment, "-frames:v", "1", "-update", "1", "-q:v", "2", filepath], capture_output=True, text=True, timeout=10)
        if result.returncode != 0 or not os.path.exists(filepath):
            logger.error(f"ffmpeg frame extract failed{' [' + label + ']' if label else ''}: {result.stderr[-300:]}")
            return None
        size = os.path.getsize(filepath)
        logger.info(f"Snapshot saved: {filepath} ({size} bytes){' [' + label + ']' if label else ''}")
        return filepath
    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg frame extract timed out{' [' + label + ']' if label else ''}")
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
