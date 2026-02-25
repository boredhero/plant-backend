import os
import shutil
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


def stitch_weekly_timelapse():
    today = datetime.now()
    week_end = today.strftime("%Y-%m-%d")
    week_start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    all_frames = []
    for i in range(7):
        day = (today - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        day_dir = os.path.join(SNAPSHOT_DIR, day)
        if os.path.isdir(day_dir):
            all_frames.extend(sorted(glob.glob(os.path.join(day_dir, "*.jpg"))))
    if len(all_frames) < 10:
        logger.warning(f"Only {len(all_frames)} frames for week {week_start} to {week_end}, skipping")
        return None
    weekly_dir = os.path.join(TIMELAPSE_DIR, "weekly")
    os.makedirs(weekly_dir, exist_ok=True)
    output_path = os.path.join(weekly_dir, f"week_{week_start}_to_{week_end}.mp4")
    list_file = os.path.join(TIMELAPSE_DIR, "weekly_frames.txt")
    with open(list_file, "w") as f:
        for frame in all_frames:
            f.write(f"file '{frame}'\nduration 0.04\n")
        f.write(f"file '{all_frames[-1]}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24", "-crf", "23", "-preset", "fast", output_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error(f"ffmpeg weekly timelapse failed: {result.stderr[-500:]}")
            return None
        logger.info(f"Weekly timelapse created: {output_path} from {len(all_frames)} frames")
        return output_path
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg weekly timelapse timed out")
        return None
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


def list_timelapses():
    if not os.path.isdir(TIMELAPSE_DIR):
        return {"daily": [], "weekly": []}
    daily_files = sorted(glob.glob(os.path.join(TIMELAPSE_DIR, "*.mp4")), reverse=True)
    daily = []
    for f in daily_files:
        basename = os.path.basename(f)
        date_str = basename.replace(".mp4", "")
        size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
        daily.append({"date": date_str, "filename": basename, "size_mb": size_mb, "url": f"/cam/timelapse/{basename}"})
    weekly_dir = os.path.join(TIMELAPSE_DIR, "weekly")
    weekly_files = sorted(glob.glob(os.path.join(weekly_dir, "*.mp4")), reverse=True) if os.path.isdir(weekly_dir) else []
    weekly = []
    for f in weekly_files:
        basename = os.path.basename(f)
        label = basename.replace("week_", "").replace(".mp4", "").replace("_to_", " to ")
        size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
        weekly.append({"label": label, "filename": basename, "size_mb": size_mb, "url": f"/cam/timelapse/weekly/{basename}"})
    return {"daily": daily, "weekly": weekly}


def get_latest_timelapse():
    tl = list_timelapses()
    if tl["daily"]:
        return tl["daily"][0]
    return None


def cleanup_old_data(snapshot_keep_days=9, daily_keep_days=30):
    """Delete snapshots older than snapshot_keep_days and daily videos older than daily_keep_days. Weekly videos are kept forever."""
    cutoff_snap = datetime.now() - timedelta(days=snapshot_keep_days)
    cutoff_daily = datetime.now() - timedelta(days=daily_keep_days)
    if os.path.isdir(SNAPSHOT_DIR):
        for dirname in os.listdir(SNAPSHOT_DIR):
            try:
                dir_date = datetime.strptime(dirname, "%Y-%m-%d")
                if dir_date < cutoff_snap:
                    shutil.rmtree(os.path.join(SNAPSHOT_DIR, dirname))
                    logger.info(f"Cleaned up snapshot directory: {dirname}")
            except ValueError:
                continue
    if os.path.isdir(TIMELAPSE_DIR):
        for fname in glob.glob(os.path.join(TIMELAPSE_DIR, "*.mp4")):
            basename = os.path.basename(fname).replace(".mp4", "")
            try:
                file_date = datetime.strptime(basename, "%Y-%m-%d")
                if file_date < cutoff_daily:
                    os.remove(fname)
                    logger.info(f"Cleaned up old daily timelapse: {basename}.mp4")
            except ValueError:
                continue
