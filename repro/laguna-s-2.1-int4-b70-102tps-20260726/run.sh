#!/usr/bin/env bash
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
readonly leg="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_mwide_measurement_leg.sh"
readonly oracle="$script_dir/teacher-token-oracle-v1.json"
readonly text_oracle="$script_dir/teacher-text-sha256-v1.json"
readonly verifier="$script_dir/verify-record.sh"
readonly runtime_verifier="$script_dir/verify-runtime.py"
readonly runtime_lock="$script_dir/manifests/runtime-lock.json"
readonly model_manifest="$script_dir/manifests/model-release-files.sha256"
readonly model_restore="$script_dir/restore-models.sh"
readonly source_restore="$script_dir/restore-sources.sh"

readonly vllm_tree="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-width12-stack-clean-20260726}"
readonly kernel_tree="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-width12-router-clean-20260726}"
readonly venv_root="${REPRO_VENV_ROOT:-/home/steve/.venvs/deepseek-v4-xpu}"
readonly xpumem_module="${REPRO_XPUMEM_MODULE:-/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio/vllm_xpu_kernels/xpumem_allocator.abi3.so}"
readonly cluster_ip="${REPRO_CLUSTER_IP:-10.0.0.65}"
readonly kernel_package="$kernel_tree/vllm_xpu_kernels"
readonly native_library_path="$kernel_package:$venv_root/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib"
readonly model_root="${REPRO_MODEL_ROOT:-/mnt/fast-ai/llm-models/laguna-s-2.1}"
readonly artifact_root="${REPRO_ARTIFACT_ROOT:-/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1}"
readonly nvme_device="${REPRO_NVME_DEVICE:-/dev/nvme0n1p2}"
readonly nvme_fstype="${REPRO_NVME_FSTYPE:-ext4}"
readonly run_root="$artifact_root/runs"
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
  local main_dirty manifest_a manifest_b device fstype iface gpu_id bdf discovery
  for command in git jq sha256sum findmnt cmp ip ss pgrep curl lspci xpu-smi; do
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
    1a555cfad62c994fbbd14a66428de5f5ffec1a9fa5f00fb75926da898af2837c
  check_hash "$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna_mwide_graph_nvme.sh" \
    5618cfbe8d3206ee19fb6446ed5b4372b773491b25ca41676b3f602bd28cf745
  check_hash "$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh" \
    bc972c3331a3010c85a4985467e30f216727e45c77ad29d21666536cde5b76cb
  check_hash "$leg" ecdd6e00769e22d57c0d36c9a138fcb55f5bd5ef4f7af7ade7bdcfc64bc734ac
  check_hash "$runtime_verifier" \
    e43f3c9f46e299eeaa8d7bbc828fadeec2ae60f69f39529f7130f154d158f20d
  check_hash "$runtime_lock" \
    8c861e5c9d44232346770e2822aa795179f8f90c2678d2ebbb42a690ef4f4a97
  check_hash "$model_manifest" \
    c19edb79458a24ceb4bb26c991302de71ef29be40e70124e90bf6c13538c692e
  check_hash "$model_restore" \
    62180ebeb0e4267fc898bf7891a411fe681540da0c485ec6e076838edc4dcd34
  check_hash "$source_restore" \
    79d939cd7cb664edcccce3c8819be6c2eba76156c35dbce13aad7b6c1a16ea3d

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
  check_hash "$kernel_tree/vllm_xpu_kernels/libgrouped_gemm_xe_default.so" \
    982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c
  check_hash "$kernel_tree/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so" \
    cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb
  check_hash "$kernel_tree/vllm_xpu_kernels/libmqa_logits_kernels_xe_2.so" \
    58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb
  check_hash "$kernel_tree/vllm_xpu_kernels/libmhc_kernels_xe_2.so" \
    f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f
  check_hash "$xpumem_module" \
    8981f5e312cfab901a5bfa8e40a5a1f194e65db3a207784bfa602e5901e5a1a8

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
  check_hash /usr/bin/xpu-smi \
    2b5b128edf28b38da8637413fe8bfe3a4a40e8113210ba9ddaed945bd56d826e

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

  [[ -d "$model_root" ]] \
    || die "model root is absent: $model_root (set REPRO_MODEL_ROOT to the verified Laguna model root)"
  [[ -d "$artifact_root" ]] \
    || die "artifact root is absent: $artifact_root (set REPRO_ARTIFACT_ROOT to a local NVMe artifact root)"
  check_hash "$model_root/int4/config.json" \
    9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6
  check_hash "$model_root/dflash-int4/config.json" \
    6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926
  manifest_a="$model_root/.verification/source-files.sha256"
  manifest_b="$model_root/.verification/nvme-files.sha256"
  check_hash "$manifest_a" 45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac
  check_hash "$manifest_b" 45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac
  cmp -- "$manifest_a" "$manifest_b" >/dev/null \
    || die "source and NVMe model manifests differ"
  "$model_restore" --verify "$model_root" >/dev/null

  read -r device fstype < <(
    findmnt --noheadings --output SOURCE,FSTYPE \
      --target "$model_root"
  )
  [[ "$device" == "$nvme_device" && "$fstype" == "$nvme_fstype" ]] \
    || die "model root is on $device ($fstype), expected $nvme_device ($nvme_fstype)"

  grep -Fx 'PRETTY_NAME="Ubuntu 24.04.4 LTS"' /etc/os-release >/dev/null \
    || die "OS identity differs from Ubuntu 24.04.4 LTS"
  [[ "$(uname -r)" == 7.0.0-28-generic ]] \
    || die "kernel identity differs from 7.0.0-28-generic"
  [[ -x /opt/intel/oneapi/compiler/2025.3/bin/icpx ]] \
    || die "oneAPI 2025.3 compiler is absent"
  /opt/intel/oneapi/compiler/2025.3/bin/icpx --version \
    | grep -F '2025.3.3 (2025.3.3.20260319)' >/dev/null \
    || die "oneAPI compiler version differs from 2025.3.3"

  iface="$(ip -o -4 addr show | awk -v ip="$cluster_ip" '$4 ~ "^"ip"/" {print $2; exit}')"
  [[ -n "$iface" && "$(cat "/sys/class/net/$iface/operstate")" == up ]] \
    || die "no up interface carries cluster IP $cluster_ip"
  ! ss -H -ltn 'sport = :18080' | grep -q . \
    || die "port 18080 already has a listener"
  ! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 \
    || die "existing vLLM workers block reproduction"

  gpu_id=0
  for bdf in 0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0; do
    lspci -Dn -s "$bdf" | grep -F '8086:e223' >/dev/null \
      || die "expected B70 8086:e223 is absent at $bdf"
    discovery="$(xpu-smi discovery -d "$gpu_id" -j)"
    jq -e --arg bdf "$bdf" '
      .device_name == "Intel(R) Arc(TM) Pro B70 Graphics"
      and .pci_vendor_id == "0x8086"
      and .pci_device_id == "0xe223"
      and .pci_bdf_address == $bdf
    ' <<<"$discovery" >/dev/null \
      || die "xpu-smi device $gpu_id does not match expected B70 at $bdf"
    gpu_id=$((gpu_id + 1))
  done

  /usr/bin/env -i \
    PATH="$venv_root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    PYTHONSAFEPATH=1 \
    PYTHONPATH="$vllm_tree:$kernel_tree" \
    LD_LIBRARY_PATH="$native_library_path" \
    "$venv_root/bin/python" "$runtime_verifier" \
    --lock "$runtime_lock" \
    --vllm-tree "$vllm_tree" \
    --kernel-tree "$kernel_tree" \
    --venv-root "$venv_root" \
    --xpumem-module "$xpumem_module" >/dev/null

  "$verifier" >/dev/null
  printf 'complete_preflight=PASS\n'
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
  REPRO_MODEL_ROOT="$model_root" \
  REPRO_ARTIFACT_ROOT="$artifact_root" \
  REPRO_NVME_DEVICE="$nvme_device" \
  REPRO_NVME_FSTYPE="$nvme_fstype" \
  REPRO_CLUSTER_IP="$cluster_ip" \
  REPRO_RUNTIME_LOCK="$runtime_lock" \
  REPRO_RUNTIME_VERIFIER="$runtime_verifier" \
  REPRO_MODEL_MANIFEST="$model_manifest" \
  REPRO_XPUMEM_MODULE="$xpumem_module" \
  REPRO_TEACHER="$oracle" \
  REPRO_TEACHER_SHA256="$expected_oracle" \
  REPRO_TEACHER_TEXT_ORACLE="$text_oracle" \
  REPRO_TEACHER_TEXT_ORACLE_SHA256="$expected_text_oracle" \
  "$leg" candidate B2 "$run_dir" 12 11 1 0 0 0 0 0 0 1 1
