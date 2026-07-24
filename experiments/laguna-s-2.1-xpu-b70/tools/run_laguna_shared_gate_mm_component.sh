#!/usr/bin/bash
# Frozen launcher for one four-card component campaign.  This wrapper never
# evaluates a command string, creates an artifact, or selects a default.
set -euo pipefail
set -f
umask 022

readonly JQ=/usr/bin/jq
readonly REALPATH=/usr/bin/realpath
readonly ENV=/usr/bin/env
readonly PYTHON=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly COORDINATOR=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/orchestrate_laguna_shared_gate_mm_component.py

die() { echo "component launcher rejected: $*" >&2; exit 2; }
[[ $# -eq 6 && $1 == --authorization && $3 == --fixture && $5 == --stage0-result ]] ||
  die "usage: run_laguna_shared_gate_mm_component.sh --authorization PACKET --fixture FIXTURE --stage0-result RESULT"
readonly AUTHORIZATION=$2 FIXTURE=$4 STAGE0_RESULT=$6
readonly SCRIPT=$($REALPATH -e -- "$0")
[[ $0 == "$SCRIPT" && ! -L $0 ]] || die "launcher must be its direct absolute non-symlink path"
for path in "$AUTHORIZATION" "$FIXTURE" "$STAGE0_RESULT"; do
  [[ $path == /* && -f $path && ! -L $path ]] || die "argument is not an absolute regular non-symlink file"
done
readonly AUTHORIZATION_REAL=$($REALPATH -e -- "$AUTHORIZATION")
readonly FIXTURE_REAL=$($REALPATH -e -- "$FIXTURE")
readonly STAGE0_RESULT_REAL=$($REALPATH -e -- "$STAGE0_RESULT")
[[ $AUTHORIZATION == "$AUTHORIZATION_REAL" && $FIXTURE == "$FIXTURE_REAL" && $STAGE0_RESULT == "$STAGE0_RESULT_REAL" ]] || die "path aliases are forbidden"
case "$AUTHORIZATION_REAL:$FIXTURE_REAL:$STAGE0_RESULT_REAL" in
  *:/media/*|*:/run/media/*|*:/mnt/usb/*|/media/*|/run/media/*|/mnt/usb/*) die "external USB paths are forbidden" ;;
esac
[[ $AUTHORIZATION_REAL == /home/steve/llm-optimizations/data/* ]] || die "packet must be tracked below main data/"
readonly ARTIFACT_PREFIX=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/
[[ $FIXTURE_REAL == "$ARTIFACT_PREFIX"* && $STAGE0_RESULT_REAL == "$ARTIFACT_PREFIX"* ]] || die "evidence must be on internal NVMe"

"$JQ" -e '
  .format == "laguna-shared-gate-m8-four-card-component-authorization-v2" and
  .phase == "four_card_component" and
  (.coordinator_environment | type == "object") and
  (.coordinator_environment | to_entries | all(.[]; (.key | test("^[A-Z][A-Z0-9_]*$")) and (.value | type == "string" and (contains("\u000a") | not)))) and
  (.coordinator_argv | type == "array" and length == 8)
' "$AUTHORIZATION_REAL" >/dev/null || die "packet preflight schema rejected"
[[ $($JQ -er '.packet_path' "$AUTHORIZATION_REAL") == "$AUTHORIZATION_REAL" ]] || die "packet path drift"
[[ $($JQ -er '.stage0.fixture_path' "$AUTHORIZATION_REAL") == "$FIXTURE_REAL" ]] || die "fixture path drift"
[[ $($JQ -er '.stage0.result_path' "$AUTHORIZATION_REAL") == "$STAGE0_RESULT_REAL" ]] || die "stage-zero result path drift"

mapfile -t COORDINATOR_ARGV < <("$JQ" -er '.coordinator_argv[]' "$AUTHORIZATION_REAL")
[[ ${COORDINATOR_ARGV[0]} == "$PYTHON" && ${COORDINATOR_ARGV[1]} == "$COORDINATOR" &&
   ${COORDINATOR_ARGV[2]} == --authorization && ${COORDINATOR_ARGV[3]} == "$AUTHORIZATION_REAL" &&
   ${COORDINATOR_ARGV[4]} == --fixture && ${COORDINATOR_ARGV[5]} == "$FIXTURE_REAL" &&
   ${COORDINATOR_ARGV[6]} == --stage0-result && ${COORDINATOR_ARGV[7]} == "$STAGE0_RESULT_REAL" ]] || die "coordinator argv drift"
readonly ACTUAL_ARGV=$($JQ -cn --args '$ARGS.positional' -- "$PYTHON" "$COORDINATOR" --authorization "$AUTHORIZATION_REAL" --fixture "$FIXTURE_REAL" --stage0-result "$STAGE0_RESULT_REAL")
readonly EXPECTED_ARGV=$($JQ -c '.coordinator_argv' "$AUTHORIZATION_REAL")
[[ "$ACTUAL_ARGV" == "$EXPECTED_ARGV" ]] || die "launcher invocation differs from frozen argv"

mapfile -t ENV_NAMES < <("$JQ" -er '.coordinator_environment | keys[]' "$AUTHORIZATION_REAL")
ENVIRONMENT=()
for name in "${ENV_NAMES[@]}"; do
  value=$($JQ -er --arg name "$name" '.coordinator_environment[$name]' "$AUTHORIZATION_REAL")
  [[ $name =~ ^[A-Z][A-Z0-9_]*$ && $value != *$'\n'* ]] || die "unsafe environment entry"
  ENVIRONMENT+=("$name=$value")
done
exec "$ENV" -i "${ENVIRONMENT[@]}" "${COORDINATOR_ARGV[@]}"
