# plant-backend

Flask API backend for a live plant camera streaming and timelapse system. Handles snapshot capture, timelapse generation, camera health monitoring, and serves as the data layer for [plant-frontend](https://github.com/boredhero/plant-frontend).

**Live site:** [planting.martinospizza.dev](https://planting.martinospizza.dev)

## Architecture

A RockPro64 SBC runs a USB webcam via [ustreamer](https://github.com/pikvm/ustreamer) (MJPEG over HTTP). The main server pulls the MJPEG stream and transcodes it to HLS using ffmpeg with Intel VAAPI hardware encoding. This backend runs alongside the transcoder in Docker, capturing snapshots for timelapse generation and exposing a REST API for stream health and timelapse data.

```
USB Cam -> ustreamer (MJPEG) -> ffmpeg VAAPI (HLS) -> nginx -> hls.js
                |
                +-> Flask backend -> snapshots -> daily/weekly timelapse MP4s
```

## Interesting Technical Decisions

### LED Flicker Band Elimination

Cheap LED grow lights produce 120Hz flicker from rectification ripple. Combined with the webcam's rolling shutter, this creates horizontal brightness bands that scroll through the frame. Two lights out of phase with each other make the pattern even more complex.

The solution is a two-stage temporal max filter in the ffmpeg pipeline:

1. **`lagfun=decay=0.9995`** -- An exponential running maximum. Each pixel holds its brightest observed value, decaying 0.05% per frame. This covers the slow beat frequency between the two out-of-phase LED sources without any frame buffering overhead.
2. **`tmedian=radius=3:percentile=1`** -- A hard pixel-wise maximum across 7 consecutive frames. Applied after lagfun, this cleans up the tiny decay artifacts that would otherwise be visible as faint scrolling motion. The `percentile=1` parameter flips the temporal median filter into a temporal maximum filter.

The key insight: since the camera is static, the "correct" brightness for every pixel exists in a nearby frame -- the temporal max just selects it. This approach was arrived at iteratively; naive temporal averaging (`tmix`) caused severe ghosting, and single-stage `tmedian` with enough radius to cover the beat frequency (radius=15, 31 frames) consumed 618% CPU on an i7-6700K. The lagfun+tmedian hybrid achieves the same visual result at ~220% CPU.

### Color Correction Calibrated Against Ground Truth

The temporal max biases the image toward the grow lights' warm spectrum (always picking the brightest = warmest illumination). Color correction was calibrated by sampling RGB values from matching regions (white surface, green cells, brown soil) in the stream versus a Pixel phone camera as ground truth.

The critical finding: highlights (whites) needed cooling (less red, more blue) while midtones (browns) needed the opposite correction (neutral red, less blue). Applying a uniform color shift in either direction made one look right and the other wrong. The `colorbalance` filter's per-tonal-range RGB controls (`rm`/`bm` for midtones, `rh`/`bh` for highlights) solved this by correcting each brightness range independently.

### Camera Auto-Detection and Exposure Calibration

USB device numbering can change across reboots. `find_camera.sh` locates the correct `/dev/videoN` by filtering for UVC-class capture devices rather than hardcoding a device path.

`calibrate_exposure.py` attempts to sync the camera's manual exposure time to the LED PWM period by sweeping exposure values and measuring horizontal row-brightness variance in captured frames. Results are cached to `/etc/ustreamer_exposure` so subsequent boots are instant. Falls back to auto-exposure if no significant improvement is found.

### MJPEG Timestamp Handling

MJPEG streams from ustreamer have no proper PTS timestamps. Without `-use_wallclock_as_timestamps 1` and `-fflags +genpts`, ffmpeg invents timestamps that drift, producing HLS segments with inconsistent durations. This was the primary cause of periodic stream freezing before being identified and fixed.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/info` | GET | Service version and status |
| `/cam/status` | GET | Camera and HLS stream health |
| `/timelapse` | GET | List daily and weekly timelapse videos |
| `/timelapse/latest` | GET | Most recent timelapse |

## Timelapse System

- **Snapshots**: Captured every 5 minutes from the camera
- **Daily stitch**: Runs at 23:00 UTC, produces one MP4 per day (~14 seconds at 20fps)
- **Weekly stitch**: Runs Sundays at 23:30 UTC, combines 7 days into one MP4 (~84 seconds at 24fps)
- **Cleanup**: Runs Sundays at 23:45 UTC. Snapshots older than 9 days and daily videos older than 30 days are deleted. Weekly videos are kept indefinitely.

## Deployment

Deployed via GitHub Actions on push to `main`. The pipeline builds a Docker image, pushes to GHCR, then SSHs into the server to pull and restart. Systemd service files for the ffmpeg transcoder and RockPro64's ustreamer are also deployed via the pipeline, using the main server as an SSH jumpbox to reach the RockPro64 on the LAN.

## Running Locally

```bash
cp .env.example .env  # fill in values
pipenv install
pipenv run python wsgi.py
```

## Stack

- Python 3.14, Flask, flask-classful, APScheduler
- ffmpeg (H.264 encoding via libx264 for timelapse, VAAPI for live stream)
- Docker + docker-compose, GHCR
- Gunicorn (production)
