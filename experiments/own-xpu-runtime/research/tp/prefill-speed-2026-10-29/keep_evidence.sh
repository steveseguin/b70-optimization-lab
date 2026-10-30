#!/usr/bin/env bash
# Compact evidence of finished harness runs (CPU only): summary, host traces, exchange/compare statistics and state hashes
# into evidence/<phase>/<run>/. Usage: keep_evidence.sh PHASE RUNS_DIR
set -eu
D=$(cd "$(dirname "$0")" && pwd); P=$1; R=$2
for d in "$R"/*/; do r=$(basename "$d"); mkdir -p "$D/evidence/$P/$r"; cp "$d/summary.json" "$D/evidence/$P/$r/"
  rk=$(ls -d "$d"/rank? | head -1)
  for f in prefill-host-trace.jsonl draft-host-trace.jsonl tp-exchange.json tp-replicate-compare.json qsa-split.json tp-submit-thread.json prefill-allocation.json draft-chunk-sites.json; do [ -f "$rk/$f" ] && cp "$rk/$f" "$D/evidence/$P/$r/"; done
  [ -f "$rk/draft-rows.jsonl" ] && grep '"chunk_replay":{' "$rk/draft-rows.jsonl" >"$D/evidence/$P/$r/draft-chunk-replays.jsonl" || true
  [ -f "$rk/state-2147483647/state.json" ] && cp "$rk/state-2147483647/state.json" "$D/evidence/$P/$r/state-2147483647--state.json"
  [ -f "$rk/draft-final-state/all-state.json" ] && cp "$rk/draft-final-state/all-state.json" "$D/evidence/$P/$r/draft-final-state--all-state.json"
done; du -sh "$D/evidence/$P"
