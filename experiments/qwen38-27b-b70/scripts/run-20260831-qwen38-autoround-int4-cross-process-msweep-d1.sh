#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
harness=${script_dir}/qwen38-det-cross-process-int4-shapes.py
prereg=${repo}/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-autoround-int4-cross-process-msweep-d1-prereg.md
root=/mnt/fast-ai/bench-results/qwen38-autoround-int4-cross-process-msweep-20260831-d1
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
ms=(1 48 49 52 53 55 56 57 59 65 71 75 78)

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x "$harness" && -f "$prereg" ]] || fail 'missing harness or preregistration'
[[ ! -e "$root" ]] || fail 'result root must be new'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'

mkdir -p "$root"
m_args=()
for m in "${ms[@]}"; do m_args+=(--m "$m"); done
for process in 1 2 3 4; do
  docker run --rm --name "q38-int4-msweep-d1-${process}" \
    --device /dev/dri:/dev/dri --group-add render --security-opt label=disable \
    --ipc=host --memory 8g --memory-swap 12g \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --env VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=1 \
    --volume "$harness:/work/harness.py:ro" \
    --entrypoint /opt/venv/bin/python "$image" /work/harness.py \
    "${m_args[@]}" >"$root/process-${process}.json"
done

python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import sys

root, prereg, image, image_id = sys.argv[1:]
root = pathlib.Path(root)
docs = [json.loads((root/f"process-{i}.json").read_text()) for i in range(1,5)]
keys = sorted({(r["name"], r["m"], r["k"], r["n"]) for d in docs for r in d["results"]})
rows=[]
for name,m,k,n in keys:
    values=[]
    for d in docs:
        match=[r for r in d["results"] if (r["name"],r["m"],r["k"],r["n"])==(name,m,k,n)]
        if len(match)!=1: raise SystemExit(f"missing or duplicate row {(name,m,k,n)}")
        values.append(match[0])
    hashes=sorted({v["sha256"] for v in values})
    rows.append({"name":name,"m":m,"k":k,"n":n,
                 "within_process_exact_all":all(v["within_process_exact"] for v in values),
                 "unique_hashes":len(hashes),"sha256s":hashes})
passed=all(r["within_process_exact_all"] and r["unique_hashes"]==1 for r in rows)
result={
 "schema":"neural.download.raw-operator-cross-process-msweep.v1",
 "created_utc":dt.datetime.now(dt.UTC).isoformat(),
 "classification":"negative-causal-screen" if passed else "positive-causal-finding",
 "image":image,"image_id":image_id,"fresh_processes":4,
 "m_values":docs[0]["m_values"],"shape_m_cases":len(rows),"passed":passed,
 "failed_cases":[r for r in rows if not r["within_process_exact_all"] or r["unique_hashes"]!=1],
 "rows":rows,
 "process_sha256":{f"process-{i}":hashlib.sha256((root/f"process-{i}.json").read_bytes()).hexdigest() for i in range(1,5)},
 "preregistration_sha256":hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest(),
}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps({k:result[k] for k in ("classification","passed","shape_m_cases","failed_cases")},indent=2))
PY
