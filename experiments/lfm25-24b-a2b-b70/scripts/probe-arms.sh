#!/usr/bin/env bash
# Start one server per arm (fresh), run the logprob identity probe, diff against the R0 reference probe.
#   ARMS="name:ENV1=1,ENV2=0 ..." LLAMA_SERVER=... probe-arms.sh
set -uo pipefail
E=/home/steve/b70-optimization-lab/experiments/lfm25-24b-a2b-b70/scripts
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b}
REF=${REF:-$OUT/probe/r0-prod.json}
mkdir -p "$OUT/probe"
outs=()
while IFS= read -r line; do
  [[ -z $line ]] && continue
  name=${line%%:*}; envs=${line#*:}
  echo "### $(date +%T) $name: $envs"
  ARM_ENV="${envs//,/ }" "$E/serve-lfm25.sh" r0 "probe-$name" || { echo "server failed for $name"; continue; }
  python3 "$E/identity_probe.py" run --out "$OUT/probe/$name.json" 2>/dev/null || echo "probe failed for $name"
  outs+=("$OUT/probe/$name.json")
done <<< "$ARMS"
systemctl --user stop lfm25-srv
python3 "$E/identity_probe.py" diff "$REF" "${outs[@]}"
