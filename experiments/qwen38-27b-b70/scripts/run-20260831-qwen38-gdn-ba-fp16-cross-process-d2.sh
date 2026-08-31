#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
harness=${script_dir}/qwen38-det-cross-process-gdn-ba-fp16.py
prereg=${repo}/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-gdn-ba-fp16-cross-process-d2-prereg.md
root=/mnt/fast-ai/bench-results/qwen38-gdn-ba-fp16-cross-process-20260831-d2
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x "$harness" && -f "$prereg" ]] || fail 'missing harness or preregistration'
[[ ! -e "$root" ]] || fail 'result root must be new'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'

mkdir -p "$root"
for process in 1 2 3 4 5 6 7 8; do
  docker run --rm --name "q38-gdn-ba-d2-${process}" \
    --device /dev/dri:/dev/dri --group-add render --security-opt label=disable \
    --ipc=host --memory 8g --memory-swap 12g \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --volume "$harness:/work/harness.py:ro" \
    --entrypoint /opt/venv/bin/python "$image" /work/harness.py \
    >"$root/process-${process}.json"
done

python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import sys

root,prereg,image,image_id=sys.argv[1:]
root=pathlib.Path(root)
docs=[json.loads((root/f"process-{i}.json").read_text()) for i in range(1,9)]
keys=sorted({(r["m"],r["k"],r["n"]) for d in docs for r in d["rows"]})
rows=[]
for key in keys:
    values=[]
    for d in docs:
        match=[r for r in d["rows"] if (r["m"],r["k"],r["n"])==key]
        if len(match)!=1: raise SystemExit(f"missing or duplicate {key}")
        values.append(match[0])
    direct=sorted({v["direct_sha256"] for v in values})
    padded=sorted({v["padded_sha256"] for v in values})
    rows.append({"m":key[0],"k":key[1],"n":key[2],
      "direct_within_exact_all":all(v["direct_within_process_exact"] for v in values),
      "padded_within_exact_all":all(v["padded_within_process_exact"] for v in values),
      "direct_unique_hashes":len(direct),"padded_unique_hashes":len(padded),
      "padded_vs_direct_exact_all":all(v["padded_vs_direct_exact"] for v in values),
      "direct_sha256s":direct,"padded_sha256s":padded})
failed=[r for r in rows if not (r["direct_within_exact_all"] and r["padded_within_exact_all"] and r["direct_unique_hashes"]==1 and r["padded_unique_hashes"]==1)]
result={"schema":"neural.download.gdn-ba-fp16-cross-process.v1",
 "created_utc":dt.datetime.now(dt.UTC).isoformat(),"classification":"negative-causal-screen" if not failed else "positive-causal-finding",
 "image":image,"image_id":image_id,"fresh_processes":8,"shape_m_cases":len(rows),
 "passed":not failed,"failed_cases":failed,
 "padded_vs_direct_exact_cases":sum(r["padded_vs_direct_exact_all"] for r in rows),
 "rows":rows,
 "process_sha256":{f"process-{i}":hashlib.sha256((root/f"process-{i}.json").read_bytes()).hexdigest() for i in range(1,9)},
 "preregistration_sha256":hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps({k:result[k] for k in ("classification","passed","shape_m_cases","padded_vs_direct_exact_cases","failed_cases")},indent=2))
PY
