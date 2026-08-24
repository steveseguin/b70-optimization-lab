#!/usr/bin/env bash
set -uo pipefail

# Opt-in fresh-cache smoke/final runner for the official rolling Qwen3.8 XPU
# image comparison/replay lane. Historical pinned-image runners remain
# separate. This runner does not establish that the image contains literal
# current upstream main; use a separately labeled custom-current-main build
# when the embedded source trails upstream.
#
# Usage: run-20260823-qwen38-rolling-nightly-strict-smoke.sh \
#   MTP KV MAXLEN GPUS PORT OUT_DIR SUITE CACHE_DIR
#
# Required CACHE_POLICY:
#   fresh        CACHE_DIR must not exist and must live on ext4.
#   seeded-fresh CACHE_DIR must not exist; only a validated .best_config
#                 bundle is copied in before a genuinely fresh compilation.
#   replay       CACHE_DIR must exist; EXPECTED_CACHE_MANIFEST_SHA256 is
#                 required.
#
# Image acquisition:
#   SOURCE_IMAGE_TAG defaults to vllm/vllm-openai-xpu:nightly.
#   PULL_SOURCE_IMAGE defaults to 1. The floating tag is pulled and resolved to
#   exactly one matching registry RepoDigest; only that immutable reference is
#   launched.
#   PULL_SOURCE_IMAGE=0 is an offline replay and requires both
#   EXPECTED_RESOLVED_IMAGE_DIGEST and EXPECTED_IMAGE_ID.
#
# Useful environment:
#   SUDO_PASS_FILE, EXTRA_VLLM_ARGS, GPU_MEM_UTIL, VLLM_XPU_GRAPH
#   PYTHONHASHSEED, VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE
#   VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING, TRITON_CACHE_AUTOTUNING
#   PROMPT_IDS (comma-separated), MAX_TOKENS (default 128), BENCH (default 1)
#   CANARY (default 1), NATURAL_EOS (default 0), RETURN_TOKEN_IDS (default 1)
#   QUALITY (default 0), QUALITY_BASELINE_JSON, QUALITY_REQUIRE_BASELINE
#   REQUIRE_GRAPH_CAPTURE (default 0; set to 1 for graph promotion work)
#   BEST_CONFIG_SEED_DIR, EXPECTED_BEST_CONFIG_SEED_COUNT,
#   EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256, BEST_CONFIG_TARGET_AOT_NAMESPACE,
#   EXPECTED_CACHE_OUTER_NAMESPACE, EXPECTED_CACHE_CODE_HASH,
#   EXPECTED_CACHE_COMPILER_HASH, EXPECTED_CACHE_CONFIG_HASH,
#   EXPECTED_CACHE_ENV_SHA256, EXPECTED_COMPUTATION_GRAPH_SHA256S

readonly image_repository="vllm/vllm-openai-xpu"
source_image_tag=${SOURCE_IMAGE_TAG:-vllm/vllm-openai-xpu:nightly}
pull_source_image=${PULL_SOURCE_IMAGE:-1}

mtp=${1:?}; kv=${2:?}; maxlen=${3:?}; gpu=${4:?}; port=${5:?}
out=${6:?}; suite=${7:?}; cache_dir=${8:?}
tp=$(( $(tr -dc ',' <<< "$gpu" | wc -c) + 1 ))
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
venv=/home/steve/.venvs/vllm-xpu
alias=qwen38-rolling-nightly-strict
name="qwen38-rolling-nightly-strict-${port}"
cache_policy=${CACHE_POLICY:?set CACHE_POLICY=fresh, seeded-fresh, or replay}
best_config_seed_dir=${BEST_CONFIG_SEED_DIR:-}
expected_best_config_seed_count=${EXPECTED_BEST_CONFIG_SEED_COUNT:-}
expected_best_config_seed_manifest_sha256=${EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256:-}
best_config_target_aot_namespace=${BEST_CONFIG_TARGET_AOT_NAMESPACE:-}
expected_cache_outer_namespace=${EXPECTED_CACHE_OUTER_NAMESPACE:-}
expected_cache_code_hash=${EXPECTED_CACHE_CODE_HASH:-}
expected_cache_compiler_hash=${EXPECTED_CACHE_COMPILER_HASH:-}
expected_cache_config_hash=${EXPECTED_CACHE_CONFIG_HASH:-}
expected_cache_env_sha256=${EXPECTED_CACHE_ENV_SHA256:-}
expected_computation_graph_sha256s=${EXPECTED_COMPUTATION_GRAPH_SHA256S:-}

dockerc() {
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    sudo -S -p '' docker "$@" < "$SUDO_PASS_FILE"
  else
    docker "$@"
  fi
}

fail() {
  echo "error: $*" >&2
  exit 1
}

cache_manifest() {
  local destination=$1
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    sudo -S -p '' bash -c '
      cd "$1" || exit 1
      find . -type f -print0 | sort -z | xargs -0 -r sha256sum
    ' bash "$cache_dir" < "$SUDO_PASS_FILE" > "$destination"
  else
    (
      cd "$cache_dir" || exit 1
      find . -type f -print0 | sort -z | xargs -0 -r sha256sum
    ) > "$destination"
  fi
}

best_config_manifest() {
  local source_dir=$1 destination=$2
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    sudo -S -p '' bash -c '
      cd "$1" || exit 1
      find . -type f -name "*.best_config" -print0 | sort -z |
        xargs -0 -r sha256sum
    ' bash "$source_dir" < "$SUDO_PASS_FILE" > "$destination"
  else
    (
      cd "$source_dir" || exit 1
      find . -type f -name '*.best_config' -print0 | sort -z |
        xargs -0 -r sha256sum
    ) > "$destination"
  fi
}

cache_jq() {
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    sudo -S -p '' jq "$@" < "$SUDO_PASS_FILE"
  else
    jq "$@"
  fi
}

cache_file_sha256() {
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    sudo -S -p '' sha256sum "$1" < "$SUDO_PASS_FILE" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

valid_sha256_ref() {
  [[ $1 =~ ^sha256:[0-9a-f]{64}$ ]]
}

valid_sha256() {
  [[ $1 =~ ^[0-9a-f]{64}$ ]]
}

[[ "$cache_policy" == "fresh" || "$cache_policy" == "seeded-fresh" || \
   "$cache_policy" == "replay" ]] || \
  fail "CACHE_POLICY must be fresh, seeded-fresh, or replay"
[[ "$pull_source_image" == "0" || "$pull_source_image" == "1" ]] || \
  fail "PULL_SOURCE_IMAGE must be 0 or 1"
[[ "$source_image_tag" == "$image_repository:"* ]] || \
  fail "SOURCE_IMAGE_TAG must be a tag in $image_repository"
[[ "$source_image_tag" != "$image_repository:latest" ]] || \
  fail ":latest is a release comparator, not this rolling-nightly experiment"
[[ "$source_image_tag" != *@* ]] || \
  fail "SOURCE_IMAGE_TAG must be a floating tag, not a digest reference"
if [[ "$pull_source_image" == "0" ]]; then
  [[ -n "${EXPECTED_RESOLVED_IMAGE_DIGEST:-}" ]] || \
    fail "offline replay requires EXPECTED_RESOLVED_IMAGE_DIGEST"
  [[ -n "${EXPECTED_IMAGE_ID:-}" ]] || \
    fail "offline replay requires EXPECTED_IMAGE_ID"
fi
if [[ "$cache_policy" == "seeded-fresh" ]]; then
  [[ -n "${EXPECTED_RESOLVED_IMAGE_DIGEST:-}" ]] || \
    fail "seeded-fresh requires EXPECTED_RESOLVED_IMAGE_DIGEST"
  [[ -n "${EXPECTED_IMAGE_ID:-}" ]] || \
    fail "seeded-fresh requires EXPECTED_IMAGE_ID"
  [[ -d "$best_config_seed_dir" ]] || \
    fail "seeded-fresh requires BEST_CONFIG_SEED_DIR"
  [[ "$expected_best_config_seed_count" =~ ^[1-9][0-9]*$ ]] || \
    fail "seeded-fresh requires a positive EXPECTED_BEST_CONFIG_SEED_COUNT"
  valid_sha256 "$expected_best_config_seed_manifest_sha256" || \
    fail "seeded-fresh requires EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256"
  [[ "$best_config_target_aot_namespace" =~ ^[0-9a-f]{64}$ ]] || \
    fail "seeded-fresh requires a 64-hex BEST_CONFIG_TARGET_AOT_NAMESPACE"
  [[ "$expected_cache_outer_namespace" =~ ^[0-9a-f]{10}$ ]] || \
    fail "seeded-fresh requires a 10-hex EXPECTED_CACHE_OUTER_NAMESPACE"
  valid_sha256 "$expected_cache_code_hash" || \
    fail "seeded-fresh requires EXPECTED_CACHE_CODE_HASH"
  [[ "$expected_cache_compiler_hash" =~ ^[0-9a-f]{10}$ ]] || \
    fail "seeded-fresh requires a 10-hex EXPECTED_CACHE_COMPILER_HASH"
  [[ "$expected_cache_config_hash" =~ ^[0-9a-f]{10}$ ]] || \
    fail "seeded-fresh requires a 10-hex EXPECTED_CACHE_CONFIG_HASH"
  valid_sha256 "$expected_cache_env_sha256" || \
    fail "seeded-fresh requires EXPECTED_CACHE_ENV_SHA256"
  [[ -n "$expected_computation_graph_sha256s" ]] || \
    fail "seeded-fresh requires EXPECTED_COMPUTATION_GRAPH_SHA256S"
fi
if [[ -n "${EXPECTED_RESOLVED_IMAGE_DIGEST:-}" ]]; then
  valid_sha256_ref "$EXPECTED_RESOLVED_IMAGE_DIGEST" || \
    fail "EXPECTED_RESOLVED_IMAGE_DIGEST must be sha256 plus 64 lowercase hex digits"
fi
if [[ -n "${EXPECTED_IMAGE_ID:-}" ]]; then
  valid_sha256_ref "$EXPECTED_IMAGE_ID" || \
    fail "EXPECTED_IMAGE_ID must be sha256 plus 64 lowercase hex digits"
fi
[[ -f "$suite" ]] || fail "missing suite: $suite"
[[ -f "$model_manifest" ]] || fail "missing model manifest: $model_manifest"
[[ -x "$model_verifier" ]] || fail "missing model verifier: $model_verifier"
[[ "${REQUIRE_GRAPH_CAPTURE:-0}" == "0" || \
   "${REQUIRE_GRAPH_CAPTURE:-0}" == "1" ]] || \
  fail "REQUIRE_GRAPH_CAPTURE must be 0 or 1"
if [[ "${REQUIRE_GRAPH_CAPTURE:-0}" == "1" ]]; then
  [[ "${VLLM_XPU_GRAPH:-}" == "1" ]] || \
    fail "REQUIRE_GRAPH_CAPTURE=1 requires VLLM_XPU_GRAPH=1"
fi
[[ ! -e "$out" ]] || fail "strict output already exists: $out"
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail "lab repo must be clean"
if dockerc ps --format '{{.Names}}' | grep -qx "$name"; then
  fail "container $name already running"
fi
pgrep -af 'EngineCore|vllm serve' | grep -v pgrep >/dev/null && \
  fail "a host vLLM server is already running"

cache_parent=$(dirname -- "$cache_dir")
mkdir -p "$cache_parent"
cache_fstype=$(findmnt -n -o FSTYPE -T "$cache_parent")
[[ "$cache_fstype" == "ext4" ]] || fail "strict cache must be on ext4, got $cache_fstype"
if [[ "$cache_policy" == "fresh" || "$cache_policy" == "seeded-fresh" ]]; then
  [[ ! -e "$cache_dir" ]] || fail "fresh cache already exists: $cache_dir"
  mkdir "$cache_dir"
else
  [[ -d "$cache_dir" ]] || fail "replay cache is missing: $cache_dir"
  [[ -n "${EXPECTED_CACHE_MANIFEST_SHA256:-}" ]] || \
    fail "replay requires EXPECTED_CACHE_MANIFEST_SHA256"
fi
mkdir -p "$(dirname -- "$out")"
mkdir "$out"
cp "$suite" "$out/validation-suite.json"

if [[ "$pull_source_image" == "1" ]]; then
  dockerc pull "$source_image_tag" > "$out/image-pull.log" 2>&1 || \
    fail "failed to pull source image tag: $source_image_tag"
  image_acquisition=pulled
else
  printf 'pull skipped: explicit offline replay\n' > "$out/image-pull.log"
  image_acquisition=offline-replay
fi

dockerc image inspect "$source_image_tag" > "$out/image-tag-inspect.json" || \
  fail "source image tag is unavailable: $source_image_tag"
tag_image_id=$(dockerc image inspect --format '{{.Id}}' "$source_image_tag") || \
  fail "could not read source tag image ID"
valid_sha256_ref "$tag_image_id" || fail "invalid source tag image ID: $tag_image_id"

matching_repo_digests=()
while IFS= read -r repo_digest; do
  [[ "$repo_digest" == "$image_repository@"* ]] || continue
  matching_repo_digests+=( "$repo_digest" )
done < <(
  dockerc image inspect \
    --format '{{range .RepoDigests}}{{println .}}{{end}}' "$source_image_tag"
)
[[ "${#matching_repo_digests[@]}" == "1" ]] || \
  fail "expected exactly one $image_repository RepoDigest, found ${#matching_repo_digests[@]}"

resolved_image_ref=${matching_repo_digests[0]}
resolved_image_digest=${resolved_image_ref#*@}
valid_sha256_ref "$resolved_image_digest" || \
  fail "invalid resolved registry digest: $resolved_image_digest"
if [[ -n "${EXPECTED_RESOLVED_IMAGE_DIGEST:-}" ]]; then
  [[ "$resolved_image_digest" == "$EXPECTED_RESOLVED_IMAGE_DIGEST" ]] || \
    fail "resolved registry digest mismatch: $resolved_image_digest"
fi
if [[ -n "${EXPECTED_IMAGE_ID:-}" ]]; then
  [[ "$tag_image_id" == "$EXPECTED_IMAGE_ID" ]] || \
    fail "source tag image ID mismatch: $tag_image_id"
fi

dockerc image inspect "$resolved_image_ref" > "$out/image-resolved-inspect.json" || \
  fail "resolved immutable image reference is unavailable: $resolved_image_ref"
resolved_image_id=$(dockerc image inspect --format '{{.Id}}' "$resolved_image_ref") || \
  fail "could not read resolved image ID"
valid_sha256_ref "$resolved_image_id" || \
  fail "invalid resolved image ID: $resolved_image_id"
[[ "$resolved_image_id" == "$tag_image_id" ]] || \
  fail "source tag and resolved registry digest map to different image IDs"
printf '%s\n' "$source_image_tag" > "$out/image-source-tag.txt"
printf '%s\n' "$resolved_image_ref" > "$out/image-resolved-ref.txt"
printf '%s\n' "$resolved_image_digest" > "$out/image-registry-digest.txt"
printf '%s\n' "$tag_image_id" > "$out/image-id.txt"

best_config_seed_target=
if [[ "$cache_policy" == "seeded-fresh" ]]; then
  [[ ! -L "$best_config_seed_dir" ]] || fail "seed directory must not be a symlink"
  [[ -z "$(find "$best_config_seed_dir" -type l -print -quit)" ]] || \
    fail "seed directory contains a symlink"
  seed_total_files=$(find "$best_config_seed_dir" -type f | wc -l)
  seed_best_config_files=$(find "$best_config_seed_dir" -type f \
    -name '*.best_config' | wc -l)
  [[ "$seed_total_files" == "$expected_best_config_seed_count" ]] || \
    fail "seed bundle has unexpected total file count: $seed_total_files"
  [[ "$seed_best_config_files" == "$expected_best_config_seed_count" ]] || \
    fail "seed bundle has unexpected .best_config count: $seed_best_config_files"
  invalid_seed_path=$(find "$best_config_seed_dir" -type f -printf '%P\n' |
    grep -Ev '^[0-9a-z]{2}/[0-9a-f]{64}\.best_config$' | head -n 1 || true)
  [[ -z "$invalid_seed_path" ]] || fail "invalid seed relative path: $invalid_seed_path"
  best_config_manifest "$best_config_seed_dir" \
    "$out/best-config-seed.source.sha256" || fail "could not manifest seed bundle"
  actual_seed_manifest_sha=$(sha256sum "$out/best-config-seed.source.sha256" |
    awk '{print $1}')
  [[ "$actual_seed_manifest_sha" == \
     "$expected_best_config_seed_manifest_sha256" ]] || \
    fail "seed bundle manifest mismatch: $actual_seed_manifest_sha"

  best_config_seed_target="$cache_dir/vllm/torch_compile_cache/torch_aot_compile/$best_config_target_aot_namespace/inductor_cache"
  mkdir -p "$best_config_seed_target"
  while IFS= read -r -d '' seed_file; do
    relative_seed_file=${seed_file#"$best_config_seed_dir"/}
    mkdir -p "$best_config_seed_target/$(dirname -- "$relative_seed_file")"
    cp --reflink=never -- "$seed_file" \
      "$best_config_seed_target/$relative_seed_file"
  done < <(find "$best_config_seed_dir" -type f -name '*.best_config' \
    -print0 | sort -z)
  best_config_manifest "$best_config_seed_target" \
    "$out/best-config-seed.precompile.sha256" || \
    fail "could not manifest precompiled seed target"
  cmp -s "$out/best-config-seed.source.sha256" \
    "$out/best-config-seed.precompile.sha256" || \
    fail "seed target differs before compilation"
  preseed_total_files=$(find "$cache_dir" -type f | wc -l)
  [[ "$preseed_total_files" == "$expected_best_config_seed_count" ]] || \
    fail "seeded fresh cache contains unexpected precompile artifacts"
fi

"$model_verifier" "$model_manifest" "$model" \
  --json "$out/model-direct-and-ordinary-verify.json" \
  > "$out/model-direct-and-ordinary-verify.log" 2>&1 || \
  fail "model direct-and-ordinary identity verification failed"
sha256sum "$model_manifest" "$suite" \
  "$repo/scripts/bench-openai-realistic-suite.py" \
  "$repo/scripts/qwen38-text-quality-suite.py" \
  "$model_verifier" "${BASH_SOURCE[0]}" > "$out/input-files.sha256" || \
  fail "failed to hash run inputs"
uname -a > "$out/host-uname.txt" || fail "failed to capture host kernel identity"
ls -l /dev/dri/by-path > "$out/host-dri-by-path.txt" || \
  fail "failed to capture DRM device mapping"

if [[ "$cache_policy" == "replay" ]]; then
  cache_manifest "$out/cache-manifest.pre.sha256"
  actual_manifest_sha=$(sha256sum "$out/cache-manifest.pre.sha256" | awk '{print $1}')
  [[ "$actual_manifest_sha" == "$EXPECTED_CACHE_MANIFEST_SHA256" ]] || \
    fail "replay cache manifest mismatch"
fi

args=( "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
  --served-model-name "$alias" --tensor-parallel-size "$tp"
  --max-model-len "$maxlen" --max-num-seqs 1 --max-num-batched-tokens 1024
  --gpu-memory-utilization "${GPU_MEM_UTIL:-0.90}" --dtype float16
  --reasoning-parser qwen3
  --default-chat-template-kwargs '{"enable_thinking": false}'
  --enable-prompt-tokens-details --no-enable-prefix-caching )
[[ "$kv" != "f16" ]] && args+=( --kv-cache-dtype "$kv" )
[[ "$mtp" != "0" ]] && args+=(
  --speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":$mtp}"
)
[[ -n "${EXTRA_VLLM_ARGS:-}" ]] && args+=( ${EXTRA_VLLM_ARGS} )
printf '%s\n' "${args[@]}" > "$out/server-args.txt"

env_args=(
  -e CCL_ZE_IPC_EXCHANGE=sockets
  -e ZE_AFFINITY_MASK="$gpu"
  -e VLLM_NO_USAGE_STATS=1
  -e VLLM_CACHE_ROOT=/run-cache/vllm
  -e XDG_CACHE_HOME=/run-cache/xdg
)
for variable in VLLM_XPU_GRAPH PYTHONHASHSEED \
  VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE \
  VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING TRITON_CACHE_AUTOTUNING; do
  if [[ -n "${!variable:-}" ]]; then
    container_variable=$variable
    [[ "$variable" == "VLLM_XPU_GRAPH" ]] && \
      container_variable=VLLM_XPU_ENABLE_XPU_GRAPH
    env_args+=( -e "$container_variable=${!variable}" )
  fi
done

{
  echo "source_image_tag=$source_image_tag"
  echo "image_acquisition=$image_acquisition"
  echo "pull_source_image=$pull_source_image"
  echo "resolved_image_ref=$resolved_image_ref"
  echo "registry_digest=$resolved_image_digest"
  echo "tag_image_id=$tag_image_id"
  echo "resolved_image_id=$resolved_image_id"
  echo "expected_resolved_image_digest=${EXPECTED_RESOLVED_IMAGE_DIGEST:-unset}"
  echo "expected_image_id=${EXPECTED_IMAGE_ID:-unset}"
  echo "cache_policy=$cache_policy"
  echo "cache_dir=$cache_dir"
  echo "best_config_seed_dir=${best_config_seed_dir:-unset}"
  echo "expected_best_config_seed_count=${expected_best_config_seed_count:-unset}"
  echo "expected_best_config_seed_manifest_sha256=${expected_best_config_seed_manifest_sha256:-unset}"
  echo "best_config_target_aot_namespace=${best_config_target_aot_namespace:-unset}"
  echo "expected_cache_outer_namespace=${expected_cache_outer_namespace:-unset}"
  echo "expected_cache_code_hash=${expected_cache_code_hash:-unset}"
  echo "expected_cache_compiler_hash=${expected_cache_compiler_hash:-unset}"
  echo "expected_cache_config_hash=${expected_cache_config_hash:-unset}"
  echo "expected_cache_env_sha256=${expected_cache_env_sha256:-unset}"
  echo "expected_computation_graph_sha256s=${expected_computation_graph_sha256s:-unset}"
  echo "tp=$tp"
  echo "gpus=$gpu"
  echo "mtp=$mtp"
  echo "kv=$kv"
  echo "max_model_len=$maxlen"
  echo "gpu_memory_utilization=${GPU_MEM_UTIL:-0.90}"
  echo "vllm_xpu_graph=${VLLM_XPU_GRAPH:-unset}"
  echo "pythonhashseed=${PYTHONHASHSEED:-unset}"
  echo "inductor_max_autotune=${VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE:-unset}"
  echo "inductor_coordinate_descent=${VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING:-unset}"
  echo "triton_cache_autotuning=${TRITON_CACHE_AUTOTUNING:-unset}"
  echo "require_graph_capture=${REQUIRE_GRAPH_CAPTURE:-0}"
  echo "natural_eos=${NATURAL_EOS:-0}"
  echo "return_token_ids=${RETURN_TOKEN_IDS:-1}"
  echo "prompt_ids=${PROMPT_IDS:-all}"
  echo "quality=${QUALITY:-0}"
  echo "quality_require_baseline=${QUALITY_REQUIRE_BASELINE:-0}"
  echo "quality_baseline_json=${QUALITY_BASELINE_JSON:-unset}"
  if [[ -n "${QUALITY_BASELINE_JSON:-}" && -f "$QUALITY_BASELINE_JSON" ]]; then
    echo "quality_baseline_sha256=$(sha256sum "$QUALITY_BASELINE_JSON" | awk '{print $1}')"
  else
    echo "quality_baseline_sha256=unset"
  fi
  echo "lab_git_head=$(git -C "$repo" rev-parse HEAD)"
} > "$out/identity.env"

cleanup() {
  local cleanup_rc=$?
  if [[ ! -f "$out/final.status" ]]; then
    echo "fail rc=$cleanup_rc" > "$out/final.status"
  fi
  dockerc logs "$name" > "$out/server.log" 2>&1 || true
  dockerc inspect "$name" > "$out/container-inspect.json" 2>/dev/null || true
  if [[ -d "$cache_dir" ]]; then
    cache_manifest "$out/cache-manifest.post.sha256" || true
    sha256sum "$out/cache-manifest.post.sha256" \
      > "$out/cache-manifest.post.sha256.digest" 2>/dev/null || true
  fi
  dockerc rm -f "$name" >/dev/null 2>&1 || true
  exit "$cleanup_rc"
}
trap cleanup EXIT

dockerc run -d --name "$name" \
  --device /dev/dri --group-add 44 --group-add 992 --ipc=host \
  -v /dev/dri/by-path:/dev/dri/by-path:ro \
  -v /mnt/usb-models:/mnt/usb-models \
  -v "$cache_dir:/run-cache" \
  -p "127.0.0.1:$port:8000" \
  "${env_args[@]}" --shm-size 16g \
  "$resolved_image_ref" "${args[@]}" > "$out/container-id.txt" || exit 2
container_image_id=$(dockerc inspect --format '{{.Image}}' "$name") || exit 2
printf '%s\n' "$container_image_id" > "$out/container-image-id.txt"
[[ "$container_image_id" == "$resolved_image_id" ]] || \
  fail "container launched an unexpected image ID: $container_image_id"

healthy=0
for _ in $(seq 1 240); do
  if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  state=$(dockerc inspect --format '{{.State.Running}}' "$name" 2>/dev/null || echo false)
  [[ "$state" == "true" ]] || exit 2
  sleep 5
done
[[ "$healthy" == "1" ]] || exit 2
dockerc exec "$name" python3 -c \
  'import importlib.metadata as m, torch, transformers, triton, vllm; print("vllm", vllm.__version__); print("torch", torch.__version__); print("triton", triton.__version__); print("transformers", transformers.__version__); print("vllm-xpu-kernels", m.version("vllm-xpu-kernels"))' \
  > "$out/stack-versions.txt" 2>&1 || exit 2
dockerc exec "$name" git -C /workspace/vllm show -s \
  '--format=%H%n%cI%n%s' HEAD > "$out/vllm-source-commit.txt" 2>&1 || exit 2
dockerc logs "$name" > "$out/server-startup.log" 2>&1 || exit 2
if [[ "${REQUIRE_GRAPH_CAPTURE:-0}" == "1" ]]; then
  grep -Fq 'quantization=inc' "$out/server-startup.log" || \
    fail "effective engine config did not report quantization=inc"
  grep -Fq 'enforce_eager=False' "$out/server-startup.log" || \
    fail "effective engine config reported eager fallback or was not captured"
  grep -Fq 'Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)' \
    "$out/server-startup.log" || fail "PIECEWISE graph capture marker missing"
  grep -Fq 'Capturing CUDA graphs (decode, FULL)' \
    "$out/server-startup.log" || fail "FULL decode graph capture marker missing"
  grep -Fq 'Graph capturing finished' "$out/server-startup.log" || \
    fail "graph completion marker missing"
fi

if [[ "$cache_policy" == "seeded-fresh" ]]; then
  grep -Fq 'Compiling a graph for compile range' "$out/server-startup.log" || \
    fail "seeded-fresh did not perform a fresh graph compilation"
  grep -Fq 'saved AOT compiled function' "$out/server-startup.log" || \
    fail "seeded-fresh did not save a fresh AOT compilation"
  grep -Fq "/torch_aot_compile/$best_config_target_aot_namespace/" \
    "$out/server-startup.log" || \
    fail "seeded-fresh compiled into an unexpected AOT namespace"
  if grep -Fq 'Directly load AOT compilation' "$out/server-startup.log"; then
    fail "seeded-fresh unexpectedly loaded an existing AOT model"
  fi

  IFS=',' read -r -a expected_graph_hashes <<< \
    "$expected_computation_graph_sha256s"
  [[ "${#expected_graph_hashes[@]}" == "$tp" ]] || \
    fail "expected graph hash count does not match TP size"
  for rank in $(seq 0 $((tp - 1))); do
    factors="$cache_dir/vllm/torch_compile_cache/$expected_cache_outer_namespace/rank_${rank}_0/backbone/cache_key_factors.json"
    graph="$cache_dir/vllm/torch_compile_cache/$expected_cache_outer_namespace/rank_${rank}_0/backbone/computation_graph.py"
    [[ -f "$factors" && -f "$graph" ]] || \
      fail "missing rank-$rank cache identity files"
    [[ "$(cache_jq -r '.code_hash' "$factors")" == \
       "$expected_cache_code_hash" ]] || fail "rank-$rank code hash mismatch"
    [[ "$(cache_jq -r '.compiler_hash' "$factors")" == \
       "$expected_cache_compiler_hash" ]] || \
      fail "rank-$rank compiler hash mismatch"
    [[ "$(cache_jq -r '.config_hash' "$factors")" == \
       "$expected_cache_config_hash" ]] || fail "rank-$rank config hash mismatch"
    actual_env_sha=$(cache_jq -S '.env' "$factors" | sha256sum | awk '{print $1}')
    [[ "$actual_env_sha" == "$expected_cache_env_sha256" ]] || \
      fail "rank-$rank cache environment hash mismatch"
    [[ "$(cache_file_sha256 "$graph")" == "${expected_graph_hashes[$rank]}" ]] || \
      fail "rank-$rank computation graph hash mismatch"
  done

  best_config_manifest "$best_config_seed_target" \
    "$out/best-config-seed.postcompile.sha256" || \
    fail "could not manifest postcompile seed target"
  cmp -s "$out/best-config-seed.source.sha256" \
    "$out/best-config-seed.postcompile.sha256" || \
    fail "compiler changed the seeded .best_config bundle"
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    postcompile_best_config_count=$(sudo -S -p '' find "$cache_dir" -type f \
      -name '*.best_config' < "$SUDO_PASS_FILE" | wc -l)
  else
    postcompile_best_config_count=$(find "$cache_dir" -type f \
      -name '*.best_config' | wc -l)
  fi
  [[ "$postcompile_best_config_count" == \
     "$expected_best_config_seed_count" ]] || \
    fail "compiler added unexpected .best_config records"
fi

if [[ "${CANARY:-1}" == "1" ]]; then
  "$venv/bin/python" - "http://127.0.0.1:$port" "$alias" "$out/canary.json" <<'PY'
import json, sys, urllib.request
base_url, model, destination = sys.argv[1:]
payload = {
    "model": model,
    "messages": [{"role": "user", "content": "What does this Python expression evaluate to? Answer only the integer: sum(i * i for i in range(4))"}],
    "max_tokens": 8,
    "temperature": 0,
    "top_p": 1,
    "seed": 20260609,
    "chat_template_kwargs": {"enable_thinking": False},
}
request = urllib.request.Request(
    f"{base_url}/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=900) as response:
    data = json.loads(response.read())
content = (data["choices"][0]["message"].get("content") or "").strip()
usage = data.get("usage") or {}
cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
result = {"content": content, "cached_tokens": cached, "response": data}
open(destination, "w").write(json.dumps(result, indent=2) + "\n")
if content != "14" or cached != 0:
    raise SystemExit(3)
PY
  canary_rc=$?
  echo "canary_rc=$canary_rc" > "$out/canary.status"
  [[ "$canary_rc" == "0" ]] || exit "$canary_rc"
fi

if [[ "${BENCH:-1}" == "1" ]]; then
  curl -fsS "http://127.0.0.1:$port/metrics" > "$out/metrics.before.prom"
  bench_args=(
    --base-url "http://127.0.0.1:$port" --model "$alias" --api-mode chat
    --suite "$suite" --max-tokens "${MAX_TOKENS:-128}" --metric-tokens 100
    --seed 1 --timeout 900 --out "$out/bench.json"
  )
  [[ "${RETURN_TOKEN_IDS:-1}" == "1" ]] && bench_args+=( --return-token-ids )
  if [[ -n "${PROMPT_IDS:-}" ]]; then
    IFS=',' read -r -a prompt_ids <<< "$PROMPT_IDS"
    for prompt_id in "${prompt_ids[@]}"; do
      bench_args+=( --prompt-id "$prompt_id" )
    done
  fi
  if [[ "${NATURAL_EOS:-0}" == "1" ]]; then
    bench_args+=( --require-natural-eos
      --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' )
  else
    bench_args+=(
      --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}'
    )
  fi
  "$venv/bin/python" "$repo/scripts/bench-openai-realistic-suite.py" \
    "${bench_args[@]}" > "$out/bench.stdout.log" 2>&1
  bench_rc=$?
  echo "bench_rc=$bench_rc" > "$out/bench.status"
  [[ "$bench_rc" == "0" ]] || exit "$bench_rc"
  curl -fsS "http://127.0.0.1:$port/metrics" > "$out/metrics.after.prom"
fi

if [[ "${QUALITY:-0}" == "1" ]]; then
  quality_args=(
    --base-url "http://127.0.0.1:$port" --model "$alias"
    --tokenizer "$model" --timeout 900 --repeat-runs 8
    --long-context-tokens 8192
    --request-id-prefix "qwen38-rolling-nightly-strict-${port}"
    --chat-template-kwargs-json '{"enable_thinking":false}'
    --output-json "$out/quality.json"
  )
  if [[ -n "${QUALITY_BASELINE_JSON:-}" ]]; then
    [[ -f "$QUALITY_BASELINE_JSON" ]] || \
      fail "missing quality baseline: $QUALITY_BASELINE_JSON"
    quality_args+=( --baseline-json "$QUALITY_BASELINE_JSON" )
  fi
  if [[ "${QUALITY_REQUIRE_BASELINE:-0}" == "1" ]]; then
    [[ -n "${QUALITY_BASELINE_JSON:-}" ]] || \
      fail "QUALITY_REQUIRE_BASELINE=1 requires QUALITY_BASELINE_JSON"
    quality_args+=( --require-baseline )
  fi
  "$venv/bin/python" "$repo/scripts/qwen38-text-quality-suite.py" \
    "${quality_args[@]}" > "$out/quality.stdout.log" 2>&1
  quality_rc=$?
  echo "quality_rc=$quality_rc" > "$out/quality.status"
  [[ "$quality_rc" == "0" ]] || exit "$quality_rc"
fi

if [[ "$cache_policy" == "seeded-fresh" ]]; then
  best_config_manifest "$best_config_seed_target" \
    "$out/best-config-seed.final.sha256" || \
    fail "could not manifest final seed target"
  cmp -s "$out/best-config-seed.source.sha256" \
    "$out/best-config-seed.final.sha256" || \
    fail "workload changed the seeded .best_config bundle"
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    final_best_config_count=$(sudo -S -p '' find "$cache_dir" -type f \
      -name '*.best_config' < "$SUDO_PASS_FILE" | wc -l)
  else
    final_best_config_count=$(find "$cache_dir" -type f \
      -name '*.best_config' | wc -l)
  fi
  [[ "$final_best_config_count" == "$expected_best_config_seed_count" ]] || \
    fail "workload added unexpected .best_config records"
fi

if [[ "$cache_policy" == "replay" ]]; then
  cache_manifest "$out/cache-manifest.replay-final.sha256"
  cmp -s "$out/cache-manifest.pre.sha256" "$out/cache-manifest.replay-final.sha256" || \
    exit 4
fi

echo "pass" > "$out/final.status"
