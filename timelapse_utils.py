import os
import shutil
import subprocess
import glob
from datetime import datetime, timedelta
from logging_setup import setup_logger
from settings import SNAPSHOT_DIR, TIMELAPSE_DIR, CAMERAS

logger = setup_logger("timelapse")


def _stitch_daily(snapshot_dir, timelapse_dir, date_str, label=""):
    day_dir = os.path.join(snapshot_dir, date_str)
    if not os.path.isdir(day_dir):
        logger.warning(f"No snapshot directory for {date_str}{' [' + label + ']' if label else ''}")
        return None
    frames = sorted(glob.glob(os.path.join(day_dir, "*.jpg")))
    if len(frames) < 2:
        logger.warning(f"Only {len(frames)} frames for {date_str}{' [' + label + ']' if label else ''}, skipping")
        return None
    os.makedirs(timelapse_dir, exist_ok=True)
    output_path = os.path.join(timelapse_dir, f"{date_str}.mp4")
    list_file = os.path.join(day_dir, "frames.txt")
    with open(list_file, "w") as f:
        for frame in frames:
            f.write(f"file '{frame}'\nduration 0.15\n")
        f.write(f"file '{frames[-1]}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c:v", "libx264", "-profile:v", "baseline", "-pix_fmt", "yuv420p", "-r", "20", "-g", "1", "-crf", "20", "-tune", "stillimage", "-movflags", "+faststart", output_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"ffmpeg daily timelapse failed{' [' + label + ']' if label else ''}: {result.stderr[-500:]}")
            return None
        logger.info(f"Daily timelapse created: {output_path} from {len(frames)} frames{' [' + label + ']' if label else ''}")
        return output_path
    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg daily timelapse timed out{' [' + label + ']' if label else ''}")
        return None
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


def _stitch_weekly(snapshot_dir, timelapse_dir, label=""):
    today = datetime.now()
    week_end = today.strftime("%Y-%m-%d")
    week_start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    all_frames = []
    for i in range(7):
        day = (today - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        day_dir = os.path.join(snapshot_dir, day)
        if os.path.isdir(day_dir):
            all_frames.extend(sorted(glob.glob(os.path.join(day_dir, "*.jpg"))))
    if len(all_frames) < 10:
        logger.warning(f"Only {len(all_frames)} frames for week {week_start} to {week_end}{' [' + label + ']' if label else ''}, skipping")
        return None
    weekly_dir = os.path.join(timelapse_dir, "weekly")
    os.makedirs(weekly_dir, exist_ok=True)
    output_path = os.path.join(weekly_dir, f"week_{week_start}_to_{week_end}.mp4")
    list_file = os.path.join(timelapse_dir, "weekly_frames.txt")
    with open(list_file, "w") as f:
        for frame in all_frames:
            f.write(f"file '{frame}'\nduration 0.04\n")
        f.write(f"file '{all_frames[-1]}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c:v", "libx264", "-profile:v", "baseline", "-pix_fmt", "yuv420p", "-r", "24", "-g", "1", "-crf", "20", "-tune", "stillimage", "-movflags", "+faststart", output_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error(f"ffmpeg weekly timelapse failed{' [' + label + ']' if label else ''}: {result.stderr[-500:]}")
            return None
        logger.info(f"Weekly timelapse created: {output_path} from {len(all_frames)} frames{' [' + label + ']' if label else ''}")
        return output_path
    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg weekly timelapse timed out{' [' + label + ']' if label else ''}")
        return None
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


def stitch_timelapse(date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    if not CAMERAS:
        return _stitch_daily(SNAPSHOT_DIR, TIMELAPSE_DIR, date_str)
    for cam in CAMERAS:
        _stitch_daily(cam["snapshot_dir"], cam["timelapse_dir"], date_str, cam["label"])


def stitch_weekly_timelapse():
    if not CAMERAS:
        return _stitch_weekly(SNAPSHOT_DIR, TIMELAPSE_DIR)
    for cam in CAMERAS:
        _stitch_weekly(cam["snapshot_dir"], cam["timelapse_dir"], cam["label"])


def list_timelapses():
    if CAMERAS:
        all_daily = []
        all_weekly = []
        for cam in CAMERAS:
            tl_dir = cam["timelapse_dir"]
            prefix = cam["timelapse_serve_prefix"]
            label_prefix = cam["label"]
            if os.path.isdir(tl_dir):
                for f in sorted(glob.glob(os.path.join(tl_dir, "*.mp4")), reverse=True):
                    try:
                        basename = os.path.basename(f)
                        date_str = basename.replace(".mp4", "")
                        size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
                        all_daily.append({"date": date_str, "cam": label_prefix, "cam_id": cam["id"], "filename": basename, "size_mb": size_mb, "url": f"{prefix}/{basename}"})
                    except FileNotFoundError:
                        continue
            weekly_dir = os.path.join(tl_dir, "weekly")
            if os.path.isdir(weekly_dir):
                for f in sorted(glob.glob(os.path.join(weekly_dir, "*.mp4")), reverse=True):
                    try:
                        basename = os.path.basename(f)
                        label = basename.replace("week_", "").replace(".mp4", "").replace("_to_", " to ")
                        size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
                        all_weekly.append({"label": label, "cam": label_prefix, "cam_id": cam["id"], "filename": basename, "size_mb": size_mb, "url": f"{prefix}/weekly/{basename}"})
                    except FileNotFoundError:
                        continue
        return {"daily": all_daily, "weekly": all_weekly}
    if not os.path.isdir(TIMELAPSE_DIR):
        return {"daily": [], "weekly": []}
    daily_files = sorted(glob.glob(os.path.join(TIMELAPSE_DIR, "*.mp4")), reverse=True)
    daily = []
    for f in daily_files:
        try:
            basename = os.path.basename(f)
            date_str = basename.replace(".mp4", "")
            size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
            daily.append({"date": date_str, "filename": basename, "size_mb": size_mb, "url": f"/cam/timelapse/{basename}"})
        except FileNotFoundError:
            continue
    weekly_dir = os.path.join(TIMELAPSE_DIR, "weekly")
    weekly_files = sorted(glob.glob(os.path.join(weekly_dir, "*.mp4")), reverse=True) if os.path.isdir(weekly_dir) else []
    weekly = []
    for f in weekly_files:
        try:
            basename = os.path.basename(f)
            label = basename.replace("week_", "").replace(".mp4", "").replace("_to_", " to ")
            size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
            weekly.append({"label": label, "filename": basename, "size_mb": size_mb, "url": f"/cam/timelapse/weekly/{basename}"})
        except FileNotFoundError:
            continue
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
    dirs_to_clean = [cam["snapshot_dir"] for cam in CAMERAS] if CAMERAS else [SNAPSHOT_DIR]
    tl_dirs_to_clean = [cam["timelapse_dir"] for cam in CAMERAS] if CAMERAS else [TIMELAPSE_DIR]
    for snap_dir in dirs_to_clean:
        if not os.path.isdir(snap_dir):
            continue
        for dirname in os.listdir(snap_dir):
            try:
                dir_date = datetime.strptime(dirname, "%Y-%m-%d")
                if dir_date < cutoff_snap:
                    shutil.rmtree(os.path.join(snap_dir, dirname))
                    logger.info(f"Cleaned up snapshot directory: {snap_dir}/{dirname}")
            except ValueError:
                continue
    for tl_dir in tl_dirs_to_clean:
        if not os.path.isdir(tl_dir):
            continue
        for fname in glob.glob(os.path.join(tl_dir, "*.mp4")):
            basename = os.path.basename(fname).replace(".mp4", "")
            try:
                file_date = datetime.strptime(basename, "%Y-%m-%d")
                if file_date < cutoff_daily:
                    os.remove(fname)
                    logger.info(f"Cleaned up old daily timelapse: {tl_dir}/{basename}.mp4")
            except ValueError:
                continue
