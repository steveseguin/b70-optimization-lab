#!/usr/bin/env bash
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
readonly leg="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_mwide_measurement_leg.sh"
readonly oracle="$script_dir/teacher-token-oracle-v1.json"
readonly text_oracle="$script_dir/teacher-text-sha256-v1.json"
readonly verifier="$script_dir/verify-record.sh"

readonly vllm_tree="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-width12-stack-clean-20260726}"
readonly kernel_tree="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-width12-router-clean-20260726}"
readonly venv_root="${REPRO_VENV_ROOT:-/home/steve/.venvs/deepseek-v4-xpu}"
readonly cluster_ip="${REPRO_CLUSTER_IP:-10.0.0.65}"
readonly run_root=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs
readonly stamp="$(date -u +%Y%m%dT%H%M%SZ)"
readonly run_dir="${RUN_DIR:-$run_root/laguna-width12-dflash-fp8-repro-$stamp}"
readonly expected_vllm=e596ef1543466ae1a05e5bb8091f58872e2b18ba
readonly expected_kernels=6f9dd3c3a7b1b677a992ca4f431a968408f9c816
readonly expected_oracle=a2be70c2c603ceaaf5de4558ef80c6063e54a38af604623463a0bcbc22e3cdeb
readonly expected_text_oracle=3b669ddc389a08c75b7812b5af2394032476019fae04b9de83e51f520db0cf72

die() {
  printf 'Laguna published-102/conventional-101.942 repro: %s\n' "$*" >&2
  exit 2
}

check_hash() {
  local path="$1" expected="$2" actual
  [[ -f "$path" ]] || die "missing file: $path"
  actual="$(sha256sum -- "$path")"
  actual="${actual%% *}"
  [[ "$actual" == "$expected" ]] \
    || die "SHA256 mismatch for $path: expected $expected, got $actual"
}

check_tree() {
  local tree="$1" expected="$2" name="$3" actual dirty
  [[ -e "$tree/.git" ]] || die "missing $name Git worktree: $tree"
  actual="$(git -C "$tree" rev-parse HEAD)"
  [[ "$actual" == "$expected" ]] \
    || die "$name commit mismatch: expected $expected, got $actual"
  dirty="$(git -C "$tree" status --porcelain --untracked-files=all)"
  [[ -z "$dirty" ]] || die "$name worktree is dirty: $tree"
}

preflight() {
  local main_dirty manifest_a manifest_b device fstype
  for command in git jq sha256sum findmnt cmp ip ss pgrep curl; do
    command -v "$command" >/dev/null || die "missing command: $command"
  done

  main_dirty="$(git -C "$repo_root" status --porcelain --untracked-files=all)"
  [[ -z "$main_dirty" ]] || die "main reproduction repository is dirty"

  check_tree "$vllm_tree" "$expected_vllm" vLLM
  check_tree "$kernel_tree" "$expected_kernels" XPU-kernel

  check_hash "$oracle" "$expected_oracle"
  check_hash "$text_oracle" "$expected_text_oracle"
  check_hash "$repo_root/experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json" \
    9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
  check_hash "$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py" \
    c18b6f37aa0f5a848a9d771fa91de14bab115b41557b9d7066bce5984c2a6945
  check_hash "$repo_root/scripts/bench-openai-realistic-suite.py" \
    40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2a
  check_hash "$repo_root/scripts/qualify_realistic_window_metrics.py" \
    3f930c1789a468873b23181353c77c7f8ba875db8415b409670f034e9ca92b20
  check_hash "$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/capture_laguna_m8_idle_snapshot.py" \
    1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01
  check_hash "$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna_mwide_graph_nvme.sh" \
    5618cfbe8d3206ee19fb6446ed5b4372b773491b25ca41676b3f602bd28cf745
  check_hash "$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh" \
    99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55
  check_hash "$leg" c12a3c04cee81feee12fb477ecea8a3249c110eda6b978d7ef54bb13f0f20ca1

  check_hash "$kernel_tree/vllm_xpu_kernels/_C.abi3.so" \
    126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2
  check_hash "$kernel_tree/vllm_xpu_kernels/_xpu_C.abi3.so" \
    f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
  check_hash "$kernel_tree/vllm_xpu_kernels/_moe_C.abi3.so" \
    00fd81608f057039d31e1b316fecbecec60b3b03151e66b95d0f844185119715
  check_hash "$kernel_tree/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
    fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96
  check_hash "$kernel_tree/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
    3390a3065de25e06dbe95a8fbc2c8456c3489a2295816782e90a4086aedc9dd4
  check_hash "$kernel_tree/vllm_xpu_kernels/libattn_kernels_xe_2.so" \
    ad0eb26f3b0680fcd54a50de821e9c881524d50ad5361b872f88cb0b333b65ca

  check_hash "$venv_root/bin/python" \
    202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
  check_hash "$venv_root/bin/vllm" \
    d16721cbe3e6bef44881b6b45ce64d9362a82bec4748754bd91ec85704c243fb
  check_hash "$venv_root/lib/libccl.so.2.0" \
    1185b0591e66f3b94f19b891367ad1c4ad5a95792f658f46d284fc7c643aedb7
  check_hash "$venv_root/lib/libsycl.so.8.0.0" \
    0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f
  check_hash "$venv_root/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so" \
    63b7a56723482bc35d31842f442f6e903ef0b7fbd741c1a4ae309123bbc90572

  "$venv_root/bin/python" - <<'PY'
from importlib.metadata import version
import torch

expected = {
    "compressed-tensors": "0.17.0",
    "oneccl": "2021.17.2",
    "safetensors": "0.8.0",
    "transformers": "5.13.1",
    "triton-xpu": "3.7.1",
}
assert torch.__version__ == "2.12.0+xpu", torch.__version__
for package, wanted in expected.items():
    actual = version(package)
    assert actual == wanted, (package, wanted, actual)
PY

  check_hash /mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json \
    9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6
  check_hash /mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4/config.json \
    6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926
  manifest_a=/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/source-files.sha256
  manifest_b=/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/nvme-files.sha256
  check_hash "$manifest_a" 45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac
  check_hash "$manifest_b" 45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac
  cmp -- "$manifest_a" "$manifest_b" >/dev/null \
    || die "source and NVMe model manifests differ"

  read -r device fstype < <(
    findmnt --noheadings --output SOURCE,FSTYPE \
      --target /mnt/fast-ai/llm-models/laguna-s-2.1
  )
  [[ "$device" == /dev/nvme0n1p2 && "$fstype" == ext4 ]] \
    || die "model root is on $device ($fstype), expected /dev/nvme0n1p2 (ext4)"

  "$verifier" >/dev/null
  printf 'preflight=PASS\n'
  printf 'vllm_commit=%s\n' "$expected_vllm"
  printf 'kernel_commit=%s\n' "$expected_kernels"
  printf 'token_oracle_sha256=%s\n' "$expected_oracle"
  printf 'text_oracle_sha256=%s\n' "$expected_text_oracle"
}

action="${1:---run}"
[[ $# -le 1 ]] || die "usage: run.sh [--preflight|--run]"
case "$action" in
  --preflight)
    preflight
    exit 0
    ;;
  --run)
    preflight
    ;;
  *)
    die "usage: run.sh [--preflight|--run]"
    ;;
esac

[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] \
  || die "RUN_DIR must be an absolute canonical path"
case "$run_dir" in
  "$run_root"/*) ;;
  *) die "RUN_DIR must be below $run_root" ;;
esac

printf 'Laguna S 2.1 exact published-metric reproduction\n'
printf 'published_legacy_tok_s=102.97143559613157\n'
printf 'conventional_interval_tok_s=101.94172124017027\n'
printf 'metric_warning=the historical score divides 100 events by a 99-interval span\n'
printf 'run_dir=%s\n' "$run_dir"
printf 'policy=one cold suite, first valid score, no retry\n'

exec /usr/bin/env -i \
  HOME="${HOME:-/home/steve}" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  REPRO_VLLM_TREE="$vllm_tree" \
  REPRO_KERNEL_TREE="$kernel_tree" \
  REPRO_VENV_ROOT="$venv_root" \
  REPRO_CLUSTER_IP="$cluster_ip" \
  REPRO_TEACHER="$oracle" \
  REPRO_TEACHER_SHA256="$expected_oracle" \
  REPRO_TEACHER_TEXT_ORACLE="$text_oracle" \
  REPRO_TEACHER_TEXT_ORACLE_SHA256="$expected_text_oracle" \
  "$leg" candidate B2 "$run_dir" 12 11 1 0 0 0 0 0 0 1 1
