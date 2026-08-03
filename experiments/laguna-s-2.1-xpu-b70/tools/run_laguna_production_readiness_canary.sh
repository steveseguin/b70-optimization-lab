#!/usr/bin/env bash
# Production-only Laguna readiness gate. This deliberately stays outside every
# cold benchmark launcher: it pays first-live graph/JIT cost before a frontdoor
# may advertise the backend as ready, and it never emits a benchmark score.
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"

run_dir="${1:?usage: run_laguna_production_readiness_canary.sh RUN_DIR SERVER_LOG EXPECTED_DSO EXPECTED_DSO_SHA256 TEACHER}"
server_log="${2:?usage: run_laguna_production_readiness_canary.sh RUN_DIR SERVER_LOG EXPECTED_DSO EXPECTED_DSO_SHA256 TEACHER}"
expected_dso="${3:?usage: run_laguna_production_readiness_canary.sh RUN_DIR SERVER_LOG EXPECTED_DSO EXPECTED_DSO_SHA256 TEACHER}"
expected_dso_sha256="${4:?usage: run_laguna_production_readiness_canary.sh RUN_DIR SERVER_LOG EXPECTED_DSO EXPECTED_DSO_SHA256 TEACHER}"
teacher="${5:?usage: run_laguna_production_readiness_canary.sh RUN_DIR SERVER_LOG EXPECTED_DSO EXPECTED_DSO_SHA256 TEACHER}"

readonly base_url="${LAGUNA_PRODUCTION_BASE_URL:-http://127.0.0.1:18080}"
readonly model="${LAGUNA_PRODUCTION_MODEL:-laguna-s-2.1-int4}"
readonly timeout_s="${LAGUNA_PRODUCTION_READINESS_TIMEOUT:-900}"
readonly venv_python="${REPRO_VENV_ROOT:-/home/steve/.venvs/deepseek-v4-xpu}/bin/python"
readonly suite="$repo_root/experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
readonly benchmark="$repo_root/scripts/bench-openai-realistic-suite.py"
readonly smoke="$script_dir/run_laguna_dflash_segmented_smoke.py"
readonly worker_validator="$script_dir/validate_laguna_worker_selector_evidence.py"
readonly ready_file="$run_dir/production-ready.json"
readonly pending_file="$run_dir/.production-ready.pending"

die() { echo "Laguna production readiness: $*" >&2; exit 2; }

[[ "${LAGUNA_PRODUCTION_READINESS_CANARY:-0}" == 1 ]] \
  || die "LAGUNA_PRODUCTION_READINESS_CANARY=1 is required"
[[ "$run_dir" == /* && "$server_log" == /* && "$expected_dso" == /* \
   && "$teacher" == /* ]] || die "all artifact paths must be absolute"
[[ "$expected_dso_sha256" =~ ^[0-9a-f]{64}$ ]] \
  || die "EXPECTED_DSO_SHA256 must be 64 lowercase hexadecimal characters"
[[ "$timeout_s" =~ ^[0-9]+$ && "$timeout_s" -ge 1 ]] \
  || die "LAGUNA_PRODUCTION_READINESS_TIMEOUT must be a positive integer"
case "${LAGUNA_PRODUCTION_READINESS_VALIDATE_ONLY:-0}" in
  0) ;;
  1) printf 'argument_validation=PASS\n'; exit 0 ;;
  *) die "LAGUNA_PRODUCTION_READINESS_VALIDATE_ONLY must be 0 or 1" ;;
esac

[[ -d "$run_dir" && ! -L "$run_dir" ]] || die "RUN_DIR must be an existing directory"
[[ -f "$server_log" && ! -L "$server_log" ]] || die "SERVER_LOG must be a regular file"
for path in "$expected_dso" "$teacher" "$suite" "$benchmark" "$smoke" \
  "$worker_validator" "$venv_python"; do
  [[ -f "$path" && ! -L "$path" ]] || die "missing or linked required file: $path"
done
[[ ! -e "$ready_file" && ! -L "$ready_file" ]] \
  || die "refusing to replace an existing readiness marker"
[[ ! -e "$pending_file" && ! -L "$pending_file" ]] \
  || die "refusing a stale pending readiness marker"
[[ "$(sha256sum -- "$expected_dso" | awk '{print $1}')" == "$expected_dso_sha256" ]] \
  || die "grouped-GEMM DSO hash mismatch"

cleanup_pending() { rm -f -- "$pending_file"; }
trap cleanup_pending EXIT

deadline=$((SECONDS + timeout_s))
until curl --fail --silent --show-error --max-time 5 "$base_url/health" >/dev/null; do
  (( SECONDS < deadline )) || die "backend did not become healthy before timeout"
  sleep 1
done

"$venv_python" "$worker_validator" \
  --server-log "$server_log" \
  --selector-output "$run_dir/production-worker-selectors.jsonl" \
  --map-output "$run_dir/production-worker-maps.jsonl" \
  --expected-dso "$expected_dso" \
  --expected-dso-sha256 "$expected_dso_sha256" \
  --require-exact-prefill

"$venv_python" "$smoke" \
  --base-url "$base_url" \
  --model "$model" \
  --suite "$suite" \
  --teacher "$teacher" \
  --benchmark-helper "$benchmark" \
  --server-log "$server_log" \
  --out "$run_dir/production-readiness-canary.json" \
  --replicated-embedding 0 \
  --target-graphs 146 \
  --target-eager-breaks 145 \
  --draft-graphs 14 \
  --draft-eager-breaks 13 \
  --request-count 1 \
  --max-tokens 400

{
  printf '{\n'
  printf '  "schema": "laguna-production-readiness-v1",\n'
  printf '  "status": "READY",\n'
  printf '  "scored_measurement": false,\n'
  printf '  "production_canary": true,\n'
  printf '  "prefix_caching": false,\n'
  printf '  "exact_prefill_worker_attested": true,\n'
  printf '  "request_count": 1,\n'
  printf '  "max_tokens": 400,\n'
  printf '  "created_at_utc": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '  "canary_sha256": "%s",\n' \
    "$(sha256sum -- "$run_dir/production-readiness-canary.json" | awk '{print $1}')"
  printf '  "worker_selectors_sha256": "%s",\n' \
    "$(sha256sum -- "$run_dir/production-worker-selectors.jsonl" | awk '{print $1}')"
  printf '  "worker_maps_sha256": "%s"\n' \
    "$(sha256sum -- "$run_dir/production-worker-maps.jsonl" | awk '{print $1}')"
  printf '}\n'
} > "$pending_file"
mv -- "$pending_file" "$ready_file"
trap - EXIT
printf 'Laguna production readiness: READY marker=%s\n' "$ready_file"
