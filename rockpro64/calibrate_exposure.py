#!/usr/bin/env python3
"""Auto-calibrate camera exposure to eliminate LED PWM banding.
Sweeps exposure_absolute values and picks the one with minimum
horizontal brightness variance (least visible banding).
Caches result to /etc/ustreamer_exposure so subsequent boots are instant.
Requires: python3, python3-pil, v4l2-ctl, ustreamer running on localhost:8080
"""
import subprocess, sys, time, io, os

CACHE_FILE = "/etc/ustreamer_exposure"
SNAPSHOT_URL = "http://localhost:8080/?action=snapshot"
# Covers multiples of common LED PWM periods: 100Hz, 120Hz, 200Hz, 500Hz, 1kHz+
EXPOSURE_VALUES = [20, 30, 40, 50, 60, 70, 80, 83, 90, 100, 110, 120, 130, 140, 150, 160, 167, 170, 180, 190, 200, 210, 220, 230, 240, 250]
SETTLE_TIME = 1.5
SAMPLES = 2


def get_device():
    try:
        with open("/run/ustreamer_device") as f:
            return f.read().strip()
    except Exception:
        return "/dev/video0"


def wait_for_ustreamer(timeout=30):
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(SNAPSHOT_URL, timeout=2).read()
            return True
        except Exception:
            time.sleep(1)
    return False


def grab_snapshot():
    import urllib.request
    from PIL import Image
    data = urllib.request.urlopen(SNAPSHOT_URL, timeout=5).read()
    return Image.open(io.BytesIO(data)).convert('L')


def banding_score(img):
    """Score horizontal banding intensity. Lower = less banding.
    Uses high-pass filtering on row means to isolate periodic banding
    from actual image content (which varies slowly across rows)."""
    pixels = list(img.getdata())
    w, h = img.size
    row_means = [sum(pixels[y * w:(y + 1) * w]) / w for y in range(h)]
    global_mean = sum(row_means) / len(row_means)
    if global_mean < 10:
        return float('inf')
    # Subtract smoothed version (100px moving average) to isolate high-frequency banding
    window = min(100, h // 4)
    smoothed = []
    for i in range(len(row_means)):
        lo = max(0, i - window // 2)
        hi = min(len(row_means), i + window // 2 + 1)
        smoothed.append(sum(row_means[lo:hi]) / (hi - lo))
    residuals = [row_means[i] - smoothed[i] for i in range(len(row_means))]
    rms = (sum(r * r for r in residuals) / len(residuals)) ** 0.5
    return rms / global_mean * 1000  # normalize by brightness


def v4l2(device, *args):
    subprocess.run(["v4l2-ctl", "-d", device] + list(args), capture_output=True)


def set_manual_exposure(device, value):
    v4l2(device, "--set-ctrl=exposure_auto=1")
    v4l2(device, f"--set-ctrl=exposure_absolute={value}")


def set_auto_exposure(device):
    v4l2(device, "--set-ctrl=exposure_auto=3", "--set-ctrl=power_line_frequency=2")


def main():
    force = "--force" in sys.argv
    device = get_device()
    # Use cached result if available (instant on subsequent boots)
    if not force and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cached = f.read().strip()
        if cached == "auto":
            print("Cached result: auto exposure")
            set_auto_exposure(device)
            return
        if cached.isdigit():
            print(f"Using cached exposure_absolute={cached}")
            set_manual_exposure(device, int(cached))
            v4l2(device, "--set-ctrl=power_line_frequency=2")
            return
    print("Waiting for ustreamer...")
    if not wait_for_ustreamer():
        print("ustreamer not responding, falling back to auto exposure")
        set_auto_exposure(device)
        return
    # Baseline: measure banding with auto exposure
    set_auto_exposure(device)
    time.sleep(2)
    try:
        auto_scores = [banding_score(grab_snapshot()) for _ in range(SAMPLES)]
        auto_score = sum(auto_scores) / len(auto_scores)
        print(f"Auto exposure banding score: {auto_score:.2f}")
    except Exception as e:
        print(f"Baseline capture failed: {e}, keeping auto exposure")
        return
    # Sweep exposure values to find the one that minimizes banding
    best_val = None
    best_score = auto_score
    print(f"Sweeping {len(EXPOSURE_VALUES)} exposure values...")
    for val in EXPOSURE_VALUES:
        try:
            set_manual_exposure(device, val)
            time.sleep(SETTLE_TIME)
            scores = []
            for _ in range(SAMPLES):
                scores.append(banding_score(grab_snapshot()))
                time.sleep(0.3)
            score = sum(scores) / len(scores)
            marker = " <-- best so far" if score < best_score else ""
            print(f"  exposure={val:3d}  score={score:.2f}{marker}")
            if score < best_score:
                best_score = score
                best_val = val
        except Exception as e:
            print(f"  exposure={val:3d}  error: {e}")
    # Only switch to manual if at least 30% improvement over auto
    if best_val is not None and best_score < auto_score * 0.7:
        print(f"Winner: exposure_absolute={best_val} (score={best_score:.2f} vs auto={auto_score:.2f})")
        set_manual_exposure(device, best_val)
        v4l2(device, "--set-ctrl=power_line_frequency=2")
        with open(CACHE_FILE, 'w') as f:
            f.write(str(best_val))
    else:
        print(f"No significant improvement (best={best_score:.2f} vs auto={auto_score:.2f}), keeping auto")
        set_auto_exposure(device)
        with open(CACHE_FILE, 'w') as f:
            f.write("auto")


if __name__ == "__main__":
    main()
