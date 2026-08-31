#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
harness=${script_dir}/qwen38-det-cross-process-ordinary-gdn.py
prereg=${repo}/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-ordinary-gdn-cross-process-d4-prereg.md
root=/mnt/fast-ai/bench-results/qwen38-ordinary-gdn-cross-process-20260831-d4
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x "$harness" && -f "$prereg" && ! -e "$root" ]] || fail 'missing input or reused root'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'
mkdir -p "$root"
for process in 1 2 3 4; do
 docker run --rm --name "q38-gdn-d4-${process}" --device /dev/dri:/dev/dri --group-add render \
  --security-opt label=disable --ipc=host --memory 8g --memory-swap 12g \
  --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  --volume "$harness:/work/harness.py:ro" --volume "$root:/out" \
  --entrypoint /opt/venv/bin/python "$image" /work/harness.py --out "/out/process-${process}.json" \
  >"$root/process-${process}.log"
done
python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt,hashlib,json,pathlib,sys
root,prereg,image,image_id=sys.argv[1:]; root=pathlib.Path(root)
docs=[json.loads((root/f"process-{i}.json").read_text()) for i in range(1,5)]
rows=[]
for m in docs[0]["rows"]:
 key=m["m"]; vals=[next(r for r in d["rows"] if r["m"]==key) for d in docs]
 pre=sorted({v["prefill_sha256"] for v in vals}); dec=sorted({v["decode_trajectory_sha256"] for v in vals})
 rows.append({"m":key,"prefill_within_exact_all":all(v["within_process_prefill_exact"] for v in vals),
  "decode_within_exact_all":all(v["within_process_decode_exact"] for v in vals),
  "prefill_unique_hashes":len(pre),"decode_unique_hashes":len(dec),"prefill_sha256s":pre,"decode_sha256s":dec})
failed=[r for r in rows if not (r["prefill_within_exact_all"] and r["decode_within_exact_all"] and r["prefill_unique_hashes"]==1 and r["decode_unique_hashes"]==1)]
result={"schema":"neural.download.ordinary-gdn-cross-process.v1","created_utc":dt.datetime.now(dt.UTC).isoformat(),
 "classification":"negative-causal-screen" if not failed else "positive-causal-finding","image":image,"image_id":image_id,
 "fresh_processes":4,"cases":len(rows),"passed":not failed,"failed_cases":failed,"rows":rows,
 "preregistration_sha256":hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps({k:result[k] for k in ("classification","passed","cases","failed_cases")},indent=2))
PY
