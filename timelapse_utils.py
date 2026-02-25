import os
import subprocess
import glob
from datetime import datetime, timedelta
from logging_setup import setup_logger
from settings import SNAPSHOT_DIR, TIMELAPSE_DIR

logger = setup_logger("timelapse")


def stitch_timelapse(date_str=None):
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=0)).strftime("%Y-%m-%d")
    day_dir = os.path.join(SNAPSHOT_DIR, date_str)
    if not os.path.isdir(day_dir):
        logger.warning(f"No snapshot directory for {date_str}")
        return None
    frames = sorted(glob.glob(os.path.join(day_dir, "*.jpg")))
    if len(frames) < 2:
        logger.warning(f"Only {len(frames)} frames for {date_str}, skipping timelapse")
        return None
    os.makedirs(TIMELAPSE_DIR, exist_ok=True)
    output_path = os.path.join(TIMELAPSE_DIR, f"{date_str}.mp4")
    list_file = os.path.join(day_dir, "frames.txt")
    with open(list_file, "w") as f:
        for frame in frames:
            f.write(f"file '{frame}'\nduration 0.15\n")
        f.write(f"file '{frames[-1]}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "20", "-crf", "23", "-preset", "fast", output_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"ffmpeg timelapse failed: {result.stderr[-500:]}")
            return None
        logger.info(f"Timelapse created: {output_path} from {len(frames)} frames")
        return output_path
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg timelapse timed out")
        return None
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


def list_timelapses():
    if not os.path.isdir(TIMELAPSE_DIR):
        return []
    files = sorted(glob.glob(os.path.join(TIMELAPSE_DIR, "*.mp4")), reverse=True)
    result = []
    for f in files:
        basename = os.path.basename(f)
        date_str = basename.replace(".mp4", "")
        size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
        result.append({"date": date_str, "filename": basename, "size_mb": size_mb, "url": f"/cam/timelapse/{basename}"})
    return result


def get_latest_timelapse():
    tl = list_timelapses()
    return tl[0] if tl else None
