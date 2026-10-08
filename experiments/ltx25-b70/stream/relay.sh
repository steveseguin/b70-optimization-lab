#!/bin/bash
# Local RTMP receiver for the sink: writes the latest frame as JPEG for the MJPEG preview, and, if
# /home/steve/.config/ltx-stream/rtmp_url exists, relays the stream (copy, no re-encode) to that destination.
# Runs as a loop because it is a client relay: when a destination drops, ffmpeg exits and we listen again;
# the sink reconnects to us within 5 s. Never touches the generation server.
set -u
W=/home/steve/ltx-stream/s97-stream01
KEYFILE=/home/steve/.config/ltx-stream/rtmp_url
mkdir -p /dev/shm/ltx-live
while true; do
  DEST=""; [ -s "$KEYFILE" ] && DEST=$(head -n1 "$KEYFILE" | tr -d '\r\n')
  if [ -n "$DEST" ]; then
    echo "$(date -u +%FT%TZ) relay: listening; forwarding to remote destination (key hidden)" >> $W/relay.log
    ffmpeg -y -hide_banner -loglevel warning -nostats -listen 1 -i rtmp://127.0.0.1:1935/live/local \
      -map 0 -c copy -flvflags no_duration_filesize -f flv "$DEST" \
      -map 0:v -an -vf fps=12 -q:v 4 -update 1 -atomic_writing 1 -f image2 /dev/shm/ltx-live/frame.jpg \
      2>> $W/relay.log
  else
    echo "$(date -u +%FT%TZ) relay: listening; local JPEG preview only (no destination file)" >> $W/relay.log
    ffmpeg -y -hide_banner -loglevel warning -nostats -listen 1 -i rtmp://127.0.0.1:1935/live/local \
      -map 0:v -an -vf fps=12 -q:v 4 -update 1 -atomic_writing 1 -f image2 /dev/shm/ltx-live/frame.jpg \
      2>> $W/relay.log
  fi
  echo "$(date -u +%FT%TZ) relay: ffmpeg exited rc=$?" >> $W/relay.log
  sleep 2
done
