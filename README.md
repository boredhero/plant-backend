# plant-backend

Flask API backend for a live plant camera streaming and timelapse system. Handles snapshot capture, timelapse generation, camera health monitoring, and serves as the data layer for [plant-frontend](https://github.com/boredhero/plant-frontend).

**Live site:** [planting.martinospizza.dev](https://planting.martinospizza.dev)

## Architecture

A RockPro64 SBC runs multiple USB webcams via [ustreamer](https://github.com/pikvm/ustreamer) (MJPEG over HTTP). The main server pulls the MJPEG streams and transcodes them to HLS using ffmpeg with AMD VAAPI hardware encoding (Radeon R9 Fury). This backend runs alongside the transcoders in Docker, capturing snapshots from all cameras for timelapse generation and exposing a REST API for stream health and timelapse data.

```
USB Cam 1 -> ustreamer@1 (:8080) --+
                                    +--> ffmpeg VAAPI (HLS) --> nginx --> hls.js
USB Cam 2 -> ustreamer@2 (:8081) --+         |
                                    +-------> Flask backend -> per-cam snapshots -> daily/weekly timelapse MP4s
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

### Multi-Camera with USB Hardware Identity

Each camera is identified by its immutable USB vendor:model ID (e.g., `0bda:5844`), not by `/dev/videoN` numbering which changes across reboots and port swaps. Per-camera config lives in `plantcam-camN.env` files containing the USB ID, ustreamer port, HLS output path, and the full ffmpeg filter chain. `find_cameras.sh` matches a given vendor:model ID to the correct `/dev/videoN` by querying udev properties.

Systemd template services (`ustreamer@.service`, `plantcam-hls@.service`) instantiate per camera — `ustreamer@1` reads `CAM_USB_ID` from `plantcam-cam1.env` and starts on the configured port. Adding a camera is: plug it in, create a new env file, enable the services.

### Stream Reset via File Trigger IPC

After repositioning a camera, the `lagfun` temporal buffer retains a ghost of the old position for ~1-2 minutes. The frontend's "Reset Stream" button hits `POST /cam/reset/<id>`, which writes a trigger file. A systemd `.path` unit on the host watches for it and restarts the corresponding HLS transcoder, clearing the buffer instantly. Rate-limited to 10 resets per 5 minutes per IP with exponential backoff.

### Exposure Calibration

`calibrate_exposure.py` attempts to sync each camera's manual exposure time to the LED PWM period by sweeping exposure values and measuring horizontal row-brightness variance in captured frames. Results are cached to `/etc/ustreamer_exposure` so subsequent boots are instant. Falls back to auto-exposure if no significant improvement is found.

### Per-Camera Filter Pipeline Reference

Each camera has an independent ffmpeg filter chain configured via its env file (`plantcam-camN.env`). The filters are applied in order before VAAPI hardware encoding.

**Available filters and what they do:**

| Filter | Purpose | Example |
|--------|---------|---------|
| `lagfun=decay=N` | Exponential running max — holds brightest pixel value with slow decay. Primary LED band eliminator. | `lagfun=decay=0.9995` |
| `tmedian=radius=N:percentile=1` | Hard pixel-wise max over 2N+1 frames. Cleans up lagfun decay artifacts. | `tmedian=radius=3:percentile=1` |
| `eq=brightness=N:saturation=N:contrast=N` | Basic brightness/contrast/saturation adjustment. Compensates for temporal max overbright. | `eq=brightness=-0.12:saturation=1.15:contrast=1.08` |
| `colorbalance=rm=N:bm=N:rh=N:bh=N` | Per-tonal-range RGB correction. `rm`/`bm` adjust midtones (browns/greens), `rh`/`bh` adjust highlights (whites). | `colorbalance=rm=0.0:bm=-0.03:rh=-0.05:bh=-0.01` |
| `drawtext=expansion=strftime:textfile=...` | Timestamp overlay (12-hour AM/PM via strftime format file). | see env example |
| `format=nv12,hwupload` | Convert to NV12 and upload to GPU for VAAPI encoding. Must be last. | `format=nv12,hwupload` |

**Current production filter chains:**

Cam 1 (overhead, cheap USB webcam — temporal max adds significant blue+red bias):
```
lagfun=decay=0.9995,tmedian=radius=3:percentile=1,
eq=brightness=-0.24:saturation=1.25:contrast=1.05,
colorbalance=rm=-0.08:gm=0.06:bm=-0.30:bs=-0.20:rh=-0.06:bh=-0.02,
drawtext=...,format=nv12,hwupload
```

Cam 2 (side view, better native color, lighter correction):
```
lagfun=decay=0.9995,tmedian=radius=3:percentile=1,
eq=brightness=-0.15:saturation=0.95,
colorbalance=rm=0.03:bm=-0.08:bh=-0.03,
drawtext=...,format=nv12,hwupload
```

### MJPEG Timestamp Handling

MJPEG streams from ustreamer have no proper PTS timestamps. Without `-use_wallclock_as_timestamps 1` and `-fflags +genpts`, ffmpeg invents timestamps that drift, producing HLS segments with inconsistent durations. This was the primary cause of periodic stream freezing before being identified and fixed.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/info` | GET | Service version and status |
| `/cam/status` | GET | Camera and HLS stream health |
| `/cam/reset/<id>` | POST | Reset stream for camera N (clears lagfun buffer). Rate-limited. |
| `/timelapse` | GET | List daily and weekly timelapse videos (all cameras) |
| `/timelapse/latest` | GET | Most recent timelapse |

## Timelapse System

- **Snapshots**: Captured every 5 minutes from each camera into per-camera directories
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
