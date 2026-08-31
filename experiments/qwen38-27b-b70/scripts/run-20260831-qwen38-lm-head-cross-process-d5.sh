#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
harness=${script_dir}/qwen38-det-cross-process-lm-head.py
prereg=${repo}/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-lm-head-cross-process-d5-prereg.md
root=/mnt/fast-ai/bench-results/qwen38-lm-head-cross-process-20260831-d5
model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x "$harness" && -f "$prereg" && ! -e "$root" ]] || fail 'missing input or reused root'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'
mkdir -p "$root"
"$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
 "$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json" "$model" \
 --json "$root/model-verify.json" >"$root/model-verify.log"
for process in 1 2 3 4; do
 docker run --rm --name "q38-head-d5-${process}" --device /dev/dri:/dev/dri --group-add render \
  --security-opt label=disable --ipc=host --memory 8g --memory-swap 12g \
  --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  --volume "$model:/model:ro" --volume "$harness:/work/harness.py:ro" --volume "$root:/out" \
  --entrypoint /opt/venv/bin/python "$image" /work/harness.py --out "/out/process-${process}.json" \
  >"$root/process-${process}.log"
done
python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt,hashlib,json,pathlib,sys
root,prereg,image,image_id=sys.argv[1:]; root=pathlib.Path(root)
docs=[json.loads((root/f"process-{i}.json").read_text()) for i in range(1,5)]
if any(d["checkpoint_shape"]!=[248320,5120] or d["checkpoint_dtype"]!="torch.bfloat16" or d["runtime_dtype"]!="torch.float16" for d in docs): raise SystemExit("weight identity mismatch")
hashes=sorted({h for d in docs for h in d["unique_logit_hashes"]}); top1=sorted({v for d in docs for v in d["top1_unique"]})
passed=len(hashes)==len(top1)==1 and all(len(d["unique_logit_hashes"])==len(d["top1_unique"])==1 for d in docs)
result={"schema":"neural.download.actual-lm-head-cross-process.v1","created_utc":dt.datetime.now(dt.UTC).isoformat(),
 "classification":"negative-causal-screen" if passed else "positive-causal-finding","image":image,"image_id":image_id,
 "fresh_processes":4,"calls":64,"passed":passed,"unique_logit_hashes":hashes,"top1_unique":top1,
 "process_sha256":{f"process-{i}":hashlib.sha256((root/f"process-{i}.json").read_bytes()).hexdigest() for i in range(1,5)},
 "model_verify_sha256":hashlib.sha256((root/"model-verify.json").read_bytes()).hexdigest(),
 "preregistration_sha256":hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps(result,indent=2,sort_keys=True))
if not passed: raise SystemExit(3)
PY
