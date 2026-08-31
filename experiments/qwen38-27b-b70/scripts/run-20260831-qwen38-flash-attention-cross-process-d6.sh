#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
harness="$script_dir/qwen38-det-cross-process-flash-attention.py"
prereg="$repo/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-flash-attention-cross-process-d6-prereg.md"
root=/mnt/fast-ai/bench-results/qwen38-flash-attention-cross-process-20260831-d6
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x "$harness" && -f "$prereg" && ! -e "$root" ]] || fail 'missing input or reused root'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'
[[ -z "$(docker ps -q)" ]] || fail 'another container is running'
exec 7>/tmp/b70-benchmark.lock; flock -n 7 || fail 'benchmark lock held'
exec 8>/tmp/b70-gpu0.lock; flock -n 8 || fail 'GPU0 lock held'
mkdir -p "$root"
for process in 1 2 3 4; do
  docker run --rm --name "q38-fa-d6-${process}" --device /dev/dri:/dev/dri \
    --group-add render --security-opt label=disable --ipc=host --memory 4g --memory-swap 6g \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --volume "$harness:/work/harness.py:ro" --volume "$root:/out" \
    --entrypoint /opt/venv/bin/python "$image" /work/harness.py --out "/out/process-${process}.json" \
    >"$root/process-${process}.log" 2>&1
done
python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt, hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1]); prereg=pathlib.Path(sys.argv[2]); image,image_id=sys.argv[3:]
docs=[json.loads((root/f"process-{i}.json").read_text()) for i in range(1,5)]
lengths=[48,49,52,53,55,56,57,59,65,71,75,78]
if any([c["length"] for c in d["cases"]] != lengths for d in docs): raise SystemExit("case identity mismatch")
unstable=[]; cases=[]
for index,length in enumerate(lengths):
    rows=[d["cases"][index] for d in docs]
    values={field:sorted({value for row in rows for value in (row[field] if isinstance(row[field],list) else [row[field]])})
            for field in ("prefill_cache_hashes","prefill_output_hashes","decode_trajectory_sha256","final_cache_sha256","input_sha256")}
    stable=all(len(items)==1 for items in values.values())
    if not stable: unstable.append(length)
    cases.append({"length":length,"stable":stable,"unique":{key:len(value) for key,value in values.items()}})
passed=not unstable
result={"schema":"neural.download.qwen38-paged-fa2-cross-process.result.v1","created_utc":dt.datetime.now(dt.UTC).isoformat(),
 "classification":"negative-causal-screen" if passed else "positive-causal-finding","image":image,"image_id":image_id,
 "fresh_processes":4,"prefill_repetitions_per_length":4,"decode_steps_per_length":32,"lengths":lengths,
 "passed":passed,"unstable_lengths":unstable,"cases":cases,
 "process_sha256":{f"process-{i}":hashlib.sha256((root/f"process-{i}.json").read_bytes()).hexdigest() for i in range(1,5)},
 "preregistration_sha256":hashlib.sha256(prereg.read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps(result,indent=2,sort_keys=True))
if not passed: raise SystemExit(3)
PY
