#!/usr/bin/env bash
set -euo pipefail
umask 077

root="/home/steve/llm-optimizations"
scripts="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts"
quality="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/quality"
model="deepseek-v4-flash-0731-reap-k160"
revision="ddc04540efda3d2a0788b129f1fad828ddc19b60"
base_url="${BASE_URL:-http://127.0.0.1:18080}"
run_dir="${RUN_DIR:?set RUN_DIR to the active 0731 server run directory}"
validation_summary="${DEEPSEEK_0731_VALIDATION_SUMMARY:?set DEEPSEEK_0731_VALIDATION_SUMMARY}"
binding_verifier="${scripts}/verify-0731-endpoint-binding.py"
mode="${1:-smoke}"

case "${mode}" in
  smoke|full) ;;
  *) printf 'usage: %s smoke|full\n' "$0" >&2; exit 2 ;;
esac

identity="${run_dir}/identity.txt"
[[ "${run_dir}" == /* ]] || {
  printf 'RUN_DIR must be absolute: %s\n' "${run_dir}" >&2
  exit 2
}
test -d "${run_dir}"
test ! -L "${run_dir}"
test "$(realpath -e -- "${run_dir}")" = "${run_dir}"
test -f "${identity}"
test ! -L "${identity}"
test -f "${validation_summary}"
test ! -L "${validation_summary}"
test -f "${binding_verifier}"

export NO_PROXY=127.0.0.1
export no_proxy=127.0.0.1
exec {qualification_lock_fd}>"${run_dir}/.qualification.lock"
flock --nonblock "${qualification_lock_fd}" || {
  printf 'another qualification is active for %s\n' "${run_dir}" >&2
  exit 2
}

attempt_root="${run_dir}/qualification-attempts"
if [[ -e "${attempt_root}" ]]; then
  test -d "${attempt_root}"
  test ! -L "${attempt_root}"
else
  mkdir "${attempt_root}"
fi
attempt_dir="$(mktemp -d "${attempt_root}/${mode}-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
test -d "${attempt_dir}"
test ! -L "${attempt_dir}"

binding_index=0
binding_baseline=""
check_binding() {
  local label="$1"
  local output
  output="$(printf '%s/binding-%02d-%s.json' "${attempt_dir}" "${binding_index}" "${label}")"
  binding_index=$((binding_index + 1))
  local args=(
    --identity "${identity}"
    --base-url "${base_url}"
    --validation-summary "${validation_summary}"
    --mode "${mode}"
    --out "${output}"
  )
  if [[ -n "${binding_baseline}" ]]; then
    args+=(--baseline "${binding_baseline}")
  fi
  python3 "${binding_verifier}" "${args[@]}" >/dev/null
  if [[ -z "${binding_baseline}" ]]; then
    binding_baseline="${output}"
  fi
}

check_binding before-endpoint-query

curl --fail --silent --show-error --noproxy '*' "${base_url}/v1/models" \
  >"${attempt_dir}/endpoint-models.json"
jq -e --arg model "${model}" \
  '.data | any(.id == $model)' "${attempt_dir}/endpoint-models.json" >/dev/null
check_binding after-endpoint-query

capture_exact() {
  local label="$1"
  local output="$2"
  local score="$3"
  python3 "${scripts}/capture-openai-logprob-corpus.py" \
    --base-url "${base_url}" \
    --model "${model}" \
    --model-revision "${revision}" \
    --suite "${quality}/exact-canaries-v1.json" \
    --out "${output}" \
    --max-tokens 32 \
    --top-logprobs 0 \
    --seed 1 \
    --label "${label}"
  python3 "${scripts}/score-exact-canaries.py" \
    "${output}" \
    --suite "${quality}/exact-canaries-v1.json" \
    --strict-contract "${quality}/exact-canaries-0731-target-contract-v1.json" \
    --out "${score}"
}

capture_exact \
  "0731-target-${mode}-pre" \
  "${attempt_dir}/exact-canaries-pre.json" \
  "${attempt_dir}/exact-canaries-pre-score.json"
check_binding after-exact-pre

if [[ "${mode}" == "smoke" ]]; then
  python3 - "${attempt_dir}" "${identity}" "${model}" "${revision}" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

attempt = Path(sys.argv[1])
identity = Path(sys.argv[2])

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

bindings = sorted(attempt.glob("binding-*.json"))
if len(bindings) != 3:
    raise SystemExit(f"expected 3 binding reports, found {len(bindings)}")
loaded = [json.loads(path.read_text(encoding="utf-8")) for path in bindings]
stable = (
    "identity_sha256", "validation_summary_sha256", "launcher_pid",
    "process_start_ticks", "host_boot_id", "listener_host", "listener_port",
    "listener_socket_inodes", "listener_owner_pids",
)
for field in stable:
    if len({json.dumps(row.get(field), sort_keys=True) for row in loaded}) != 1:
        raise SystemExit(f"binding continuity failed for {field}")
identity_digest = digest(identity)
if identity_digest != loaded[0].get("identity_sha256"):
    raise SystemExit("identity changed after the final binding check")
validation_path = Path(loaded[0]["validation_summary"])
if digest(validation_path) != loaded[0].get("validation_summary_sha256"):
    raise SystemExit("validation receipt changed after the final binding check")
result = {
    "schema": "deepseek-v4-0731-target-qualification-v1",
    "status": "pass",
    "qualification_scope": "endpoint-binding-and-exact-smoke",
    "overall_model_quality": "not_evaluated_in_smoke_mode",
    "mode": "smoke",
    "model": sys.argv[3],
    "revision": sys.argv[4],
    "identity_sha256": identity_digest,
    "exact_pre_score_sha256": digest(attempt / "exact-canaries-pre-score.json"),
    "sha256": {
        name: digest(attempt / name)
        for name in (
            "endpoint-models.json",
            "exact-canaries-pre.json",
            "exact-canaries-pre-score.json",
        )
    },
    "binding_sha256": {path.name: digest(path) for path in bindings},
}
output = attempt / "target-qualification-summary.json"
if output.exists() or output.is_symlink():
    raise SystemExit(f"refusing to overwrite {output}")
fd, temporary = tempfile.mkstemp(prefix=".target-summary.", dir=attempt)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
try:
    os.link(temporary, output)
finally:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
directory = os.open(attempt, os.O_RDONLY)
try:
    os.fsync(directory)
finally:
    os.close(directory)
PY
  printf 'qualification_attempt=%s\n' "${attempt_dir}"
  exit 0
fi

python3 "${scripts}/capture-openai-logprob-corpus.py" \
  --base-url "${base_url}" \
  --model "${model}" \
  --model-revision "${revision}" \
  --suite "${quality}/suite-v1.json" \
  --out "${attempt_dir}/quality-continuity.json" \
  --max-tokens 1024 \
  --top-logprobs 0 \
  --seed 1776 \
  --label 0731-target-quality-continuity
python3 "${scripts}/score-quality-capture.py" \
  "${attempt_dir}/quality-continuity.json" \
  --promotion \
  --suite "${quality}/suite-v1.json" \
  --expected-model "${model}" \
  --expected-model-revision "${revision}" \
  --out "${attempt_dir}/quality-continuity-score.json"
check_binding after-quality

python3 "${root}/scripts/bench-openai-realistic-suite.py" \
  --base-url "${base_url}" \
  --model "${model}" \
  --suite "${root}/repro/rapid-model-snapshots-b70/realistic-suite-v1.json" \
  --max-tokens 512 \
  --metric-tokens 100 \
  --seed 1 \
  --return-token-ids \
  --out "${attempt_dir}/realistic-suite.json"
jq -e '.realistic_final_gate.passed == true' \
  "${attempt_dir}/realistic-suite.json" >/dev/null
check_binding after-realistic-suite

capture_exact \
  0731-target-full-post \
  "${attempt_dir}/exact-canaries-post.json" \
  "${attempt_dir}/exact-canaries-post-score.json"
check_binding after-exact-post

python3 - "${attempt_dir}" "${identity}" "${model}" "${revision}" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

run = Path(sys.argv[1])
identity = Path(sys.argv[2])
model = sys.argv[3]
revision = sys.argv[4]


def load(name: str):
    return json.loads((run / name).read_text(encoding="utf-8"))


def digest(name: str) -> str:
    return hashlib.sha256((run / name).read_bytes()).hexdigest()


exact_pre = load("exact-canaries-pre-score.json")
exact_post = load("exact-canaries-post-score.json")
quality = load("quality-continuity-score.json")
realistic = load("realistic-suite.json")
bindings = sorted(run.glob("binding-*.json"))
if len(bindings) != 6:
    raise SystemExit(f"expected 6 binding reports, found {len(bindings)}")
loaded_bindings = [json.loads(path.read_text(encoding="utf-8")) for path in bindings]
stable = (
    "identity_sha256", "validation_summary_sha256", "launcher_pid",
    "process_start_ticks", "host_boot_id", "listener_host", "listener_port",
    "listener_socket_inodes", "listener_owner_pids",
)
for field in stable:
    if len({json.dumps(row.get(field), sort_keys=True) for row in loaded_bindings}) != 1:
        raise SystemExit(f"binding continuity failed for {field}")
identity_digest = hashlib.sha256(identity.read_bytes()).hexdigest()
if identity_digest != loaded_bindings[0].get("identity_sha256"):
    raise SystemExit("identity changed after the final binding check")
validation_path = Path(loaded_bindings[0]["validation_summary"])
if hashlib.sha256(validation_path.read_bytes()).hexdigest() != loaded_bindings[0].get(
    "validation_summary_sha256"
):
    raise SystemExit("validation receipt changed after the final binding check")
result = {
    "schema": "deepseek-v4-0731-target-qualification-v1",
    "status": "pass",
    "qualification_scope": "automated-endpoint-and-executable-quality-gates",
    "overall_model_quality": (
        "pending_manual_rubrics"
        if quality.get("manual_rubrics_pending")
        else "automated_gates_passed"
    ),
    "mode": "full",
    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    "model": model,
    "revision": revision,
    "gates": {
        "exact_pre": exact_pre.get("passed") is True,
        "quality_executable_and_corruption": quality.get("promotion_gates_passed") is True,
        "realistic_fresh_response": realistic.get("realistic_final_gate", {}).get("passed") is True,
        "exact_post": exact_post.get("passed") is True,
    },
    "quality_manual_rubrics_pending": quality.get("manual_rubrics_pending"),
    "performance": realistic.get("summary"),
    "sha256": {
        name: identity_digest
        if name == "identity.txt"
        else digest(name)
        for name in (
            "identity.txt",
            "endpoint-models.json",
            "exact-canaries-pre.json",
            "exact-canaries-pre-score.json",
            "quality-continuity.json",
            "quality-continuity-score.json",
            "realistic-suite.json",
            "exact-canaries-post.json",
            "exact-canaries-post-score.json",
        )
    },
    "binding_sha256": {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(run.glob("binding-*.json"))
    },
}
if not all(result["gates"].values()):
    raise SystemExit(f"qualification gate unexpectedly false: {result['gates']}")
output = run / "target-qualification-summary.json"
if output.exists() or output.is_symlink():
    raise SystemExit(f"refusing to overwrite {output}")
temporary = run / f".{output.name}.{os.getpid()}.tmp"
with temporary.open("x", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
try:
    os.link(temporary, output)
finally:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
directory = os.open(run, os.O_RDONLY)
try:
    os.fsync(directory)
finally:
    os.close(directory)
PY
printf 'qualification_attempt=%s\n' "${attempt_dir}"
