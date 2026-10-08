#!/bin/bash
# Start the LTX RTMP sink. Destination: the first line of /home/steve/.config/ltx-stream/rtmp_url (outside Git, never printed),
# else a local discard receiver on rtmp://127.0.0.1:1935/live/local so the pipeline stays live and in sync.
set -u
W=${LTX_STREAM_WORKDIR:-/home/steve/ltx-stream/s97-stream01}
PY=/home/steve/.venvs/ltx25-baseline/bin/python
SINK=/home/steve/llm-optimizations/experiments/ltx25-b70/stream/ltx_rtmp_sink.py
# Always push to the local relay (relay2.sh): it writes the LAN preview frame and forwards to the
# remote destination in ~/.config/ltx-stream/rtmp_url without re-encoding. The sink never holds the key.
URL=rtmp://127.0.0.1:1935/live/local; DEST=local-relay
if [ -n "${LTX_STREAM_DISPOSE+x}" ]; then DISPOSE_ARGS=$LTX_STREAM_DISPOSE; else DISPOSE_ARGS='--delete-played-after-seconds 3600 --disposable-dir-regex s97-twowayw2b2p1dxpu2-stream01-[0-9]{7}'; fi
echo "sink destination: $DEST ($(date -u +%FT%TZ))" >> $W/sink-destinations.log
exec $PY -B $SINK --manifest $W/manifest.jsonl --rtmp "$URL" --state $W/sink-state.json --stats $W/sink-stats.json \
  --workdir $W/sinkwork --size 768x768 --decode-threads 2 \
  --title "${LTX_STREAM_TITLE:-LTX-2.5 kittens, live on 4x Intel Arc Pro B70 - 256x256 native, every clip freshly generated (independent takes; continuous scenes coming)}" \
  $DISPOSE_ARGS "$@"
