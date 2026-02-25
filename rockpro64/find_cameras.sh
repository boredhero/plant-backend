#!/bin/bash
# Finds a specific USB camera by vendor:model ID and outputs its /dev/videoN path.
# Usage: find_cameras.sh <vendor_id>:<model_id>
# Example: find_cameras.sh 0bda:5844
# Returns the /dev/videoN path of the matching camera's MJPEG capture endpoint.
if [[ -z "$1" ]]; then
    echo "Usage: find_cameras.sh <vendor_id:model_id>" >&2
    exit 1
fi
TARGET_VID=$(echo "$1" | cut -d: -f1)
TARGET_PID=$(echo "$1" | cut -d: -f2)
for dev in /dev/video*; do
    [[ "$dev" == *-* ]] && continue
    props=$(udevadm info --query=property --name="$dev" 2>/dev/null)
    vid=$(echo "$props" | grep "^ID_VENDOR_ID=" | sed 's/.*=//')
    pid=$(echo "$props" | grep "^ID_MODEL_ID=" | sed 's/.*=//')
    [[ "$vid" != "$TARGET_VID" || "$pid" != "$TARGET_PID" ]] && continue
    has_mjpg=$(v4l2-ctl --device="$dev" --list-formats 2>/dev/null | grep -c "MJPG")
    [[ "$has_mjpg" -eq 0 ]] && continue
    echo "$dev"
    exit 0
done
echo "Camera $1 not found" >&2
exit 1
