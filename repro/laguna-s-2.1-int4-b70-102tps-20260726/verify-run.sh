#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
readonly comparator="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py"
readonly oracle="$script_dir/teacher-token-oracle-v1.json"
readonly text_oracle="$script_dir/teacher-text-sha256-v1.json"
readonly runtime_lock="$script_dir/manifests/runtime-lock.json"
readonly minimum_conventional_tok_s=96.84463517816175

die() {
  printf 'Laguna reproduction validation: %s\n' "$*" >&2
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

[[ $# == 1 ]] || die "usage: verify-run.sh RUN_DIR"
run_dir="$(realpath -e -- "$1")"
[[ -d "$run_dir" ]] || die "not a run directory: $run_dir"

for file in \
  bench.json exactness-vs-q1.json identity.txt server.log status.txt \
  cleanup-status.txt service-environment.txt pre-idle.json post-idle.json \
  runtime-verification.json idle-interval/summary.txt; do
  [[ -r "$run_dir/$file" ]] || die "missing or unreadable $file"
done

check_hash "$comparator" c18b6f37aa0f5a848a9d771fa91de14bab115b41557b9d7066bce5984c2a6945
check_hash "$oracle" a2be70c2c603ceaaf5de4558ef80c6063e54a38af604623463a0bcbc22e3cdeb
check_hash "$text_oracle" 3b669ddc389a08c75b7812b5af2394032476019fae04b9de83e51f520db0cf72
check_hash "$runtime_lock" 8c861e5c9d44232346770e2822aa795179f8f90c2678d2ebbb42a690ef4f4a97

[[ "$(wc -l < "$run_dir/status.txt")" == 1 ]] \
  || die "status.txt must contain exactly one line"
grep -Fx 'status=PASS' "$run_dir/status.txt" >/dev/null \
  || die "run status is not PASS"

python3 - "$run_dir/identity.txt" "$run_dir/runtime-verification.json" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

identity_path = Path(sys.argv[1])
runtime_path = Path(sys.argv[2])
values = {}
for line_number, line in enumerate(
    identity_path.read_text(encoding="utf-8").splitlines(), 1
):
    if "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key in values:
        raise SystemExit(f"duplicate identity key at line {line_number}: {key}")
    values[key] = value

expected = {
    "schema": "laguna-mwide-measurement-leg-v2",
    "label": "B2",
    "treatment": "candidate",
    "exact_max_m": "12",
    "num_speculative_tokens": "11",
    "prebuilt_exact_attn_metadata": "1",
    "draft_breakable_graph": "0",
    "local_argmax": "0",
    "capture_attention_graphs": "0",
    "inline_attention_graphs": "0",
    "width12_router_workspace_stack": "1",
    "mwide_bf16_router_topk": "1",
    "dflash_context_kv_workspace": "1",
    "dflash_fp8_w8a16": "1",
    "dflash_fp8_target_unchanged": "true",
    "m8_shared_elementwise": "0",
    "m8_qknorm_rope": "0",
    "gpu_memory_utilization": "0.90",
    "identity_source": "actual_worktree_heads",
    "measurement_leg_not_record_leg": "true",
    "vllm_commit": "e596ef1543466ae1a05e5bb8091f58872e2b18ba",
    "kernel_commit": "6f9dd3c3a7b1b677a992ca4f431a968408f9c816",
    "model_manifest_sha256": "45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac",
    "model_release_manifest_sha256": "c19edb79458a24ceb4bb26c991302de71ef29be40e70124e90bf6c13538c692e",
    "runtime_lock_sha256": "8c861e5c9d44232346770e2822aa795179f8f90c2678d2ebbb42a690ef4f4a97",
    "runtime_verifier_sha256": "e43f3c9f46e299eeaa8d7bbc828fadeec2ae60f69f39529f7130f154d158f20d",
    "xpumem_module_sha256": "8981f5e312cfab901a5bfa8e40a5a1f194e65db3a207784bfa602e5901e5a1a8",
    "shared_native_module_sha256": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "xpu_native_module_sha256": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "moe_native_module_sha256": "00fd81608f057039d31e1b316fecbecec60b3b03151e66b95d0f844185119715",
    "grouped_gemm_native_module_sha256": "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96",
    "fa2_binary_sha256": "3390a3065de25e06dbe95a8fbc2c8456c3489a2295816782e90a4086aedc9dd4",
    "attn_library_sha256": "ad0eb26f3b0680fcd54a50de821e9c881524d50ad5361b872f88cb0b333b65ca",
    "grouped_gemm_default_sha256": "982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c",
    "gdn_attn_library_sha256": "cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb",
    "mqa_logits_library_sha256": "58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb",
    "mhc_library_sha256": "f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f",
    "suite_sha256": "9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638",
    "teacher_sha256": "a2be70c2c603ceaaf5de4558ef80c6063e54a38af604623463a0bcbc22e3cdeb",
    "teacher_text_oracle_sha256": "3b669ddc389a08c75b7812b5af2394032476019fae04b9de83e51f520db0cf72",
    "selector_stack": "exact-m12-dflash11-breakablegraph-w1routew2-routeinterleave-n64-routerworkspace1-draftfp81",
    "metadata_selector": "1",
    "attention_capture_selector": "0",
    "inline_attention_selector": "0",
    "expected_num_graphs": "146",
    "expected_num_eager_breaks": "145",
    "no_warmup": "true",
    "suite_invocations": "1",
    "retries": "0",
    "verified_idle_interval_seconds": "60",
}
for key, wanted in expected.items():
    actual = values.get(key)
    if actual != wanted:
        raise SystemExit(
            f"identity mismatch for {key}: expected {wanted!r}, got {actual!r}"
        )

runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
if runtime.get("schema") != "laguna-s-2.1-runtime-verification-v1":
    raise SystemExit("runtime verification schema mismatch")
if runtime.get("status") != "PASS":
    raise SystemExit("runtime verification did not pass")
actual_runtime_hash = hashlib.sha256(runtime_path.read_bytes()).hexdigest()
if values.get("runtime_verification_sha256") != actual_runtime_hash:
    raise SystemExit("runtime verification JSON hash differs from identity")
PY

[[ "$(wc -l < "$run_dir/cleanup-status.txt")" == 4 ]] \
  || die "cleanup-status.txt must contain exactly four lines"
for expected in \
  original_status=0 stop_status=0 worker_status=0 idle_status=0; do
  grep -Fx "$expected" "$run_dir/cleanup-status.txt" >/dev/null \
    || die "cleanup status is missing $expected"
done

python3 - "$run_dir/service-environment.txt" <<'PY'
import sys
from pathlib import Path

values = {}
for line_number, line in enumerate(
    Path(sys.argv[1]).read_text(encoding="utf-8").splitlines(), 1
):
    if "=" not in line:
        raise SystemExit(f"malformed environment line {line_number}")
    key, value = line.split("=", 1)
    if key in values:
        raise SystemExit(f"duplicate environment key: {key}")
    values[key] = value

expected = {
    "CCL_ATL_TRANSPORT": "ofi",
    "CCL_TOPO_P2P_ACCESS": "1",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "11",
    "LAGUNA_GPU_UTIL": "0.90",
    "LAGUNA_LOCAL_ARGMAX": "false",
    "LAGUNA_M": "12",
    "LAGUNA_SPEC": "11",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
    "ZE_AFFINITY_MASK": "0,1,2,3",
    "VLLM_KV_CACHE_LAYOUT": "NHD",
    "VLLM_USE_AOT_COMPILE": "0",
    "VLLM_USE_BREAKABLE_CUDAGRAPH": "1",
    "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
    "VLLM_XPU_EXACT_SPEC_ATTN": "1",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE": "1",
    "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16": "1",
    "VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH": "0",
    "VLLM_XPU_LAGUNA_EXACT_MAX_M": "12",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "1",
    "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1",
    "VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS": "0",
    "VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS": "0",
    "VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA": "1",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "0",
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "0",
    "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK": "1",
    "XPU_GRAPH": "1",
}
for key, wanted in expected.items():
    actual = values.get(key)
    if actual != wanted:
        raise SystemExit(
            f"service environment mismatch for {key}: "
            f"expected {wanted!r}, got {actual!r}"
        )
if values.get("CCL_KVS_IFACE") != values.get("FI_TCP_IFACE"):
    raise SystemExit("oneCCL/libfabric interface values differ")
ld_path = values.get("LD_LIBRARY_PATH", "")
if not ld_path.split(":", 1)[0].endswith("/vllm_xpu_kernels"):
    raise SystemExit("pinned kernel package is not first in LD_LIBRARY_PATH")
PY

for idle in "$run_dir/pre-idle.json" "$run_dir/post-idle.json"; do
  jq -e '
    .status == "passed"
    and .idle.device_ids == [0,1,2,3]
    and .xpu_smi.sha256
      == "2b5b128edf28b38da8637413fe8bfe3a4a40e8113210ba9ddaed945bd56d826e"
  ' "$idle" >/dev/null || die "idle evidence failed: $idle"
done
python3 - "$run_dir/idle-interval/summary.txt" <<'PY'
import re
import sys
from pathlib import Path

rows = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
if len(rows) != 2:
    raise SystemExit(f"idle summary must have two lines, got {len(rows)}")
pattern = re.compile(r"^(prestart|poststop) elapsed_seconds=(\d+) snapshots=13$")
observed = {}
for row in rows:
    match = pattern.fullmatch(row)
    if not match:
        raise SystemExit(f"malformed idle summary: {row!r}")
    observed[match.group(1)] = int(match.group(2))
if set(observed) != {"prestart", "poststop"}:
    raise SystemExit(f"idle phases differ: {sorted(observed)}")
if any(seconds < 60 for seconds in observed.values()):
    raise SystemExit(f"idle interval shorter than 60 seconds: {observed}")
PY

python3 "$comparator" \
  --teacher "$oracle" \
  --teacher-text-oracle "$text_oracle" \
  --require-text-hash \
  --candidate "$run_dir/bench.json" \
  --out /dev/null >/dev/null \
  || die "candidate differs from the compact token/text oracles"

jq -e '
  .fresh_response_validity.valid == true
  and .fresh_response_validity.each_prompt_run_once == true
  and .fresh_response_validity.cached_tokens_all_zero == true
  and .fresh_response_validity.history_acceleration == false
  and .fresh_response_validity.response_reuse == false
  and .fresh_response_validity.context_checkpoints_or_prefix_reuse == false
  and .realistic_final_gate.passed == true
  and .run_identity.prompt_count == 13
  and .run_identity.max_tokens == 512
  and .run_identity.seed == 1
  and .summary.tok_s_1_100_after_ttft.count == 13
  and .summary.tok_s_1_100_intervals_after_ttft.count == 13
' "$run_dir/bench.json" >/dev/null || die "fresh-response or metric gate failed"

python3 - "$run_dir/server.log" <<'PY'
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
rank_pattern = re.compile(r"Worker_TP([0-3])_EP([0-3])")
expected_ranks = {(0, 0), (1, 1), (2, 2), (3, 3)}
for label, marker in (
    ("capture", "Captured audited breakable cudagraph"),
    ("replay", "Replayed audited breakable cudagraph"),
):
    rows = [line for line in lines if marker in line]
    ranks = {
        tuple(map(int, match.groups()))
        for line in rows
        if (match := rank_pattern.search(line))
    }
    if len(rows) != 4 or ranks != expected_ranks:
        raise SystemExit(
            f"{label} evidence mismatch: rows={len(rows)} ranks={sorted(ranks)}"
        )
    if any("(graphs=146, eager_breaks=145)" not in line for line in rows):
        raise SystemExit(f"{label} topology is not 146/145")

fp8_marker = "Prepared Laguna DFlash FP8 W8A16 draft projections: count=31"
fp8_rows = [line for line in lines if fp8_marker in line]
fp8_ranks = {
    tuple(map(int, match.groups()))
    for line in fp8_rows
    if (match := rank_pattern.search(line))
}
if len(fp8_rows) != 4 or fp8_ranks != expected_ranks:
    raise SystemExit(
        f"draft FP8 evidence mismatch: rows={len(fp8_rows)} "
        f"ranks={sorted(fp8_ranks)}"
    )
PY

python3 - "$run_dir/bench.json" "$minimum_conventional_tok_s" <<'PY'
import json
import math
import statistics
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
minimum = float(sys.argv[2])
legacy = []
conventional = []
for index, row in enumerate(data["rows"]):
    offsets = row["token_id_offsets_s"]
    if len(offsets) < 100:
        raise SystemExit(f"row {index} has fewer than 100 token timestamps")
    span = float(offsets[99]) - float(offsets[0])
    if span <= 0:
        raise SystemExit(f"row {index} has a nonpositive metric span")
    legacy.append(100.0 / span)
    conventional.append(99.0 / span)

published = statistics.median(legacy)
corrected = statistics.median(conventional)
summary = data["summary"]
checks = (
    (summary["tok_s_1_100_after_ttft"]["median"], published, "legacy summary"),
    (
        summary["tok_s_1_100_intervals_after_ttft"]["median"],
        corrected,
        "interval summary",
    ),
)
for actual, expected, label in checks:
    if not math.isclose(float(actual), expected, rel_tol=0, abs_tol=1e-12):
        raise SystemExit(f"{label} mismatch: {actual!r} != {expected!r}")
if corrected < minimum:
    raise SystemExit(
        f"semantic gates passed but conventional throughput {corrected:.14f} "
        f"is below the explicit reproduction floor {minimum:.14f}"
    )
print(f"published_legacy_tok_s={published:.14f}")
print(f"conventional_interval_tok_s={corrected:.14f}")
print(f"performance_floor_conventional_tok_s={minimum:.14f}")
PY

printf 'semantic_reproduction=PASS\n'
printf 'performance_reproduction=PASS\n'
printf 'reproduction_validation=PASS\n'
