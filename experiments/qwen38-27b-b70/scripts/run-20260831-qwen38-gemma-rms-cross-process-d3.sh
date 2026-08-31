#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
harness=${script_dir}/qwen38-det-cross-process-gemma-rms.py
prereg=${repo}/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-gemma-rms-cross-process-d3-prereg.md
root=/mnt/fast-ai/bench-results/qwen38-gemma-rms-cross-process-20260831-d3
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
for process in 1 2 3 4; do
  docker run --rm --name "q38-rms-d3-${process}" \
    --device /dev/dri:/dev/dri --group-add render --security-opt label=disable \
    --ipc=host --memory 8g --memory-swap 12g \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --volume "$harness:/work/harness.py:ro" \
    --entrypoint /opt/venv/bin/python "$image" /work/harness.py \
    >"$root/process-${process}.json"
done
python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt,hashlib,json,pathlib,sys
root,prereg,image,image_id=sys.argv[1:]; root=pathlib.Path(root)
docs=[json.loads((root/f"process-{i}.json").read_text()) for i in range(1,5)]
keys=sorted({(r["m"],r["fused_residual"]) for d in docs for r in d["rows"]})
rows=[]
for key in keys:
 vals=[]
 for d in docs:
  match=[r for r in d["rows"] if (r["m"],r["fused_residual"])==key]
  if len(match)!=1: raise SystemExit(f"missing or duplicate {key}")
  vals.append(match[0])
 row={"m":key[0],"fused_residual":key[1]}
 for mode in ("direct","serial","padded"):
  row[f"{mode}_within_exact_all"]=all(v[f"{mode}_within_exact"] for v in vals)
  hashes=sorted({v[f"{mode}_sha256"] for v in vals})
  row[f"{mode}_unique_hashes"]=len(hashes); row[f"{mode}_sha256s"]=hashes
 row["direct_vs_serial_exact_all"]=all(v["direct_vs_serial_exact"] for v in vals)
 row["direct_vs_padded_exact_all"]=all(v["direct_vs_padded_exact"] for v in vals)
 rows.append(row)
failed=[r for r in rows if not all(r[f"{mode}_within_exact_all"] and r[f"{mode}_unique_hashes"]==1 for mode in ("direct","serial","padded"))]
result={"schema":"neural.download.gemma-rms-cross-process.v1","created_utc":dt.datetime.now(dt.UTC).isoformat(),
 "classification":"negative-causal-screen" if not failed else "positive-causal-finding","image":image,"image_id":image_id,
 "fresh_processes":4,"cases":len(rows),"passed":not failed,"failed_cases":failed,"rows":rows,
 "preregistration_sha256":hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps({k:result[k] for k in ("classification","passed","cases","failed_cases")},indent=2))
PY
