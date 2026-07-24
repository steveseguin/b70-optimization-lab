#!/usr/bin/bash
# Frozen one-shot launcher for the exactness-only Laguna shared gate+up M=8 screen.
#
# This wrapper deliberately does not create, redirect into, or log beneath the
# output root. The Python adapter acquires that fresh root with its first
# O_EXCL+fsync identity checkpoint, then treats it as terminal.

set -euo pipefail
set -f
umask 022

readonly JQ=/usr/bin/jq
readonly REALPATH=/usr/bin/realpath
readonly ENV=/usr/bin/env
readonly FIXTURE_FORMAT=laguna-shared-gate-up-m8-stage0-fixtures-v1
readonly AUTHORIZATION_FORMAT=laguna-shared-gate-up-m8-stage0-authorization-v1
readonly DISPATCH_REJECTION_COUNT=30

die() {
  echo "stage-zero runner rejected: $*" >&2
  exit 2
}

[[ $# -eq 6 ]] || die "expected exactly six arguments"
[[ $1 == --authorization && $3 == --fixture && $5 == --output-root ]] ||
  die "argument order differs from the frozen protocol"

readonly AUTHORIZATION=$2
readonly FIXTURE=$4
readonly OUTPUT_ROOT=$6
readonly SCRIPT_PATH=$("$REALPATH" -e -- "$0")

[[ $0 == "$SCRIPT_PATH" && ! -L $0 ]] ||
  die "runner must be invoked directly by its absolute non-symlink path"
[[ $AUTHORIZATION == /* && -f $AUTHORIZATION && ! -L $AUTHORIZATION ]] ||
  die "authorization is not an absolute regular non-symlink file"
[[ $FIXTURE == /* && -f $FIXTURE && ! -L $FIXTURE ]] ||
  die "fixture is not an absolute regular non-symlink file"
[[ $OUTPUT_ROOT == /* && ! -e $OUTPUT_ROOT && ! -L $OUTPUT_ROOT ]] ||
  die "output root is not a fresh absolute path"

readonly AUTHORIZATION_REAL=$("$REALPATH" -e -- "$AUTHORIZATION")
readonly FIXTURE_REAL=$("$REALPATH" -e -- "$FIXTURE")
readonly OUTPUT_ROOT_REAL=$("$REALPATH" -m -- "$OUTPUT_ROOT")
[[ $AUTHORIZATION == "$AUTHORIZATION_REAL" ]] ||
  die "authorization path contains aliases or symlinks"
[[ $FIXTURE == "$FIXTURE_REAL" ]] || die "fixture path contains aliases or symlinks"
[[ $OUTPUT_ROOT == "$OUTPUT_ROOT_REAL" ]] ||
  die "output-root path contains aliases or symlinks"

case "$AUTHORIZATION_REAL:$FIXTURE_REAL:$OUTPUT_ROOT_REAL" in
  *:/media/* | *:/run/media/* | *:/mnt/usb/* | /media/* | /run/media/* | /mnt/usb/*)
    die "removable-media paths are forbidden"
    ;;
esac
readonly ARTIFACT_PREFIX=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/
[[ $FIXTURE_REAL == "$ARTIFACT_PREFIX"* ]] ||
  die "fixture is outside the internal-NVMe artifact root"
[[ $OUTPUT_ROOT_REAL == "$ARTIFACT_PREFIX"* ]] ||
  die "output root is outside the internal-NVMe artifact root"
[[ $AUTHORIZATION_REAL == /home/steve/llm-optimizations/* ]] ||
  die "authorization is not tracked beneath the main repository"

"$JQ" -e --arg format "$AUTHORIZATION_FORMAT" \
  --argjson rejection_count "$DISPATCH_REJECTION_COUNT" '
  .format == $format and
  .phase == "stage0" and
  .adapter_state == "READY_STAGE0_EXECUTION" and
  .protocol.native_mm_order == ["gate_proj", "up_proj"] and
  (.protocol.dispatch_rejections | type == "array" and length == $rejection_count) and
  (.protocol.dispatch_rejection_counts | type == "object" and
    (keys | length) == $rejection_count) and
  ((.protocol.dispatch_rejections | sort) ==
    (.protocol.dispatch_rejection_counts | keys)) and
  (.protocol.dispatch_rejection_counts | to_entries | all(.[].value;
    . == {"mm_calls": 0, "bmm_calls": 0, "fallback_calls": 0})) and
  (.environment | type == "object") and
  (.environment | to_entries | all(.[];
    (.key | test("^[A-Z][A-Z0-9_]*$")) and
    (.value | type == "string" and (contains("\u000a") | not))
  ))
' "$AUTHORIZATION_REAL" >/dev/null || die "packet preflight schema rejected"

"$JQ" -e --arg format "$FIXTURE_FORMAT" '
  .format == $format and
  .stage == "stage0" and
  .adapter_state == "READY_STAGE0_EXECUTION"
' "$FIXTURE_REAL" >/dev/null || die "fixture preflight schema rejected"

readonly PACKET_AUTH=$("$JQ" -er '.packet_path' "$AUTHORIZATION_REAL")
readonly PACKET_FIXTURE=$("$JQ" -er '.fixture.path' "$AUTHORIZATION_REAL")
readonly PACKET_OUTPUT=$("$JQ" -er '.storage.output_root' "$AUTHORIZATION_REAL")
[[ $PACKET_AUTH == "$AUTHORIZATION_REAL" ]] ||
  die "authorization argument differs from packet"
[[ $PACKET_FIXTURE == "$FIXTURE_REAL" ]] || die "fixture argument differs from packet"
[[ $PACKET_OUTPUT == "$OUTPUT_ROOT_REAL" ]] ||
  die "output-root argument differs from packet"

readonly ACTUAL_RUNNER_ARGV=$(
  "$JQ" -cn --args '$ARGS.positional' -- \
    "$SCRIPT_PATH" \
    --authorization "$AUTHORIZATION_REAL" \
    --fixture "$FIXTURE_REAL" \
    --output-root "$OUTPUT_ROOT_REAL"
)
readonly PACKET_RUNNER_ARGV=$("$JQ" -c '.runner_argv' "$AUTHORIZATION_REAL")
[[ $ACTUAL_RUNNER_ARGV == "$PACKET_RUNNER_ARGV" ]] ||
  die "runner argv differs from frozen packet"

mapfile -t ENVIRONMENT_NAMES < <("$JQ" -er '.environment | keys[]' "$AUTHORIZATION_REAL")
ENVIRONMENT=()
for name in "${ENVIRONMENT_NAMES[@]}"; do
  value=$("$JQ" -er --arg name "$name" '.environment[$name]' "$AUTHORIZATION_REAL")
  [[ $name =~ ^[A-Z][A-Z0-9_]*$ && $value != *$'\n'* ]] ||
    die "unsafe environment entry"
  ENVIRONMENT+=("$name=$value")
done

mapfile -t ADAPTER_ARGV < <("$JQ" -er '.argv[]' "$AUTHORIZATION_REAL")
[[ ${#ADAPTER_ARGV[@]} -eq 8 ]] || die "adapter argv length drift"
[[ ${ADAPTER_ARGV[0]} == /home/steve/.venvs/deepseek-v4-xpu/bin/python ]] ||
  die "adapter Python drift"
[[ ${ADAPTER_ARGV[1]} == \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_up_mm_stage0.py ]] ||
  die "adapter path drift"
[[ ${ADAPTER_ARGV[2]} == --authorization &&
  ${ADAPTER_ARGV[3]} == "$AUTHORIZATION_REAL" &&
  ${ADAPTER_ARGV[4]} == --fixture &&
  ${ADAPTER_ARGV[5]} == "$FIXTURE_REAL" &&
  ${ADAPTER_ARGV[6]} == --result ]] || die "adapter argument structure drift"

readonly PACKET_RESULT=$("$JQ" -er '.storage.result_path' "$AUTHORIZATION_REAL")
[[ $PACKET_RESULT == "$OUTPUT_ROOT_REAL/stage0-result.json" ]] ||
  die "result path differs from fresh output root"
[[ ${ADAPTER_ARGV[7]} == "$PACKET_RESULT" ]] || die "adapter result argument drift"

# No shell redirection is permitted here: the adapter must own the run root.
exec "$ENV" -i "${ENVIRONMENT[@]}" "${ADAPTER_ARGV[@]}"
