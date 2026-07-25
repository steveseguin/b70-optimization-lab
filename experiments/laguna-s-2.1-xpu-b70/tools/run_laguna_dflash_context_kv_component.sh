#!/usr/bin/env bash
# One-shot, non-generative four-card DFlash context-KV component gate.
set -euo pipefail
set -f
umask 077
export PYTHONDONTWRITEBYTECODE=1

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
readonly repo=/home/steve/llm-optimizations
readonly vllm=/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725
readonly kernels=/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly tools="$repo/experiments/laguna-s-2.1-xpu-b70/tools"
readonly shell_path="$(realpath -e -- "$0")"
readonly consumer="$tools/create_laguna_dflash_context_kv_consumption.py"
readonly worker="$tools/run_laguna_dflash_context_kv_component.py"
readonly analyzer="$tools/analyze_laguna_dflash_context_kv_component.py"
readonly root="${1:?usage: run_laguna_dflash_context_kv_component.sh FRESH_NVME_ROOT}"
readonly expected_vllm=4459910e2ac5a7b552887fc0a3f3e3cf9a4701c0
readonly expected_kernels=4772f727590c51b72add79350b913d098cf67872
readonly authorization_dir=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations

die() { echo "Laguna DFlash context-KV gate: $*" >&2; exit 2; }

cleanup() {
  local rc=$?
  [[ -d "$root" ]] && chmod -R a-w -- "$root" || true
  exit "$rc"
}
trap cleanup EXIT

[[ "$0" == "$shell_path" && ! -L "$0" ]] ||
  die "runner must be invoked by its absolute non-symlink path"

[[ "$root" == /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/* ]] ||
  die "run root must be beneath the internal-NVMe Laguna run root"
[[ "$(realpath -m -- "$root")" == "$root" && ! -e "$root" && ! -L "$root" ]] ||
  die "run root must be fresh and canonical"
[[ -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)" ]] ||
  die "main worktree is dirty"
[[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" &&
   -z "$(git -C "$vllm" status --porcelain=v1 --untracked-files=all)" ]] ||
  die "vLLM source identity drift"
[[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernels" &&
   -z "$(git -C "$kernels" status --porcelain=v1 --untracked-files=all)" ]] ||
  die "kernel source identity drift"

ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] || die "refusing inherited runtime variables: $ambient_sensitive"

[[ "$(findmnt --noheadings --output SOURCE --target "$(dirname -- "$root")" | xargs)" == /dev/nvme0n1p2 &&
   "$(findmnt --noheadings --output FSTYPE --target "$(dirname -- "$root")" | xargs)" == ext4 ]] ||
  die "campaign root is not on the frozen internal NVMe/ext4 filesystem"
mkdir --mode=700 -- "$root"
mkdir -p -- "$root/cards" "$root/private"/{home,tmp,cache,xdg/{config,data,state}}
chmod -R 700 -- "$root"
readonly main_commit="$(git -C "$repo" rev-parse HEAD)"
{
  printf 'schema=laguna-dflash-context-kv-component-campaign-v1\n'
  printf 'purpose=exactness-only component; generation=false; timing=false; endpoint=false; submission=false\n'
  printf 'vllm=%s\nkernels=%s\n' "$expected_vllm" "$expected_kernels"
  printf 'main=%s\n' "$main_commit"
  sha256sum -- "$shell_path" "$consumer" "$worker" "$analyzer"
} >"$root/identity.txt"
printf 'consumed=true\nmain=%s\n' "$main_commit" >"$root/consumed.txt"
sync -f "$root/identity.txt"
sync -f "$root/consumed.txt"
readonly packet_sha256="$(sha256sum -- "$root/identity.txt" | awk '{print $1}')"
mkdir -p -- "$authorization_dir"
chmod 700 -- "$authorization_dir"
readonly consumption_marker="$authorization_dir/laguna-dflash-context-kv-${main_commit}-${packet_sha256}.consumed.json"
"$python" "$consumer" \
  --marker "$consumption_marker" \
  --run-root "$root" \
  --main-commit "$main_commit" \
  --packet-sha256 "$packet_sha256" \
  >"$root/consumption-creator.stdout" ||
  die "this exact committed packet has already been consumed"
/usr/bin/timeout --foreground --signal=TERM --kill-after=2s 15s \
  env -i PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/xpu-smi discovery -j >"$root/device-discovery.json"
sync -f "$root/device-discovery.json"

for rank in 0 1 2 3; do
  set +e
  /usr/bin/timeout --foreground --preserve-status --signal=TERM --kill-after=30s 600s \
    /usr/bin/env -i \
    PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    HOME="$root/private/home" TMP="$root/private/tmp" TEMP="$root/private/tmp" \
    TMPDIR="$root/private/tmp" XDG_CACHE_HOME="$root/private/cache" \
    XDG_CONFIG_HOME="$root/private/xdg/config" \
    XDG_DATA_HOME="$root/private/xdg/data" \
    XDG_STATE_HOME="$root/private/xdg/state" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    PYTHONHASHSEED=0 PYTHONPATH="$vllm:$kernels" \
    ONEAPI_DEVICE_SELECTOR=level_zero:0 ZE_AFFINITY_MASK="$rank" \
    VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1 \
    LD_PRELOAD= \
    LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
    "$python" "$worker" --rank "$rank" --main-commit "$main_commit" \
    --consumption-marker "$consumption_marker" \
    --device-discovery "$root/device-discovery.json" \
    --out "$root/cards/rank${rank}.json" \
    >"$root/cards/rank${rank}.stdout" 2>"$root/cards/rank${rank}.stderr"
  status=$?
  set -e
  (( status == 0 )) || die "physical-card leg $rank failed with status $status"
done

"$python" "$analyzer" --root "$root" --out "$root/analysis.json" \
  >"$root/analyzer.stdout" 2>"$root/analyzer.stderr"
find "$root" -type f ! -name final-manifest.sha256 -print0 |
  sort -z | xargs -0 sha256sum >"$root/final-manifest.sha256"
sync -f "$root/final-manifest.sha256"
chmod -R a-w -- "$root"
trap - EXIT
echo "Laguna DFlash context-KV component passed: $root"
