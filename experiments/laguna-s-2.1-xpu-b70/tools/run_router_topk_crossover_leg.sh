#!/usr/bin/env bash
set -euo pipefail

treatment="${1:?usage: run_router_topk_crossover_leg.sh control|candidate RUN_DIR}"
run_dir="${2:?usage: run_router_topk_crossover_leg.sh control|candidate RUN_DIR}"

case "$treatment" in
  control) bf16_router_topk=0 ;;
  candidate) bf16_router_topk=1 ;;
  *) echo "treatment must be control or candidate" >&2; exit 2 ;;
esac

case "$run_dir" in
  /media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/*) ;;
  *) echo "RUN_DIR must be a Laguna runs directory on CorsairExternal" >&2; exit 2 ;;
esac

canonical_run_dir="$(readlink -m -- "$run_dir")"
if [[ "$canonical_run_dir" != "$run_dir" ]]; then
  echo "RUN_DIR must already be canonical (no symlink or .. traversal)" >&2
  exit 2
fi
if [[ -e "$run_dir" ]]; then
  echo "refusing to reuse existing run directory: $run_dir" >&2
  exit 2
fi

ambient_sensitive="$(
  compgen -e | LC_ALL=C sort -u | awk '
    /^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {
      print
    }
  '
)"
if [[ -n "$ambient_sensitive" ]]; then
  echo "refusing inherited benchmark-sensitive environment names:" >&2
  printf '%s\n' "$ambient_sensitive" >&2
  exit 2
fi

repo_root=/home/steve/llm-optimizations
vllm_root=/home/steve/src/deepseek-v4-vllm-xpu-dspark
kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
venv_python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
suite_rel=experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json
teacher=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json
target_root=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/int4
draft_root=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/dflash-int4
target_revision=4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb
draft_revision=5e07c246915c86dc6920fead03d019989224f2ba
target_tree="$target_root/.cache/huggingface/trees/$target_revision.json"
draft_tree="$draft_root/.cache/huggingface/trees/$draft_revision.json"
target_config="$target_root/config.json"
draft_config="$draft_root/config.json"
serve_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna.sh"
compare_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py"
benchmark_script="$repo_root/scripts/bench-openai-realistic-suite.py"
script_path="$(readlink -f "$0")"
base_url=http://127.0.0.1:18080

expected_vllm=689ee3643f320e4a10c621ddd829620bc2f5b3b3
expected_kernels=af6811818ef797aa86aef51bda15ae9c49040f7b
expected_suite=9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
expected_teacher=d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1
expected_launcher=b27267affd51e242fbf24879e7adff69a1ca3e1829428d43501db67c9b65ccf4
expected_comparator=87ad4d57907a15afba221be42ea00e3a1975308d421e0edc13881dafe38e3db3
expected_benchmark=40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2a
expected_target_config=9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6
expected_draft_config=6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926
expected_target_tree=0128e1ddc4954ade6b4ab7677376e3f3a95aaa02ffede3efdd314f3d4d766643
expected_draft_tree=452f28ec2d80bcc33dc89e3581996dd6c1b706243097ea4b342d7f4ee08b08be
expected_chat_template=444819b8ad4612870827ac05b9147fe9e3344d3850cae8c2790898fc514099ff
expected_generation_config=7d29550cada2f2ef1c0b73be71fa5c4531fd745b9d27c547929ed83b2dd2b272
expected_weight_index=d6688684f088af44ba3f002d67df6355be1659a457c9a43168cf2f48740d3c88
expected_special_tokens=70cd3459fde61761e9440751a590e89a108c09b1803cc7727f5ad1ed1ea6122b
expected_tokenizer=809240f7a182cde859a4fc4ebc902e619a173d507e99304c1092aa04e7a6658e
expected_tokenizer_config=8103b5dd4baf13b38ee927370fbfeab2b1378457efaa233d1c5f0410c40dc9f9
expected_target_configuration=9446b4fca6f895bd0ed79d861f33447f8c231ba42b7c89cb4b4d25af3958c1fd
expected_target_modeling=765fd328542d176ff6a62ac814327b11a824df29bdca001d341e9a7c2fe9d876
expected_draft_code=7f908e8aea464132f6cb24e35f0adeee59ceed318f75ec4ee5f08bdff1aec07c
expected_c=bd337e35e8c5735f7e7ab2e4ff97835931c86a6daa51241329c3997a6b61f5b4
expected_xpu_c=625af4bbe792effde9f2f54c319f807a5c49b9756be313f9307d90da9ff5149e
expected_moe_c=0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0
expected_grouped_gemm=78a7218de45ee46b3734dc977c0d6115607ff7536706c0be2d4728b4ca2c40be
expected_xpu_smi_version=d14b356677a57006a19e1e5b4aa45cada8fc0c553cd214ac76ad420ef5bdb4ab
expected_runtime_versions=$'torch=2.12.0+xpu\nvllm=0.1.dev1172+g4a6fd8747.xpu\ntransformers=5.13.1\nvllm-xpu-kernels=0.1.11.dev53+g744a8b4\ntriton-xpu=3.7.1'

actual_vllm="$(git -C "$vllm_root" rev-parse HEAD)"
actual_kernels="$(git -C "$kernel_root" rev-parse HEAD)"
actual_suite="$(sha256sum "$repo_root/$suite_rel" | awk '{print $1}')"
[[ "$actual_vllm" == "$expected_vllm" ]] || {
  echo "vLLM identity mismatch: $actual_vllm" >&2
  exit 3
}
[[ "$actual_kernels" == "$expected_kernels" ]] || {
  echo "kernel identity mismatch: $actual_kernels" >&2
  exit 3
}
[[ "$actual_suite" == "$expected_suite" ]] || {
  echo "suite identity mismatch: $actual_suite" >&2
  exit 3
}

check_hash() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(sha256sum "$path" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || {
    echo "SHA256 mismatch for $path: $actual" >&2
    exit 3
  }
}

check_hash "$teacher" "$expected_teacher"
check_hash "$serve_script" "$expected_launcher"
check_hash "$compare_script" "$expected_comparator"
check_hash "$benchmark_script" "$expected_benchmark"
check_hash "$target_config" "$expected_target_config"
check_hash "$draft_config" "$expected_draft_config"
check_hash "$target_tree" "$expected_target_tree"
check_hash "$draft_tree" "$expected_draft_tree"
check_hash "$target_root/chat_template.jinja" "$expected_chat_template"
check_hash "$target_root/generation_config.json" "$expected_generation_config"
check_hash "$target_root/model.safetensors.index.json" "$expected_weight_index"
check_hash "$target_root/special_tokens_map.json" "$expected_special_tokens"
check_hash "$target_root/tokenizer.json" "$expected_tokenizer"
check_hash "$target_root/tokenizer_config.json" "$expected_tokenizer_config"
check_hash "$target_root/configuration_laguna.py" "$expected_target_configuration"
check_hash "$target_root/modeling_laguna.py" "$expected_target_modeling"
check_hash "$draft_root/config.py" "$expected_draft_code"
check_hash "$kernel_root/vllm_xpu_kernels/_C.abi3.so" "$expected_c"
check_hash "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" "$expected_xpu_c"
check_hash "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" "$expected_moe_c"
check_hash \
  "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
  "$expected_grouped_gemm"

verify_manifest_sizes() {
  local root="$1"
  local tree="$2"
  local expected_count="$3"
  "$venv_python" - "$root" "$tree" "$expected_count" <<'PY'
import json
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
tree = Path(sys.argv[2])
expected_count = int(sys.argv[3])
files = json.loads(tree.read_text(encoding="utf-8")).get("files")
if not isinstance(files, dict) or len(files) != expected_count:
    raise SystemExit(
        f"{tree}: expected {expected_count} manifest files, "
        f"found {None if not isinstance(files, dict) else len(files)}"
    )
for name, metadata in files.items():
    path = root / name
    expected_size = metadata.get("size")
    if not path.is_file() or path.stat().st_size != expected_size:
        actual_size = path.stat().st_size if path.exists() else None
        raise SystemExit(
            f"{path}: expected size {expected_size}, found {actual_size}"
        )
    expected_sha256 = metadata.get("lfs_sha256")
    if expected_sha256 is not None:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
                digest.update(chunk)
        actual_sha256 = digest.hexdigest()
        if actual_sha256 != expected_sha256:
            raise SystemExit(
                f"{path}: expected SHA256 {expected_sha256}, "
                f"found {actual_sha256}"
            )
PY
}

runtime_versions="$(
  "$venv_python" - <<'PY'
from importlib.metadata import version

for name in ("torch", "vllm", "transformers", "vllm-xpu-kernels", "triton-xpu"):
    print(f"{name}={version(name)}")
PY
)"
if [[ "$runtime_versions" != "$expected_runtime_versions" ]]; then
  echo "runtime package identity mismatch:" >&2
  printf '%s\n' "$runtime_versions" >&2
  exit 3
fi

[[ -z "$(git -C "$vllm_root" status --short)" ]] || {
  echo "vLLM source tree is dirty" >&2
  exit 3
}
[[ -z "$(git -C "$kernel_root" status --short)" ]] || {
  echo "kernel source tree is dirty" >&2
  exit 3
}
if curl -fsS "$base_url/health" >/dev/null 2>&1; then
  echo "Laguna endpoint is already active" >&2
  exit 4
fi
if ss -H -ltn 'sport = :18080' | grep -q .; then
  echo "port 18080 already has a listener" >&2
  exit 4
fi
if pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1; then
  echo "an existing vLLM process is active" >&2
  exit 4
fi

verify_manifest_sizes "$target_root" "$target_tree" 27
verify_manifest_sizes "$draft_root" "$draft_tree" 5

mkdir -p "$run_dir"

capture_idle_xpu() {
  local output_path="$1"
  local residual_path="$2"
  if ! timeout 15 xpu-smi ps > "$output_path"; then
    echo "xpu-smi ps failed or timed out" >&2
    return 1
  fi
  if ! awk '
    NR == 1 {
      header_ok = $1 == "PID" && $2 == "Command" && $3 == "DeviceID" \
        && $4 == "SHR" && $5 == "MEM"
      next
    }
    {
      rows += 1
      if ($2 != "xpu-smi" || $3 !~ /^[0-3]$/) {
        print
        bad = 1
        next
      }
      seen[$3] += 1
    }
    END {
      if (!header_ok) {
        print "invalid xpu-smi ps header"
        bad = 1
      }
      if (rows != 4) {
        print "expected exactly four xpu-smi probe rows; found " rows
        bad = 1
      }
      for (device = 0; device < 4; device += 1) {
        if (seen[device] != 1) {
          print "expected one xpu-smi probe row for device " device \
            "; found " seen[device]
          bad = 1
        }
      }
      exit bad
    }
  ' "$output_path" > "$residual_path"; then
    echo "XPU idle proof failed:" >&2
    cat "$residual_path" >&2
    return 1
  fi
}

xpu-smi -v > "$run_dir/xpu-smi-version.txt"
check_hash "$run_dir/xpu-smi-version.txt" "$expected_xpu_smi_version"
capture_idle_xpu \
  "$run_dir/prestart-xpu-ps.txt" \
  "$run_dir/prestart-residual.txt"

unset PYTHONPATH
unset TRITON_INTEL_DISABLE_IGC_OPT
unset VLLM_XPU_LAGUNA_PARITY_RETURN_STAGE
unset VLLM_LAGUNA_TARGET_TRACE_DIR
unset VLLM_LAGUNA_TARGET_TRACE_INPUTS
unset VLLM_LAGUNA_TARGET_TRACE_LAYER
unset VLLM_LAGUNA_TARGET_TRACE_POSITION
unset VLLM_LAGUNA_TARGET_TRACE_RANK
export ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3
export ZE_AFFINITY_MASK=0,1,2,3
export VLLM_XPU_LAGUNA_PARITY_PROBE=0
export VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
export VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
export VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK="$bf16_router_topk"
export VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=0
export VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0
export VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0
export VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0
export VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0
export VLLM_DISABLE_SHARED_EXPERTS_STREAM=0
export VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256
export VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0
export VLLM_XPU_V4_M1_BIASED_TOPK=0
export VLLM_XPU_V4_M1_ROUTER_NORM=0
export VLLM_TRACE_FUNCTION=0
export LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7
export LAGUNA_DFLASH_ROOT="$draft_root"
export LAGUNA_GPU_MEMORY_UTILIZATION=0.90
export VLLM_EXTRA_ARGS=

{
  date -u +%Y-%m-%dT%H:%M:%SZ
  uname -a
  git -C "$repo_root" rev-parse HEAD
  git -C "$vllm_root" rev-parse HEAD
  git -C "$kernel_root" rev-parse HEAD
  sha256sum \
    "$script_path" \
    "$serve_script" \
    "$compare_script" \
    "$benchmark_script" \
    "$repo_root/$suite_rel" \
    "$teacher" \
    "$run_dir/xpu-smi-version.txt" \
    "$target_tree" \
    "$draft_tree" \
    "$target_config" \
    "$draft_config" \
    "$target_root/chat_template.jinja" \
    "$target_root/generation_config.json" \
    "$target_root/model.safetensors.index.json" \
    "$target_root/special_tokens_map.json" \
    "$target_root/tokenizer.json" \
    "$target_root/tokenizer_config.json" \
    "$target_root/configuration_laguna.py" \
    "$target_root/modeling_laguna.py" \
    "$draft_root/config.py" \
    "$kernel_root/vllm_xpu_kernels/_C.abi3.so" \
    "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" \
    "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" \
    "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
  printf '%s\n' \
    "model=$target_root" \
    "model_revision=$target_revision" \
    "draft_model=$draft_root" \
    "draft_revision=$draft_revision" \
    'target_manifest_files=27' \
    'draft_manifest_files=5' \
    'target_lfs_sha256_files=15' \
    'draft_lfs_sha256_files=1' \
    'ambient_sensitive_environment=empty_before_runner' \
    'ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3' \
    'ZE_AFFINITY_MASK=0,1,2,3' \
    'CCL_ATL_TRANSPORT=ofi' \
    'CCL_TOPO_P2P_ACCESS=1' \
    'VLLM_KV_CACHE_LAYOUT=NHD' \
    'VLLM_XPU_EXACT_SPEC_ATTN=1' \
    'VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1' \
    'VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1' \
    'VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1' \
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=$bf16_router_topk" \
    'VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=0' \
    'VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0' \
    'VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0' \
    'VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0' \
    'VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0' \
    'VLLM_XPU_LAGUNA_PARITY_PROBE=0' \
    'VLLM_XPU_LAGUNA_PARITY_RETURN_STAGE=<unset>' \
    'VLLM_LAGUNA_TARGET_TRACE=<unset>' \
    'VLLM_DISABLE_SHARED_EXPERTS_STREAM=0' \
    'VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256' \
    'VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0' \
    'VLLM_XPU_V4_M1_BIASED_TOPK=0' \
    'VLLM_XPU_V4_M1_ROUTER_NORM=0' \
    'VLLM_TRACE_FUNCTION=0' \
    'TRITON_INTEL_DISABLE_IGC_OPT=<unset>' \
    'VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0' \
    'VLLM_USE_AOT_COMPILE=0' \
    'XPU_GRAPH=0' \
    'VLLM_XPU_ENABLE_XPU_GRAPH=0' \
    'LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7' \
    'LAGUNA_GPU_MEMORY_UTILIZATION=0.90' \
    'VLLM_EXTRA_ARGS=' \
    'mode=dflash eager --no-async-scheduling kv=bfloat16 max_num_seqs=1' \
    'prefix_caching=disabled' \
    'generation_warmup=none' \
    'benchmark=max_tokens=512 metric_tokens=100 seed=1 return_token_ids=true' \
    "suite=$repo_root/$suite_rel" \
    "teacher=$teacher" \
    "treatment=$treatment"
  printf '%s\n' "$runtime_versions"
} > "$run_dir/identity.txt"

server_pid=""
leader_alive() {
  [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null
}

leader_is_zombie() {
  [[ -n "$server_pid" ]] \
    && [[ -r "/proc/$server_pid/stat" ]] \
    && [[ "$(awk '{print $3}' "/proc/$server_pid/stat")" == Z ]]
}

process_group_alive() {
  [[ -n "$server_pid" ]] && kill -0 -- "-$server_pid" 2>/dev/null
}

service_alive() {
  leader_alive || process_group_alive
}

stop_service() {
  local signal
  local attempts
  if [[ -z "$server_pid" ]]; then
    return 0
  fi
  for signal in INT TERM KILL; do
    if ! service_alive; then
      break
    fi
    if process_group_alive; then
      kill "-$signal" -- "-$server_pid" 2>/dev/null || true
    fi
    if leader_alive; then
      kill "-$signal" "$server_pid" 2>/dev/null || true
    fi
    case "$signal" in
      INT) attempts=30 ;;
      TERM) attempts=15 ;;
      KILL) attempts=10 ;;
    esac
    for _ in $(seq 1 "$attempts"); do
      service_alive || break
      sleep 1
    done
  done
  if leader_is_zombie || ! leader_alive; then
    wait "$server_pid" 2>/dev/null || true
  fi
  if service_alive; then
    echo "server leader or process group $server_pid survived bounded shutdown" >&2
    return 1
  fi
}

poststop_proof() {
  local clean=0
  for _ in $(seq 1 30); do
    if ! ss -H -ltn 'sport = :18080' | grep -q . \
      && ! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1; then
      clean=1
      break
    fi
    sleep 2
  done
  if (( clean == 0 )); then
    echo "vLLM processes or port 18080 remained after shutdown" >&2
    return 1
  fi
  capture_idle_xpu \
    "$run_dir/poststop-xpu-ps.txt" \
    "$run_dir/poststop-residual.txt"
}

finalize() {
  local original_status="$1"
  local stop_status=0
  local proof_status=0
  local final_status="$original_status"
  trap - EXIT INT TERM
  set +e
  stop_service
  stop_status=$?
  poststop_proof
  proof_status=$?
  if (( final_status == 0 && (stop_status != 0 || proof_status != 0) )); then
    final_status=6
  fi
  {
    printf 'original_status=%s\n' "$original_status"
    printf 'stop_status=%s\n' "$stop_status"
    printf 'poststop_proof_status=%s\n' "$proof_status"
    printf 'final_status=%s\n' "$final_status"
  } > "$run_dir/cleanup-status.txt"
  if (( final_status == 0 )); then
    echo "completed $treatment leg: $run_dir"
  fi
  exit "$final_status"
}

trap 'finalize "$?"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

setsid "$serve_script" dflash "$run_dir" bfloat16 \
  > "$run_dir/server.log" 2>&1 &
server_pid="$!"
printf '%s\n' "$server_pid" > "$run_dir/server.pid"

ready=0
for _ in $(seq 1 180); do
  if curl -fsS "$base_url/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "service exited before becoming healthy" >&2
    tail -120 "$run_dir/server.log" >&2
    exit 5
  fi
  sleep 5
done
if (( ready == 0 )); then
  echo "service did not become healthy within 15 minutes" >&2
  tail -120 "$run_dir/server.log" >&2
  exit 5
fi

curl -fsS "$base_url/metrics" > "$run_dir/metrics-before-suite.prom"

cd "$repo_root"
"$venv_python" "$benchmark_script" \
  --base-url "$base_url" \
  --model laguna-s-2.1-int4 \
  --suite "$suite_rel" \
  --max-tokens 512 \
  --metric-tokens 100 \
  --seed 1 \
  --timeout 1800 \
  --return-token-ids \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
  --out "$run_dir/bench.json" \
  | tee "$run_dir/bench.stdout"

curl -fsS "$base_url/metrics" > "$run_dir/metrics-after-suite.prom"

"$venv_python" "$compare_script" \
  --teacher "$teacher" \
  --candidate "$run_dir/bench.json" \
  --out "$run_dir/exactness-vs-q1.json" \
  > "$run_dir/exactness-vs-q1.stdout"

jq -e '
  .fresh_response_validity.valid == true and
  .fresh_response_validity.prompts_are_unique == true and
  .fresh_response_validity.each_prompt_run_once == true and
  .fresh_response_validity.cached_tokens_all_zero == true and
  .fresh_response_validity.history_acceleration == false and
  .fresh_response_validity.ngram_history_acceleration == false and
  .fresh_response_validity.response_reuse == false and
  .fresh_response_validity.context_checkpoints_or_prefix_reuse == false and
  .realistic_final_gate.passed == true and
  .realistic_final_gate.return_token_ids_requested == true and
  .run_identity.api_mode == "chat" and
  .run_identity.model == "laguna-s-2.1-int4" and
  .run_identity.seed == 1 and
  .run_identity.max_tokens == 512 and
  .run_identity.prompt_count == 13 and
  .run_identity.return_token_ids == true and
  .run_identity.request_extra.chat_template_kwargs.enable_thinking == false and
  .run_identity.suite.suite_id == "laguna-s-2.1-realistic-cold-v1" and
  .run_identity.suite.version == 1 and
  .run_identity.suite_path ==
    "experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
' "$run_dir/bench.json" >/dev/null

jq -e '
  .all_exact == true and
  (.candidates | length) == 1 and
  .candidates[0].comparison.exact == true and
  .candidates[0].comparison.exact_count == 13 and
  .candidates[0].comparison.total == 13 and
  .candidates[0].comparison.all_cached_zero == true
' "$run_dir/exactness-vs-q1.json" >/dev/null
