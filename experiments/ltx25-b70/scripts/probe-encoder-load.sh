#!/bin/bash
# Load-path crash probe: fresh server, one warm prompt, record survival, stop.
# Two GP faults today hit the same hot dereference site during the encoder
# load, both after the campaign's 60 s rest. This loop measures the crash
# rate of the launch->single-load path with and without the rest, using
# single prompts only: a server crash here has never taken the host down.
#
#   bash scripts/probe-encoder-load.sh [rounds] [rest-seconds]
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-graph-capture-89
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
PY=/home/steve/.venvs/ltx25-baseline/bin/python
MANIFEST=$(sha256sum $P/manifest.json | cut -d' ' -f1)
ROUNDS=${1:-2}
REST=${2:-0}
RESULTS=$LANE/data/graph-capture-89/load-probe.tsv
mkdir -p "$(dirname $RESULTS)"
for i in $(seq 1 $ROUNDS); do
  RUN=encoder-server-graph-capture-89-probe-$(date +%H%M%S)
  echo "=== $(date -u +%FT%TZ) probe $i/$ROUNDS rest=${REST}s run=$RUN"
  $PY -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $MANIFEST \
      --run-name $RUN >/tmp/probe-server.log 2>&1 &
  SPID=$!
  ok=0
  for w in $(seq 1 240); do
    curl -sf -m 2 http://127.0.0.1:8188/queue >/dev/null 2>&1 && { ok=1; break; }
    kill -0 $SPID 2>/dev/null || break
    sleep 5
  done
  [ $ok = 0 ] && { echo "  server never came up"; kill $SPID 2>/dev/null; wait $SPID 2>/dev/null; continue; }
  [ $REST -gt 0 ] && sleep $REST
  PREFIX=probe$(date +%H%M%S)
  $PY -B $LANE/scripts/run-throughput-fixtures.py $PREFIX \
      --graph $P/graphs/graph-capture-all48-pipe-samp2-tsh.json \
      --arm pipe-samp2-tsh --server-run $R/$RUN --count 1 --index-base 210000 \
      --out $LANE/data/graph-capture-89 >/tmp/probe-run.log 2>&1
  RC=$?
  sleep 2
  if kill -0 $SPID 2>/dev/null; then SRV=alive; else SRV=DEAD; fi
  # Graceful stop: a bare kill during in-flight graph work faulted the xe
  # engine on 2026-09-21 (00:24:38) and burned the boot for further launches.
  kill -TERM $SPID 2>/dev/null
  for w in $(seq 1 24); do kill -0 $SPID 2>/dev/null || break; sleep 5; done
  kill -0 $SPID 2>/dev/null && kill -KILL $SPID 2>/dev/null
  wait $SPID 2>/dev/null
  sleep 15
  mv $R/$RUN $R/$RUN-done 2>/dev/null
  rm -rf $R/requests/$PREFIX-00 $R/output/validation/$PREFIX-00 $R/$RUN-done
done
echo "=== probes complete"
