#!/bin/bash
# Finds all UVC video capture devices sorted by USB bus path for consistent
# ordering across reboots. Writes /run/ustreamer_device_1, _2, etc.
# Usage: find_cameras.sh [N] — output only the Nth camera (1-indexed)
DEVICES=()
for dev in /dev/video*; do
    [[ "$dev" == *-* ]] && continue
    info=$(v4l2-ctl --device="$dev" --info 2>/dev/null)
    driver=$(echo "$info" | grep "Driver name" | head -1 | sed 's/.*: //')
    has_capture=$(echo "$info" | grep -c "Video Capture")
    if [[ "$driver" == "uvcvideo" && "$has_capture" -gt 0 ]]; then
        bus_path=$(udevadm info --query=property --name="$dev" 2>/dev/null | grep "ID_PATH=" | sed 's/ID_PATH=//')
        DEVICES+=("$bus_path|$dev")
    fi
done
if [[ ${#DEVICES[@]} -eq 0 ]]; then
    echo "No UVC cameras found" >&2
    exit 1
fi
IFS=$'\n' SORTED=($(sort <<<"${DEVICES[*]}")); unset IFS
for i in "${!SORTED[@]}"; do
    dev_path=$(echo "${SORTED[$i]}" | cut -d'|' -f2)
    num=$((i + 1))
    echo "$dev_path" > "/run/ustreamer_device_$num"
done
if [[ -n "$1" ]]; then
    file="/run/ustreamer_device_$1"
    if [[ -f "$file" ]]; then
        cat "$file"
    else
        echo "Camera $1 not found (only ${#SORTED[@]} detected)" >&2
        exit 1
    fi
else
    echo "${#SORTED[@]}"
fi
