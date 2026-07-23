#!/usr/bin/env bash
set -euo pipefail

if (( $# != 2 )); then
  echo "usage: run_w1_n128_crossover_leg.sh control|candidate RUN_DIR" >&2
  exit 2
fi
treatment="${1:?usage: run_w1_n128_crossover_leg.sh control|candidate RUN_DIR}"
run_dir="${2:?usage: run_w1_n128_crossover_leg.sh control|candidate RUN_DIR}"
campaign_id=w1-n128-nvme-recovery-abba-8936aac-c59aaad-20260723T131632Z
campaign_root="/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/$campaign_id"

case "$run_dir" in
  "$campaign_root/01-A1-control")
    leg_key=A1
    leg_index=1
    expected_treatment=control
    w1_n_tile=64
    ;;
  "$campaign_root/02-B1-candidate")
    leg_key=B1
    leg_index=2
    expected_treatment=candidate
    w1_n_tile=128
    ;;
  "$campaign_root/03-B2-candidate")
    leg_key=B2
    leg_index=3
    expected_treatment=candidate
    w1_n_tile=128
    ;;
  "$campaign_root/04-A2-control")
    leg_key=A2
    leg_index=4
    expected_treatment=control
    w1_n_tile=64
    ;;
  *)
    echo "RUN_DIR is not one of the four frozen campaign leg paths" >&2
    exit 2
    ;;
esac
if [[ "$treatment" != "$expected_treatment" ]]; then
  echo "$leg_key treatment must be $expected_treatment" >&2
  exit 2
fi
shared_elementwise=1
qknorm_rope=1

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

# shellcheck source=laguna_nvme_paths.sh
source "$(cd -- "$(dirname -- "$0")" && pwd -P)/laguna_nvme_paths.sh"

repo_root=/home/steve/llm-optimizations
vllm_root=/home/steve/src/deepseek-v4-vllm-xpu-dspark
kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
venv_python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
oneccl_library=/home/steve/.venvs/deepseek-v4-xpu/lib/libccl.so
libfabric_library=/home/steve/.venvs/deepseek-v4-xpu/lib/libfabric.so
suite_rel=experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json
artifact_root=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1
model_root=/mnt/fast-ai/llm-models/laguna-s-2.1
target_root="$model_root/int4"
draft_root="$model_root/dflash-int4"
source_model_manifest="$model_root/.verification/source-files.sha256"
model_manifest="$model_root/.verification/nvme-files.sha256"
expected_model_aggregate_manifest=45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac
teacher="$artifact_root/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json"
target_revision=4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb
draft_revision=5e07c246915c86dc6920fead03d019989224f2ba
target_tree="$target_root/.cache/huggingface/trees/$target_revision.json"
draft_tree="$draft_root/.cache/huggingface/trees/$draft_revision.json"
target_config="$target_root/config.json"
draft_config="$draft_root/config.json"
nvme_paths_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh"
serve_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna_nvme.sh"
compare_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py"
benchmark_script="$repo_root/scripts/bench-openai-realistic-suite.py"
analyzer_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/analyze_w1_n128_crossover.py"
preregistration="$repo_root/experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-w1-n128-nvme-recovery-preregistration.md"
formal_component="$artifact_root/runs/w1-n128-formal2-aggregate-c59aaad-8f2345e-20260723T053000-0400/summary.json"
counter_component="$artifact_root/runs/w1-n128-counter-gate-c59aaad-00ceeac-20260723T054500-0400/summary.json"
script_path="$(readlink -f "$0")"
base_url=http://127.0.0.1:18080
campaign_journal="$campaign_root/.campaign-journal.txt"
campaign_lock="$campaign_root/.campaign.lock"
phase1_analysis="$campaign_root/phase1-analysis.json"
phase1_markdown="$campaign_root/phase1-analysis.md"
phase1_stdout="$campaign_root/phase1-analysis.stdout"
phase1_seal="$campaign_root/phase1-analysis.seal.json"
genesis_chain_sha256=0000000000000000000000000000000000000000000000000000000000000000

expected_vllm=8936aac144929190c1e53f8b8624ca397ce16f5b
expected_kernels=c59aaadbbfd350c2b5f4ad663e247c2811ae3181
expected_suite=9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
expected_teacher=d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1
expected_launcher=280ae28aa68fd627f45986673a8288131e4599b4af7fb43a60e0b5acfe22a33c
expected_nvme_paths=99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55
expected_comparator=87ad4d57907a15afba221be42ea00e3a1975308d421e0edc13881dafe38e3db3
expected_benchmark=40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2a
expected_preregistration=82849945856ed78c3d7ca3e700ef3796399d03b65e270839857f6510cc467424
expected_formal_component=bb48793e711cdb20889e888092344d35f0f3c7cb0e85bc120f63f51cff39b932
expected_counter_component=677b69fe353056a8a7a9afff7e7e952fe337a6d605c326beb80ae5e0103b6e76
expected_oneccl=ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3
expected_libfabric=d849d56fd3f8f2581b4b0c17c1564f8145911a313c2c011d694aaf21e5e86b27
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
expected_c=126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2
expected_xpu_c=f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
expected_moe_c=0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0
expected_grouped_gemm=fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96
expected_xpu_smi_version=d14b356677a57006a19e1e5b4aa45cada8fc0c553cd214ac76ad420ef5bdb4ab
expected_runtime_versions=$'torch=2.12.0+xpu\nvllm=0.1.dev1172+g4a6fd8747.xpu\ntransformers=5.13.1\nvllm-xpu-kernels=0.1.11.dev53+g744a8b4\ntriton-xpu=3.7.1'

assert_nvme_identity_constants() {
  local name="$1"
  local actual="$2"
  local expected="$3"
  [[ "$actual" == "$expected" ]] || {
    echo "NVMe path identity mismatch for $name: $actual" >&2
    exit 3
  }
}

assert_nvme_identity_constants artifact_root "$LAGUNA_NVME_ARTIFACT_ROOT" "$artifact_root"
assert_nvme_identity_constants model_root "$LAGUNA_NVME_MODEL_ROOT" "$model_root"
assert_nvme_identity_constants target_root "$LAGUNA_NVME_TARGET_ROOT" "$target_root"
assert_nvme_identity_constants draft_root "$LAGUNA_NVME_DRAFT_ROOT" "$draft_root"
assert_nvme_identity_constants nvme_device "$LAGUNA_NVME_DEVICE" /dev/nvme0n1p2
assert_nvme_identity_constants nvme_fstype "$LAGUNA_NVME_FSTYPE" ext4
assert_nvme_identity_constants backup_root "$LAGUNA_NVME_BACKUP_ROOT" \
  /media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1
assert_nvme_identity_constants cache_root "$LAGUNA_NVME_CACHE_ROOT" "$artifact_root/cache"
assert_nvme_identity_constants tmp_root "$LAGUNA_NVME_TMP_ROOT" "$artifact_root/tmp"
assert_nvme_identity_constants run_root "$LAGUNA_NVME_RUN_ROOT" "$artifact_root/runs"
assert_nvme_identity_constants evidence_root "$LAGUNA_NVME_EVIDENCE_ROOT" "$artifact_root/evidence"
assert_nvme_identity_constants source_manifest "$LAGUNA_NVME_SOURCE_MANIFEST" \
  "$source_model_manifest"
assert_nvme_identity_constants model_manifest "$LAGUNA_NVME_LOCAL_MANIFEST" "$model_manifest"
assert_nvme_identity_constants manifest_sha256 "$LAGUNA_NVME_MANIFEST_SHA256" "$expected_model_aggregate_manifest"
assert_nvme_identity_constants campaign_root "$campaign_root" \
  "$LAGUNA_NVME_RUN_ROOT/$campaign_id"

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
check_hash "$source_model_manifest" "$expected_model_aggregate_manifest"
check_hash "$model_manifest" "$expected_model_aggregate_manifest"
cmp "$source_model_manifest" "$model_manifest"
check_hash "$nvme_paths_script" "$expected_nvme_paths"
check_hash "$serve_script" "$expected_launcher"
check_hash "$compare_script" "$expected_comparator"
check_hash "$benchmark_script" "$expected_benchmark"
check_hash "$preregistration" "$expected_preregistration"
check_hash "$formal_component" "$expected_formal_component"
check_hash "$counter_component" "$expected_counter_component"
check_hash "$oneccl_library" "$expected_oneccl"
check_hash "$libfabric_library" "$expected_libfabric"
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
jq -e '
  .passed == true and
  .component_exactness_and_timing_pass == true and
  .mean_relative_improvement >= .required_mean_relative_improvement
' "$formal_component" >/dev/null
jq -e '
  .passed == true and
  .aggregate.all_cards_passed == true and
  .aggregate.all_full_path_traces_passed == true and
  .aggregate.all_w2_names_and_counts_identical == true and
  .aggregate.all_gather_names_and_counts_identical == true and
  .aggregate.all_profiles_zero_spill_proxies == true
' "$counter_component" >/dev/null

verify_manifest_sizes() {
  local root="$1"
  local tree="$2"
  local expected_count="$3"
  local expected_total_bytes="$4"
  local expected_lfs_count="$5"
  local expected_lfs_bytes="$6"
  "$venv_python" - \
    "$root" "$tree" "$expected_count" "$expected_total_bytes" \
    "$expected_lfs_count" "$expected_lfs_bytes" <<'PY'
import json
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
tree = Path(sys.argv[2])
expected_count = int(sys.argv[3])
expected_total_bytes = int(sys.argv[4])
expected_lfs_count = int(sys.argv[5])
expected_lfs_bytes = int(sys.argv[6])
files = json.loads(tree.read_text(encoding="utf-8")).get("files")
if not isinstance(files, dict) or len(files) != expected_count:
    raise SystemExit(
        f"{tree}: expected {expected_count} manifest files, "
        f"found {None if not isinstance(files, dict) else len(files)}"
    )
total_bytes = sum(metadata.get("size", -1) for metadata in files.values())
lfs_files = [
    metadata for metadata in files.values()
    if metadata.get("lfs_sha256") is not None
]
lfs_bytes = sum(metadata.get("size", -1) for metadata in lfs_files)
if (
    total_bytes != expected_total_bytes
    or len(lfs_files) != expected_lfs_count
    or lfs_bytes != expected_lfs_bytes
):
    raise SystemExit(
        f"{tree}: manifest totals mismatch: "
        f"count={len(files)} bytes={total_bytes} "
        f"lfs_count={len(lfs_files)} lfs_bytes={lfs_bytes}"
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
[[ -z "$(git -C "$repo_root" status --short)" ]] || {
  echo "main source tree is dirty" >&2
  exit 3
}

# This is deliberately the full content check, not just the aggregate-manifest
# hash or metadata comparison. It completes before any endpoint/service start.
laguna_nvme_prepare_paths
laguna_nvme_verify_model_contents

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

verify_manifest_sizes "$target_root" "$target_tree" 27 71922378071 15 71907915776
verify_manifest_sizes "$draft_root" "$draft_tree" 5 2229973769 1 2229962896

runner_sha256="$(sha256sum "$script_path" | awk '{print $1}')"
analyzer_sha256="$(sha256sum "$analyzer_script" | awk '{print $1}')"

validate_campaign_state() {
  "$venv_python" - \
    "$campaign_root" "$campaign_journal" "$campaign_lock" "$leg_index" \
    "$campaign_id" "$runner_sha256" "$analyzer_script" \
    "$phase1_analysis" "$phase1_markdown" "$phase1_stdout" "$phase1_seal" \
    "$genesis_chain_sha256" <<'PY'
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
journal = Path(sys.argv[2])
lock = Path(sys.argv[3])
current_index = int(sys.argv[4])
campaign_id = sys.argv[5]
runner_sha256 = sys.argv[6]
analyzer = Path(sys.argv[7])
phase1_analysis = Path(sys.argv[8])
phase1_markdown = Path(sys.argv[9])
phase1_stdout = Path(sys.argv[10])
phase1_seal = Path(sys.argv[11])
genesis = sys.argv[12]
legs = (
    ("A1", "01-A1-control", "control"),
    ("B1", "02-B1-candidate", "candidate"),
    ("B2", "03-B2-candidate", "candidate"),
    ("A2", "04-A2-control", "control"),
)
evidence_names = (
    "identity.txt",
    "server.pid",
    "xpu-smi-version.txt",
    "prestart-xpu-ps.txt",
    "prestart-residual.txt",
    "server.log",
    "metrics-before-suite.prom",
    "bench.json",
    "bench.stdout",
    "metrics-after-suite.prom",
    "exactness-vs-q1.json",
    "exactness-vs-q1.stdout",
    "poststop-xpu-ps.txt",
    "poststop-residual.txt",
    "cleanup-status.txt",
)
sha_line = re.compile(r"^(?P<sha>[0-9a-f]{64})  (?P<path>/.*)$")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SystemExit(f"{label}: invalid timestamp {value!r}") from error
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise SystemExit(f"{label}: timestamp is not UTC")
    return parsed


if not root.is_dir() or not journal.is_file() or not lock.is_file():
    raise SystemExit("campaign root, journal, or lock is missing")
entries: dict[str, str] = {}
for raw_line in journal.read_text(encoding="utf-8").splitlines():
    if "=" not in raw_line:
        raise SystemExit(f"invalid campaign journal line: {raw_line!r}")
    key, value = raw_line.split("=", 1)
    if not key or key in entries:
        raise SystemExit(f"duplicate or empty campaign journal key: {key!r}")
    entries[key] = value

expected_keys = {
    "campaign_id",
    "campaign_root",
    "runner_sha256",
    "frozen_sequence",
    "genesis_chain_sha256",
}
header = {
    "campaign_id": campaign_id,
    "campaign_root": str(root),
    "runner_sha256": runner_sha256,
    "frozen_sequence": "A1-control,B1-candidate,B2-candidate,A2-control",
    "genesis_chain_sha256": genesis,
}
for key, expected in header.items():
    if entries.get(key) != expected:
        raise SystemExit(
            f"campaign journal header mismatch for {key}: "
            f"{entries.get(key)!r} != {expected!r}"
        )

phase_sha = "-"
if current_index >= 3:
    for path in (phase1_analysis, phase1_markdown, phase1_stdout, phase1_seal):
        if not path.is_file():
            raise SystemExit(f"missing frozen phase-one artifact: {path}")
    if file_sha256(phase1_stdout) != file_sha256(phase1_analysis):
        raise SystemExit("phase-one stdout does not match phase-one JSON")
    phase = json.loads(phase1_analysis.read_text(encoding="utf-8"))
    seal = json.loads(phase1_seal.read_text(encoding="utf-8"))
    expected_phase_dirs = [
        str((root / "01-A1-control").resolve()),
        str((root / "02-B1-candidate").resolve()),
    ]
    phase_checks = {
        "analysis_mode": phase.get("analysis_mode") == "phase1_a1_b1",
        "phase1_pass": phase.get("phase1_pass") is True,
        "failed_phase1_gates_empty": (
            phase.get("failed_gates", {}).get("phase1") == []
        ),
        "order": phase.get("order") == ["A1-control", "B1-candidate"],
        "sequence": phase.get("phase1_sequence", {}).get("passed") is True,
        "pair": phase.get("pairs", {}).get("B1_vs_A1", {}).get("pass") is True,
        "runner_sha256": (
            phase.get("frozen_run_identity", {}).get("runner_sha256")
            == runner_sha256
        ),
        "analyzer_sha256": (
            phase.get("frozen_run_identity", {}).get("analyzer_sha256")
            == file_sha256(analyzer)
        ),
        "run_directories": [
            phase.get("runs", {}).get(key, {}).get("directory")
            for key in ("A1", "B1")
        ]
        == expected_phase_dirs,
        "a1_bench_sha256": (
            phase.get("runs", {}).get("A1", {}).get("bench_sha256")
            == file_sha256(root / "01-A1-control" / "bench.json")
        ),
        "b1_bench_sha256": (
            phase.get("runs", {}).get("B1", {}).get("bench_sha256")
            == file_sha256(root / "02-B1-candidate" / "bench.json")
        ),
        "quality": all(
            phase.get("runs", {})
            .get(key, {})
            .get("quality_and_honesty_pass")
            is True
            for key in ("A1", "B1")
        ),
        "phase_campaign_journal": (
            phase.get("campaign_ledger", {}).get("journal_sha256")
            == seal.get("campaign_journal_sha256")
        ),
        "phase_campaign_journal_current_before_b2": (
            current_index != 3
            or phase.get("campaign_ledger", {}).get("journal_sha256")
            == file_sha256(journal)
        ),
        "phase_campaign_chain": (
            phase.get("campaign_ledger", {}).get("final_chain_sha256")
            == entries.get("B1_chain_sha256")
        ),
        "seal_valid": seal.get("valid") is True,
        "seal_mode": seal.get("analysis_mode") == "phase1_a1_b1",
        "seal_phase1_pass": seal.get("phase1_pass") is True,
        "seal_json": (
            seal.get("analysis_json_sha256") == file_sha256(phase1_analysis)
        ),
        "seal_markdown": (
            seal.get("analysis_markdown_sha256") == file_sha256(phase1_markdown)
        ),
        "seal_stdout": (
            seal.get("analysis_stdout_sha256") == file_sha256(phase1_stdout)
        ),
        "seal_analyzer": (
            seal.get("analyzer_sha256") == file_sha256(analyzer)
        ),
        "seal_runner": seal.get("runner_sha256") == runner_sha256,
        "seal_campaign_journal": (
            seal.get("campaign_journal_sha256")
            == phase.get("campaign_ledger", {}).get("journal_sha256")
        ),
        "seal_campaign_chain": (
            seal.get("campaign_final_chain_sha256")
            == entries.get("B1_chain_sha256")
        ),
    }
    if not all(phase_checks.values()):
        raise SystemExit(f"frozen phase-one analysis does not pass: {phase_checks}")
    phase_sha = file_sha256(phase1_analysis)
    if current_index == 4:
        phase_entries = {
            "phase1_analysis_path": str(phase1_analysis),
            "phase1_analysis_sha256": phase_sha,
            "phase1_markdown_sha256": file_sha256(phase1_markdown),
            "phase1_stdout_sha256": file_sha256(phase1_stdout),
            "phase1_seal_sha256": file_sha256(phase1_seal),
            "phase1_analyzer_sha256": file_sha256(analyzer),
        }
        expected_keys.update(phase_entries)
        for key, expected in phase_entries.items():
            if entries.get(key) != expected:
                raise SystemExit(
                    f"campaign phase-one binding mismatch for {key}: "
                    f"{entries.get(key)!r} != {expected!r}"
                )

previous_chain = genesis
last_cleanup = None
for key, basename, treatment in legs[: current_index - 1]:
    directory = (root / basename).resolve()
    prefix = f"{key}_"
    required = {
        f"{prefix}attempt_started_utc",
        f"{prefix}run_dir",
        f"{prefix}treatment",
        f"{prefix}service_start_utc",
        f"{prefix}final_status",
        f"{prefix}cleanup_completed_utc",
        f"{prefix}evidence_manifest_path",
        f"{prefix}evidence_manifest_sha256",
        f"{prefix}previous_chain_sha256",
        f"{prefix}chain_sha256",
    }
    expected_keys.update(required)
    if entries.get(f"{prefix}run_dir") != str(directory):
        raise SystemExit(f"{key}: journal run directory mismatch")
    if entries.get(f"{prefix}treatment") != treatment:
        raise SystemExit(f"{key}: journal treatment mismatch")
    if entries.get(f"{prefix}final_status") != "0":
        raise SystemExit(f"{key}: prior leg did not complete successfully")
    attempt = entries.get(f"{prefix}attempt_started_utc", "")
    service = entries.get(f"{prefix}service_start_utc", "")
    cleanup = entries.get(f"{prefix}cleanup_completed_utc", "")
    if not (utc(attempt, f"{key} attempt") <= utc(service, f"{key} service")):
        raise SystemExit(f"{key}: service timestamp predates attempt")
    cleanup_time = utc(cleanup, f"{key} cleanup")
    if not (utc(service, f"{key} service") <= cleanup_time):
        raise SystemExit(f"{key}: cleanup timestamp predates service")
    last_cleanup = cleanup_time
    manifest = directory / "leg-evidence.sha256"
    if entries.get(f"{prefix}evidence_manifest_path") != str(manifest):
        raise SystemExit(f"{key}: evidence manifest path mismatch")
    if not manifest.is_file():
        raise SystemExit(f"{key}: evidence manifest is missing")
    manifest_sha = file_sha256(manifest)
    if entries.get(f"{prefix}evidence_manifest_sha256") != manifest_sha:
        raise SystemExit(f"{key}: evidence manifest SHA256 mismatch")
    manifest_entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = sha_line.fullmatch(line)
        if match is None:
            raise SystemExit(f"{key}: invalid evidence manifest line: {line!r}")
        manifest_path = str(Path(match.group("path")).resolve())
        if manifest_path in manifest_entries:
            raise SystemExit(f"{key}: duplicate evidence path {manifest_path}")
        manifest_entries[manifest_path] = match.group("sha")
    expected_paths = {str((directory / name).resolve()) for name in evidence_names}
    if set(manifest_entries) != expected_paths:
        raise SystemExit(f"{key}: evidence manifest path set mismatch")
    expected_entries = set(evidence_names) | {"leg-evidence.sha256"}
    directory_entries = list(directory.iterdir())
    if {path.name for path in directory_entries} != expected_entries:
        raise SystemExit(f"{key}: leg directory entry set mismatch")
    if not all(path.is_file() and not path.is_symlink() for path in directory_entries):
        raise SystemExit(f"{key}: leg directory contains a non-regular file")
    for manifest_path, expected_sha in manifest_entries.items():
        path = Path(manifest_path)
        if not path.is_file() or file_sha256(path) != expected_sha:
            raise SystemExit(f"{key}: evidence changed after manifest: {path}")
    if entries.get(f"{prefix}previous_chain_sha256") != previous_chain:
        raise SystemExit(f"{key}: previous chain mismatch")
    leg_phase_sha = phase_sha if key in {"B2", "A2"} else "-"
    payload = "|".join(
        (
            previous_chain,
            key,
            str(directory),
            treatment,
            attempt,
            service,
            cleanup,
            manifest_sha,
            leg_phase_sha,
        )
    )
    computed_chain = hashlib.sha256((payload + "\n").encode()).hexdigest()
    if entries.get(f"{prefix}chain_sha256") != computed_chain:
        raise SystemExit(f"{key}: campaign chain SHA256 mismatch")
    previous_chain = computed_chain

if last_cleanup is not None:
    idle_gap = (datetime.now(timezone.utc) - last_cleanup).total_seconds()
    if idle_gap < 60.0:
        raise SystemExit(
            "next campaign leg is premature: "
            f"only {idle_gap:.0f}s elapsed since prior cleanup"
        )

if set(entries) != expected_keys:
    raise SystemExit(
        "campaign journal has missing or unexpected keys: "
        f"missing={sorted(expected_keys - set(entries))}, "
        f"unexpected={sorted(set(entries) - expected_keys)}"
    )
expected_directories = {basename for _key, basename, _treatment in legs[: current_index - 1]}
actual_directories = {path.name for path in root.iterdir() if path.is_dir()}
if actual_directories != expected_directories:
    raise SystemExit(
        "campaign root has omitted or intervening leg directories: "
        f"expected={sorted(expected_directories)}, "
        f"actual={sorted(actual_directories)}"
    )
expected_files = {journal.name, lock.name}
if current_index >= 3:
    expected_files.update(
        {
            phase1_analysis.name,
            phase1_markdown.name,
            phase1_stdout.name,
            phase1_seal.name,
        }
    )
actual_files = {path.name for path in root.iterdir() if path.is_file()}
if actual_files != expected_files:
    raise SystemExit(
        "campaign root has unexpected files: "
        f"expected={sorted(expected_files)}, actual={sorted(actual_files)}"
    )
print(previous_chain)
PY
}

if (( leg_index == 1 )); then
  if [[ -e "$campaign_root" ]]; then
    echo "frozen campaign root already exists; A1 cannot be retried" >&2
    exit 7
  fi
  mkdir -p "$run_dir"
else
  if [[ ! -d "$campaign_root" ]]; then
    echo "frozen campaign root is missing; prior legs cannot be omitted" >&2
    exit 7
  fi
fi

exec 9> "$campaign_lock"
if ! flock -n 9; then
  echo "another frozen campaign leg is active" >&2
  exit 7
fi

if (( leg_index == 1 )); then
  previous_chain_sha256="$genesis_chain_sha256"
  {
    printf 'campaign_id=%s\n' "$campaign_id"
    printf 'campaign_root=%s\n' "$campaign_root"
    printf 'runner_sha256=%s\n' "$runner_sha256"
    printf 'frozen_sequence=%s\n' \
      'A1-control,B1-candidate,B2-candidate,A2-control'
    printf 'genesis_chain_sha256=%s\n' "$genesis_chain_sha256"
  } > "$campaign_journal"
else
  previous_chain_sha256="$(validate_campaign_state)"
  if [[ -e "$run_dir" ]]; then
    echo "frozen campaign leg already exists; retries are forbidden" >&2
    exit 7
  fi
  mkdir "$run_dir"
fi

if (( leg_index == 3 )); then
  {
    printf 'phase1_analysis_path=%s\n' "$phase1_analysis"
    printf 'phase1_analysis_sha256=%s\n' \
      "$(sha256sum "$phase1_analysis" | awk '{print $1}')"
    printf 'phase1_markdown_sha256=%s\n' \
      "$(sha256sum "$phase1_markdown" | awk '{print $1}')"
    printf 'phase1_stdout_sha256=%s\n' \
      "$(sha256sum "$phase1_stdout" | awk '{print $1}')"
    printf 'phase1_seal_sha256=%s\n' \
      "$(sha256sum "$phase1_seal" | awk '{print $1}')"
    printf 'phase1_analyzer_sha256=%s\n' "$analyzer_sha256"
  } >> "$campaign_journal"
fi

leg_attempt_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
  printf '%s_attempt_started_utc=%s\n' "$leg_key" "$leg_attempt_started_utc"
  printf '%s_run_dir=%s\n' "$leg_key" "$run_dir"
  printf '%s_treatment=%s\n' "$leg_key" "$treatment"
} >> "$campaign_journal"

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
export VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0
export VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE="$shared_elementwise"
export VLLM_XPU_LAGUNA_M8_QKNORM_ROPE="$qknorm_rope"
export VLLM_XPU_LAGUNA_M8_W1_N_TILE="$w1_n_tile"
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
export LAGUNA_GPU_MEMORY_UTILIZATION=0.90
export VLLM_EXTRA_ARGS=

service_start_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s_service_start_utc=%s\n' \
  "$leg_key" "$service_start_utc" >> "$campaign_journal"

{
  printf 'service_start_utc=%s\n' "$service_start_utc"
  uname -a
  git -C "$repo_root" rev-parse HEAD
  git -C "$vllm_root" rev-parse HEAD
  git -C "$kernel_root" rev-parse HEAD
  sha256sum \
    "$script_path" \
    "$nvme_paths_script" \
    "$serve_script" \
    "$compare_script" \
    "$benchmark_script" \
    "$analyzer_script" \
    "$preregistration" \
    "$formal_component" \
    "$counter_component" \
    "$oneccl_library" \
    "$libfabric_library" \
    "$repo_root/$suite_rel" \
    "$teacher" \
    "$source_model_manifest" \
    "$model_manifest" \
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
    "retained_source_model_manifest=$source_model_manifest" \
    "model_aggregate_manifest=$model_manifest" \
    "model_aggregate_manifest_sha256=$expected_model_aggregate_manifest" \
    "nvme_artifact_root=$artifact_root" \
    "nvme_model_root=$model_root" \
    'target_manifest_files=27' \
    'draft_manifest_files=5' \
    'target_manifest_bytes=71922378071' \
    'draft_manifest_bytes=2229973769' \
    'target_lfs_sha256_files=15' \
    'draft_lfs_sha256_files=1' \
    'target_lfs_bytes=71907915776' \
    'draft_lfs_bytes=2229962896' \
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
    'VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0' \
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=$shared_elementwise" \
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=$qknorm_rope" \
    "VLLM_XPU_LAGUNA_M8_W1_N_TILE=$w1_n_tile" \
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
    "preregistration=$preregistration" \
    "formal_component_gate=$formal_component" \
    "counter_component_gate=$counter_component" \
    "oneccl_library=$oneccl_library" \
    "libfabric_library=$libfabric_library" \
    "campaign_id=$campaign_id" \
    "campaign_root=$campaign_root" \
    "campaign_journal=$campaign_journal" \
    "campaign_leg=$leg_key" \
    "campaign_leg_index=$leg_index" \
    "campaign_previous_chain_sha256=$previous_chain_sha256" \
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

validate_current_leg_entries() {
  "$venv_python" - "$run_dir" <<'PY'
import sys
from pathlib import Path

directory = Path(sys.argv[1])
expected = {
    "identity.txt",
    "server.pid",
    "xpu-smi-version.txt",
    "prestart-xpu-ps.txt",
    "prestart-residual.txt",
    "server.log",
    "metrics-before-suite.prom",
    "bench.json",
    "bench.stdout",
    "metrics-after-suite.prom",
    "exactness-vs-q1.json",
    "exactness-vs-q1.stdout",
    "poststop-xpu-ps.txt",
    "poststop-residual.txt",
    "cleanup-status.txt",
}
entries = list(directory.iterdir())
actual = {path.name for path in entries}
if actual != expected:
    raise SystemExit(
        "current leg has unexpected or missing artifacts: "
        f"expected={sorted(expected)}, actual={sorted(actual)}"
    )
if not all(path.is_file() and not path.is_symlink() for path in entries):
    raise SystemExit("current leg contains a non-regular artifact")
PY
}

finalize() {
  local original_status="$1"
  local stop_status=0
  local proof_status=0
  local final_status="$original_status"
  local cleanup_completed_utc
  local evidence_manifest
  local evidence_manifest_sha256
  local phase1_chain_sha256=-
  local chain_payload
  local chain_sha256
  trap - EXIT INT TERM
  set +e
  stop_service
  stop_status=$?
  poststop_proof
  proof_status=$?
  if (( final_status == 0 && (stop_status != 0 || proof_status != 0) )); then
    final_status=6
  fi
  cleanup_completed_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  {
    printf 'original_status=%s\n' "$original_status"
    printf 'stop_status=%s\n' "$stop_status"
    printf 'poststop_proof_status=%s\n' "$proof_status"
    printf 'final_status=%s\n' "$final_status"
    printf 'cleanup_completed_utc=%s\n' "$cleanup_completed_utc"
  } > "$run_dir/cleanup-status.txt"
  if (( final_status == 0 )); then
    if ! validate_current_leg_entries; then
      final_status=6
    fi
  fi
  if (( final_status == 0 )); then
    evidence_manifest="$run_dir/leg-evidence.sha256"
    if ! sha256sum \
      "$run_dir/identity.txt" \
      "$run_dir/server.pid" \
      "$run_dir/xpu-smi-version.txt" \
      "$run_dir/prestart-xpu-ps.txt" \
      "$run_dir/prestart-residual.txt" \
      "$run_dir/server.log" \
      "$run_dir/metrics-before-suite.prom" \
      "$run_dir/bench.json" \
      "$run_dir/bench.stdout" \
      "$run_dir/metrics-after-suite.prom" \
      "$run_dir/exactness-vs-q1.json" \
      "$run_dir/exactness-vs-q1.stdout" \
      "$run_dir/poststop-xpu-ps.txt" \
      "$run_dir/poststop-residual.txt" \
      "$run_dir/cleanup-status.txt" \
      > "$evidence_manifest"; then
      final_status=6
    fi
    if (( final_status == 0 )); then
      evidence_manifest_sha256="$(
        sha256sum "$evidence_manifest" | awk '{print $1}'
      )"
      if [[ ! "$evidence_manifest_sha256" =~ ^[0-9a-f]{64}$ ]]; then
        final_status=6
      fi
    fi
    if (( final_status == 0 && leg_index >= 3 )); then
      phase1_chain_sha256="$(
        sha256sum "$phase1_analysis" | awk '{print $1}'
      )"
      if [[ ! "$phase1_chain_sha256" =~ ^[0-9a-f]{64}$ ]]; then
        final_status=6
      fi
    fi
    if (( final_status == 0 )); then
      chain_payload="$previous_chain_sha256|$leg_key|$run_dir|$treatment"
      chain_payload+="|$leg_attempt_started_utc|$service_start_utc"
      chain_payload+="|$cleanup_completed_utc|$evidence_manifest_sha256"
      chain_payload+="|$phase1_chain_sha256"
      chain_sha256="$(
        printf '%s\n' "$chain_payload" | sha256sum | awk '{print $1}'
      )"
      if [[ ! "$chain_sha256" =~ ^[0-9a-f]{64}$ ]]; then
        final_status=6
      fi
    fi
  fi
  if (( final_status != 0 )); then
    {
      printf 'original_status=%s\n' "$original_status"
      printf 'stop_status=%s\n' "$stop_status"
      printf 'poststop_proof_status=%s\n' "$proof_status"
      printf 'final_status=%s\n' "$final_status"
      printf 'cleanup_completed_utc=%s\n' "$cleanup_completed_utc"
    } > "$run_dir/cleanup-status.txt"
  fi
  {
    printf '%s_final_status=%s\n' "$leg_key" "$final_status"
    printf '%s_cleanup_completed_utc=%s\n' \
      "$leg_key" "$cleanup_completed_utc"
  } >> "$campaign_journal"
  if (( final_status == 0 )); then
    {
      printf '%s_evidence_manifest_path=%s\n' \
        "$leg_key" "$evidence_manifest"
      printf '%s_evidence_manifest_sha256=%s\n' \
        "$leg_key" "$evidence_manifest_sha256"
      printf '%s_previous_chain_sha256=%s\n' \
        "$leg_key" "$previous_chain_sha256"
      printf '%s_chain_sha256=%s\n' "$leg_key" "$chain_sha256"
    } >> "$campaign_journal"
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

mutation_request_count="$(
  grep -Ec -- '- "(POST|PUT|PATCH|DELETE) [^ ]+ HTTP/[0-9]+([.][0-9]+)?" ' \
    "$run_dir/server.log" || true
)"
successful_completion_count="$(
  grep -Fc -- '"POST /v1/chat/completions HTTP/1.1" 200 OK' \
    "$run_dir/server.log" || true
)"
if [[ "$mutation_request_count" != 13 || "$successful_completion_count" != 13 ]]; then
  echo "unexpected mutating HTTP request count or route" >&2
  exit 5
fi
if grep -E -- '- "(POST|PUT|PATCH|DELETE) [^ ]+ HTTP/[0-9]+([.][0-9]+)?" ' \
  "$run_dir/server.log" \
  | grep -Fv -- '"POST /v1/chat/completions HTTP/1.1" 200 OK' \
  | grep -q .; then
  echo "a non-benchmark mutating HTTP request reached the service" >&2
  exit 5
fi
