#!/usr/bin/env bash
# Fresh-server identity per arm (card 1; Gemma on card 0, restored at the end): for each arm, serve.sh fast with the
# arm's extra env, the 12-prompt suite (package check.sh), token comparison with R0, stop.
#   ARMS="name1=ENV ENV;name2=ENV" TAG=x identity-arms.sh     (SUDO_ASKPASS set; under systemd-run --user)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
BUILD_DIR=${BUILD_DIR:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25}
MODEL_DIR=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf
TAG=${TAG:?}
OUT=/mnt/fast-ai/bench-results/lfm25-24b-a2b/fusion/$TAG
PORT=18110
UNIT=lfm25-fuse-srv
mkdir -p "$OUT"
log() { echo "### $(date +%T) $*"; }
START=$(date '+%Y-%m-%d %H:%M:%S')
restore() {
  systemctl --user stop $UNIT 2>/dev/null
  log "restoring Gemma's two-card throughput recipe"
  "$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput 2>&1 | grep -v "JSONDecode\|raise " | tail -3
  journalctl -k --since "$START" --no-pager -o cat | grep -iE 'xe .*(fault|reset|error)|GT[0-9]*: .*reset' | head -5 || true
  log done
}
trap restore EXIT
log "moving Gemma to card 0"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -1
IFS=';' read -ra arms <<< "${ARMS:?}"
for arm in "${arms[@]}"; do
  name=${arm%%=*}
  envs_str=${arm#*=}
  for _ in $(seq 1 120); do [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && break; sleep 1; done
  systemctl --user reset-failed $UNIT 2>/dev/null
  envs=(-E BUILD_DIR="$BUILD_DIR" -E MODEL_DIR="$MODEL_DIR" -E GPU=1 -E PORT=$PORT)
  for kv in $envs_str; do envs+=(-E "$kv"); done
  systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB "${envs[@]}" \
    bash -c "exec $PKG/serve.sh fast > $OUT/server-$name.log 2>&1" >/dev/null
  ok=0
  for _ in $(seq 1 240); do curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { ok=1; break; }; sleep 1; done
  [[ $ok == 1 ]] || { log "$name: server did not start"; tail -5 "$OUT/server-$name.log"; systemctl --user stop $UNIT; continue; }
  log "$name: suite"
  RESULTS_DIR=$OUT "$PKG/check.sh" run "$name" 2>&1 | grep -v "^Against\|^compiler" | tail -2
  systemctl --user stop $UNIT
  for _ in $(seq 1 60); do systemctl --user is-active -q $UNIT || break; sleep 1; done
done
