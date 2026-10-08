#!/bin/bash
# Start the LTX RTMP sink. Destination: the first line of /home/steve/.config/ltx-stream/rtmp_url (outside Git, never printed),
# else a local discard receiver on rtmp://127.0.0.1:1935/live/local so the pipeline stays live and in sync.
set -u
W=/home/steve/ltx-stream/s97-stream01
PY=/home/steve/.venvs/ltx25-baseline/bin/python
SINK=/home/steve/llm-optimizations/experiments/ltx25-b70/stream/ltx_rtmp_sink.py
KEYFILE=/home/steve/.config/ltx-stream/rtmp_url
if [ -s "$KEYFILE" ]; then
  URL=$(head -n1 "$KEYFILE" | tr -d '\r\n'); DEST=remote
else
  URL=rtmp://127.0.0.1:1935/live/local; DEST=local-discard
  if ! pgrep -f 'listen 1 -i rtmp://127.0.0.1:1935/live/local' >/dev/null; then
    setsid ffmpeg -hide_banner -loglevel warning -listen 1 -i rtmp://127.0.0.1:1935/live/local -f null - > $W/local-receiver.log 2>&1 < /dev/null &
    sleep 1
  fi
fi
echo "sink destination: $DEST ($(date -u +%FT%TZ))" >> $W/sink-destinations.log
exec $PY -B $SINK --manifest $W/manifest.jsonl --rtmp "$URL" --state $W/sink-state.json --stats $W/sink-stats.json \
  --workdir $W/sinkwork --size 768x768 --decode-threads 2 \
  --title "LTX-2.5 kittens, live on 4x Intel Arc Pro B70 - 256x256 native, every clip freshly generated (independent takes; continuous scenes coming)" \
  --delete-played-after-seconds 3600 --disposable-dir-regex 's97-twowayw2b2p1dxpu2-stream01-[0-9]{7}' "$@"
