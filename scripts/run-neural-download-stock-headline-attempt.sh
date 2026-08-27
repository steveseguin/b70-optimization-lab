#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
profile=${PROFILE_ID:?set PROFILE_ID to a registered stock profile}
attempt=${ATTEMPT:?set ATTEMPT to a unique attempt label}
model_dir=${MODEL_DIR:?set MODEL_DIR to the verified local model directory}
build_dir=${BUILD_DIR:?set BUILD_DIR to the pinned llama.cpp SYCL build directory}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
port=${PORT:-18151}
suite=${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json
prereg=${repo}/data/2026-08-27-neural-download-stock-headline-closure-prereg.json

case "${profile}" in
  lfm25-q8-tp1)
    manifest=${repo}/repro/lfm25-26b-q8-b70/model-manifest.json
    model_file=LFM2.5-2.6B-Q8_0.gguf
    alias_name=lfm25-q8-tp1
    ;;
  ornith15-9b-q8-tp1)
    manifest=${repo}/repro/ornith-15-9b-q8-b70/model-manifest.json
    model_file=Ornith-1.5-9B-Q8_0.gguf
    alias_name=ornith15-9b-q8-tp1
    ;;
  nemotron35-lightning-udq4km-tp1)
    manifest=${repo}/repro/nemotron-35-lightning-30b-a3b-b70/model-manifest.json
    model_file=NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf
    alias_name=nemotron35-lightning-udq4km-tp1
    ;;
  *)
    printf 'FAIL: unregistered PROFILE_ID=%s\n' "${profile}" >&2
    exit 2
    ;;
esac

server=${build_dir}/bin/llama-server
runtime_files=(
  llama-server
  libllama-server-impl.so
  libllama-common.so
  libmtmd.so
  libllama.so
  libggml.so
  libggml-cpu.so
  libggml-sycl.so
  libggml-base.so
)
runtime_hashes=(
  7d524360677aa06d1847e7a68b7e8a8234aaad203ea7334cd7237e6015fb0e56
  c07c39c5b547f41e3dd70207d3b3bcc0014aae8d2ddc04af814f133ee694d344
  59dd9902f947b8591a67e209093543b4b397dfc6075b00863db8ce1cd171f47f
  f4bfe35aa10369fd69b6aeea6dfd91a1ad2901db1cd21bb0a0606d8c7fec8798
  03af889304acd9df10f5bd36db9f65ae99de525de81f69eddf90ef011827fa8e
  810b6c6dbae53586a491b0ff089fb1e4e5d280b97c5a38fc31389b75af1d9d26
  609636d85dd1e2bcdaf6bb02500c313e0d6a44d0bbb1ef7b76dd13244f3456a1
  5f0b9ed040737c1629bd4b4968347244c3d4dced88a12a0b80d6f529d7d810e4
  37b4e5ef151d698cbc36d853c6e90a69b93c44c231391a9ef9c602430d77c05a
)

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
[[ -f "${model_dir}/${model_file}" ]] || fail "model file missing: ${model_dir}/${model_file}"
[[ -x "${server}" ]] || fail "server missing: ${server}"
[[ -f "${suite}" && -f "${prereg}" && -f "${manifest}" ]] || fail 'campaign input missing'
[[ -z "$(git -C "${repo}" status --porcelain)" ]] || fail 'repository must be clean'
[[ "$(git -C "${repo}" branch --show-current)" == main ]] || fail 'campaign must run from main'
[[ "$(git -C "${repo}" rev-parse HEAD)" == "$(git -C "${repo}" rev-parse origin/main)" ]] || fail 'main must be pushed before execution'

for index in "${!runtime_files[@]}"; do
  file=${build_dir}/bin/${runtime_files[$index]}
  [[ -e "${file}" ]] || fail "runtime file missing: ${file}"
  actual=$(sha256sum "${file}" | awk '{print $1}')
  [[ "${actual}" == "${runtime_hashes[$index]}" ]] || fail "runtime hash mismatch: ${file}"
done

exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU0 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

mkdir -p "${out_dir}"
python3 "${repo}/scripts/verify-neural-download-model.py" "${manifest}" "${model_dir}" \
  --json "${out_dir}/model-verification.json" >"${out_dir}/model-verification.stdout"

python3 - "${out_dir}/campaign-identity.json" "${profile}" "${attempt}" \
  "${model_dir}/${model_file}" "${manifest}" "${server}" "${build_dir}" \
  "${suite}" "${prereg}" "${repo}" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys

out, profile, attempt, model, manifest, server, build, suite, prereg, repo = sys.argv[1:]
def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
runtime_names = [
    "llama-server", "libllama-server-impl.so", "libllama-common.so",
    "libmtmd.so", "libllama.so", "libggml.so", "libggml-cpu.so",
    "libggml-sycl.so", "libggml-base.so",
]
runtime = {
    name: {"path": str(pathlib.Path(build) / "bin" / name),
           "sha256": digest(pathlib.Path(build) / "bin" / name)}
    for name in runtime_names
}
value = {
    "schema": "neural.download.stock-headline-attempt.v1",
    "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "profile": profile,
    "attempt": attempt,
    "repository_commit": subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "HEAD"], text=True
    ).strip(),
    "artifacts": {
        "model": {"path": model, "sha256": digest(model)},
        "model_manifest": {"path": manifest, "sha256": digest(manifest)},
        "suite": {"path": suite, "sha256": digest(suite)},
        "preregistration": {"path": prereg, "sha256": digest(prereg)},
        "benchmark_harness": {
            "path": str(pathlib.Path(repo) / "scripts/bench-openai-realistic-suite.py"),
            "sha256": digest(pathlib.Path(repo) / "scripts/bench-openai-realistic-suite.py"),
        },
        "canary_harness": {
            "path": str(pathlib.Path(repo) / "scripts/neural-download-canaries.py"),
            "sha256": digest(pathlib.Path(repo) / "scripts/neural-download-canaries.py"),
        },
        "runtime": runtime,
    },
    "contract": {
        "cards": 1, "gpu": 0, "tp": 1, "mtp": 0, "reasoning": "off",
        "graph": "off", "kv": "f16", "parallel_slots": 1,
        "configured_context_tokens": 8192, "prompt_cache": False,
        "context_checkpoints": False, "prompt_count": 12,
        "prompt_classes": 6, "max_tokens": 512,
        "metric_events": 100, "metric_intervals": 99,
    },
}
pathlib.Path(out).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY

server_pid=
cleanup() {
  if pgrep -x llama-server >/dev/null; then pkill -TERM -x llama-server 2>/dev/null || true; fi
  if [[ -n "${server_pid:-}" ]]; then wait "${server_pid}" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export GGML_SYCL_ENABLE_GRAPH=0

systemd-run --user --scope --quiet \
  --property=MemoryHigh=12G --property=MemoryMax=14G --property=MemorySwapMax=28G \
  "${server}" --model "${model_dir}/${model_file}" --alias "${alias_name}" \
  --reasoning off --ctx-size 8192 --cache-type-k f16 --cache-type-v f16 \
  --device SYCL0 --gpu-layers 99 --split-mode none --flash-attn auto \
  --parallel 1 --cache-ram 0 --ctx-checkpoints 0 --no-cache-prompt \
  --slot-prompt-similarity 0 --fit off --metrics --no-webui \
  --host 127.0.0.1 --port "${port}" >"${out_dir}/server.log" 2>&1 &
server_pid=$!

for _ in $(seq 1 600); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>"${out_dir}/health.err"; then break; fi
  kill -0 "${server_pid}" 2>/dev/null || fail 'server exited before readiness'
  sleep 2
done
curl -fsS "http://127.0.0.1:${port}/health" >/dev/null || fail 'server readiness timeout'
curl -fsS "http://127.0.0.1:${port}/props" >"${out_dir}/props.json" || true
llama_pid=$(pgrep -n -x llama-server)
tr '\0' ' ' <"/proc/${llama_pid}/cmdline" | sed 's/[[:space:]]*$//' >"${out_dir}/server-command.txt"
printf '\n' >>"${out_dir}/server-command.txt"
tr '\0' '\n' <"/proc/${llama_pid}/environ" \
  | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|SYCL_UR_USE_LEVEL_ZERO_V2=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' \
  | LC_ALL=C sort >"${out_dir}/runtime-environment.txt"

python3 "${repo}/scripts/bench-openai-realistic-suite.py" \
  --base-url "http://127.0.0.1:${port}" --model "${alias_name}" \
  --api-mode native-raw --suite "${suite}" --max-tokens 512 --metric-tokens 100 \
  --seed 42 --timeout 900 --return-token-ids --require-natural-eos \
  --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0,"top_p":1}' \
  --out "${out_dir}/performance.json" >"${out_dir}/performance.stdout"
python3 "${repo}/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:${port}" --model "${alias_name}" \
  --out "${out_dir}/canaries.json" >"${out_dir}/canaries.stdout"

python3 - "${out_dir}/performance.json" "${out_dir}/canaries.json" \
  "${out_dir}/qualification.json" <<'PY'
import json
import pathlib
import sys

performance = json.load(open(sys.argv[1]))
canaries = json.load(open(sys.argv[2]))
gate = performance["realistic_final_gate"]
fresh = performance["fresh_response_validity"]
rows = performance["rows"]
tokens_complete = all(
    isinstance(row.get("token_ids"), list) and len(row["token_ids"]) >= 100
    for row in rows
)
passed = (
    gate["passed"] and fresh["valid"] and gate["cached_tokens_all_zero"]
    and len(rows) == 12 and canaries["pass_all"] and tokens_complete
)
value = {
    "schema": "neural.download.stock-headline-attempt-qualification.v1",
    "status": "passed" if passed else "failed-closed",
    "class_balanced_median_tok_s": performance["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"],
    "all_prompt_median_tok_s": performance["summary"]["tok_s_1_100_intervals_after_ttft"]["median"],
    "prompt_count": len(rows),
    "cached_tokens_all_zero": gate["cached_tokens_all_zero"],
    "objective_canaries_passed": canaries["pass_all"],
    "complete_token_arrays_retained": tokens_complete,
    "publication_authority": "single fresh-server attempt only; requires a second exact attempt",
}
pathlib.Path(sys.argv[3]).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
if not passed:
    raise SystemExit("qualification failed closed")
print(f"class_balanced_median_tok_s={value['class_balanced_median_tok_s']:.12f}")
PY

curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/post-health.json"
trap - EXIT INT TERM
cleanup
printf 'complete profile=%s attempt=%s evidence=%s\n' "${profile}" "${attempt}" "${out_dir}"
