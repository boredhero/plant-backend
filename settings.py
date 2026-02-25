import os
import yaml
from dotenv import load_dotenv

load_dotenv()


def _load_info():
    info_path = os.path.join(os.path.dirname(__file__), "info.yml")
    if os.path.exists(info_path):
        with open(info_path, "r") as f:
            return yaml.safe_load(f)
    return {}


INFO = _load_info()
VERSION = INFO.get("version", "0.0.0")
CAMERA_HOST = os.environ.get("CAMERA_HOST", "")
CAMERA_PORT = int(os.environ.get("CAMERA_PORT", "8080"))
HLS_DIR = os.environ.get("HLS_DIR", "/var/www/planting/cam/hls")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
TIMELAPSE_DIR = os.path.join(DATA_DIR, "timelapse")
SNAPSHOT_INTERVAL_MIN = int(os.environ.get("SNAPSHOT_INTERVAL_MIN", "5"))
TIMELAPSE_STITCH_HOUR = int(os.environ.get("TIMELAPSE_STITCH_HOUR", "23"))
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5050"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
CAMERA_SNAPSHOT_URL = f"http://{CAMERA_HOST}:{CAMERA_PORT}/?action=snapshot"
CAMERA_STREAM_URL = f"http://{CAMERA_HOST}:{CAMERA_PORT}/?action=stream"
HLS_PLAYLIST = os.path.join(HLS_DIR, "stream.m3u8")
