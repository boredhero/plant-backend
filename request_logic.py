from settings import VERSION
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
