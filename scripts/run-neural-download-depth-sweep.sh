#!/usr/bin/env bash
set -euo pipefail

# Context-depth sweep for a neural.download packet: pp2048 (prefill) and
# tg128 (decode) at depths 0..32768 via llama-bench, 5 repetitions per
# point, JSON output. Raw engine rates - labeled distinctly from the
# server-suite medians in every packet. One model per invocation.
#
# Env: MODEL_PATH (gguf), SWEEP_ID, OUT_DIR, LLAMA_BUILD, GPU_INDEX=0,
#      KV_TYPE=f16 (flagship uses q8_0), DEPTHS override optional.

model_path="${MODEL_PATH:?set MODEL_PATH}"
sweep_id="${SWEEP_ID:?set SWEEP_ID}"
out_dir="${OUT_DIR:?set OUT_DIR}"
llama_build="${LLAMA_BUILD:?set LLAMA_BUILD}"
gpu_index="${GPU_INDEX:-0}"
kv_type="${KV_TYPE:-f16}"
depths="${DEPTHS:-0,2048,4096,8192,16384,24576,32768}"

bench="${llama_build}/bin/llama-bench"
[[ -x "$bench" ]] || { echo "missing llama-bench: $bench" >&2; exit 1; }
[[ -f "$model_path" ]] || { echo "missing model: $model_path" >&2; exit 1; }
pgrep -x llama-server >/dev/null && { echo 'llama-server is running; refuse to sweep' >&2; exit 1; }
pgrep -x llama-bench >/dev/null && { echo 'another llama-bench is running' >&2; exit 1; }

mkdir -p "$out_dir"
set +u
[[ -r /opt/intel/oneapi/setvars.sh ]] && source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR="level_zero:${gpu_index}"

meta="$out_dir/${sweep_id}.meta.json"
python3 - "$meta" "$sweep_id" "$model_path" "$bench" "$kv_type" "$depths" <<'PY'
import hashlib, json, subprocess, sys
out, sweep_id, model_path, bench, kv_type, depths = sys.argv[1:]
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()
json.dump({
    "format": "neural-download-depth-sweep-meta-v1",
    "sweep_id": sweep_id,
    "model_path": model_path,
    "model_sha256": sha(model_path),
    "bench_path": bench,
    "bench_sha256": sha(bench),
    "kv_type": kv_type,
    "depths": depths,
    "protocol": "llama-bench pp2048+tg128 at each depth, 5 reps, fa=on, raw engine rates",
}, open(out, "w"), indent=1)
PY

"$bench" \
  -m "$model_path" \
  -p 2048 -n 128 -d "$depths" \
  -fa on -ctk "$kv_type" -ctv "$kv_type" \
  -ngl 99 -r 5 -o json \
  > "$out_dir/${sweep_id}.sweep.json" \
  2> "$out_dir/${sweep_id}.stderr.log"
rc=$?
echo "SWEEP-RC:$rc"
python3 - "$out_dir/${sweep_id}.sweep.json" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))
for r in rows:
    kind = 'pp' if r['n_prompt'] else 'tg'
    n = r['n_prompt'] or r['n_gen']
    print(f"depth={r.get('n_depth', 0):>6}  {kind}{n:<5} {r['avg_ts']:9.2f} tok/s  (+/- {r['stddev_ts']:.2f})")
PY
exit "$rc"
