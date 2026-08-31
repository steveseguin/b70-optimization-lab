#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
harness="$script_dir/qwen38-det-cross-process-tp1-stacked-int4.py"
prereg="$repo/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-tp1-stacked-int4-cross-process-d7-prereg.md"
root=/mnt/fast-ai/bench-results/qwen38-tp1-stacked-int4-cross-process-20260831-d7
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
ms=(1 48 49 52 53 55 56 57 59 65 71 75 78)
fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x "$harness" && -f "$prereg" && ! -e "$root" ]] || fail 'missing input or reused root'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'
[[ -z "$(docker ps -q)" ]] || fail 'another container is running'
exec 7>/tmp/b70-benchmark.lock; flock -n 7 || fail 'benchmark lock held'
exec 8>/tmp/b70-gpu0.lock; flock -n 8 || fail 'GPU0 lock held'
mkdir -p "$root"; m_args=(); for m in "${ms[@]}"; do m_args+=(--m "$m"); done
for process in 1 2 3 4; do
  docker run --rm --name "q38-int4-d7-${process}" --device /dev/dri:/dev/dri \
    --group-add render --security-opt label=disable --ipc=host --memory 4g --memory-swap 6g \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --env VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=1 \
    --volume "$harness:/work/harness.py:ro" --entrypoint /opt/venv/bin/python "$image" \
    /work/harness.py "${m_args[@]}" >"$root/process-${process}.json"
done
python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt,hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); prereg=pathlib.Path(sys.argv[2]); image,image_id=sys.argv[3:]
docs=[json.loads((root/f"process-{i}.json").read_text()) for i in range(1,5)]
keys=sorted({(r["name"],r["m"],r["k"],r["n"]) for d in docs for r in d["results"]}); rows=[]
for key in keys:
 values=[]
 for d in docs:
  match=[r for r in d["results"] if (r["name"],r["m"],r["k"],r["n"])==key]
  if len(match)!=1: raise SystemExit(f"missing or duplicate {key}")
  values.append(match[0])
 hashes=sorted({v["sha256"] for v in values})
 rows.append({"name":key[0],"m":key[1],"k":key[2],"n":key[3],"within_process_exact_all":all(v["within_process_exact"] for v in values),"unique_hashes":len(hashes),"sha256s":hashes})
failed=[r for r in rows if not r["within_process_exact_all"] or r["unique_hashes"]!=1]; passed=not failed
result={"schema":"neural.download.qwen38-tp1-stacked-int4-cross-process.v1","created_utc":dt.datetime.now(dt.UTC).isoformat(),
 "classification":"negative-causal-screen" if passed else "positive-causal-finding","image":image,"image_id":image_id,
 "fresh_processes":4,"m_values":docs[0]["m_values"],"shape_m_cases":len(rows),"passed":passed,"failed_cases":failed,
 "process_sha256":{f"process-{i}":hashlib.sha256((root/f"process-{i}.json").read_bytes()).hexdigest() for i in range(1,5)},
 "preregistration_sha256":hashlib.sha256(prereg.read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True))
if not passed: raise SystemExit(3)
PY
