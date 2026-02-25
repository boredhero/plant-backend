#!/bin/bash
# Finds the first UVC video capture device.
# Returns the /dev/videoN path, or exits 1 if none found.
for dev in /dev/video*; do
    [[ "$dev" == *-* ]] && continue
    info=$(v4l2-ctl --device="$dev" --info 2>/dev/null)
    driver=$(echo "$info" | grep "Driver name" | head -1 | sed 's/.*: //')
    has_capture=$(echo "$info" | grep -c "Video Capture")
    if [[ "$driver" == "uvcvideo" && "$has_capture" -gt 0 ]]; then
        echo "$dev"
        exit 0
    fi
done
echo "No UVC camera found" >&2
exit 1
