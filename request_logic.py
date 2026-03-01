import os
import time
import threading
from settings import VERSION, DATA_DIR
from cam_utils import check_hls_health, check_camera_health
from timelapse_utils import list_timelapses, get_latest_timelapse
from helpers import get_unix_timestamp


def handle_info():
    return {"version": VERSION, "service": "plant-backend", "timestamp": get_unix_timestamp()}


def handle_cam_status():
    hls = check_hls_health()
    camera = check_camera_health()
    if hls["status"] == "live":
        overall = "live"
    elif camera["status"] == "online":
        overall = "degraded"
    else:
        overall = "offline"
    return {"overall": overall, "hls": hls, "camera": camera, "timestamp": get_unix_timestamp()}


def handle_timelapse_list():
    tl = list_timelapses()
    return {"daily": tl["daily"], "weekly": tl["weekly"], "timestamp": get_unix_timestamp()}


def handle_timelapse_latest():
    latest = get_latest_timelapse()
    if latest is None:
        return {"error": "no_timelapses", "timestamp": get_unix_timestamp()}, 404
    return {"timelapse": latest, "timestamp": get_unix_timestamp()}


_reset_lock = threading.Lock()
_reset_history = {}  # ip -> list of timestamps
RESET_WINDOW_SEC = 300
RESET_MAX_IN_WINDOW = 10
RESET_COOLDOWN_SEC = 60
_last_reset_per_cam = {}


def _get_client_ip():
    from flask import request
    return request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr


def handle_reset_stream(cam_id):
    now = get_unix_timestamp()
    ip = _get_client_ip()
    with _reset_lock:
        # Per-IP spam detection: >10 resets in 5 minutes triggers exponential backoff
        history = _reset_history.get(ip, [])
        history = [t for t in history if now - t < RESET_WINDOW_SEC]
        if len(history) >= RESET_MAX_IN_WINDOW:
            backoff = min(2 ** (len(history) - RESET_MAX_IN_WINDOW) * 60, 3600)
            _reset_history[ip] = history
            return {"status": "rate_limited", "message": f"Too many resets. Try again in {backoff}s.", "retry_after": backoff, "timestamp": now}, 429
        # Per-camera cooldown: 60 seconds between resets of the same camera
        last = _last_reset_per_cam.get(cam_id, 0)
        if now - last < RESET_COOLDOWN_SEC:
            remaining = RESET_COOLDOWN_SEC - (now - last)
            return {"status": "cooldown", "message": f"Camera was just reset. Wait {remaining}s.", "retry_after": remaining, "timestamp": now}, 429
        history.append(now)
        _reset_history[ip] = history
        _last_reset_per_cam[cam_id] = now
    trigger_file = os.path.join(DATA_DIR, f"reset_cam{cam_id}.trigger")
    with open(trigger_file, "w") as f:
        f.write(str(now))
    return {"status": "ok", "cam": cam_id, "timestamp": now}
