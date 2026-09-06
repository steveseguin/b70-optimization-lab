#!/usr/bin/env bash
# Replay the lossless MTP1 record on the originating host through the lab's
# frozen packet path: verify identities, derive a fresh attempt from the frozen
# A189 packet, launch it with the host-controlled launcher (root: swap/ASPM
# reset, page-cache drop, fail-closed preflight), run the frozen client once,
# and compare the result with the record. Needs: REPRO_ATTEMPT (an unused
# attempt number > 189), optionally REPRO_PORT (default 19900).
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo="$(cd -- "$script_dir/../.." && pwd -P)"
pk="$repo/experiments/qwen38-flash-next-fp8-b70/tools"
attempt="${REPRO_ATTEMPT:?set REPRO_ATTEMPT to an unused attempt number above 189}"
port="${REPRO_PORT:-19900}"
log_dir="${REPRO_LOG_DIR:-/tmp/q38-replay-a${attempt}}"
results="${REPRO_RESULT_PARENT:-/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70}"
run_dir="$results/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-4352-ple-only-r1-attempt${attempt}"
die() { printf 'lossless MTP1 record gate: %s\n' "$*" >&2; exit 2; }
[[ "$attempt" =~ ^[1-9][0-9]*$ && "$attempt" -gt 189 ]] || die "REPRO_ATTEMPT must be a number above 189"
[[ ! -e "$run_dir" ]] || die "run directory already exists: $run_dir"
ls "$pk"/*a"${attempt}"* >/dev/null 2>&1 && die "attempt ${attempt} already has packet files in $pk"
"$script_dir/verify-identity.sh"
python3 "$script_dir/make-replay-attempt.py" "$attempt" "$port" >"${TMPDIR:-/tmp}/q38-replay-a${attempt}-packet.sha256"
printf 'derived packet a%s (port %s):\n' "$attempt" "$port"; cat "${TMPDIR:-/tmp}/q38-replay-a${attempt}-packet.sha256"
env "Q38_A${attempt}_VALIDATE_ONLY=1" bash "$pk/launch-tp4-mtp1-4352-ple-only-a${attempt}-fullgraphdet-w13n32.sh" >/dev/null || die "packet static validation failed"
driver="$(mktemp "${TMPDIR:-/tmp}/q38-replay-driver-a${attempt}.XXXX.sh")"
printf '#!/usr/bin/env bash\nexec "%s" %s %s\n' "$script_dir/wait-and-run-client.sh" "$attempt" "$port" >"$driver"; chmod +x "$driver"
mkdir -p "$log_dir"
setsid nohup bash "$pk/q38-launch-frozen-attempt.sh" "$attempt" "$driver" "$log_dir" >"$log_dir/launch.out" 2>&1 </dev/null &
sleep 20; cat "$log_dir/launch.out"
grep -q '^FAIL' "$log_dir/launch.out" && die "launch preflight failed; see $log_dir/launch.out"
rc_file="/tmp/q38-mtp1-ple-only-a${attempt}.rc"
printf 'waiting for %s (load ~10 min, capture ~2 min, suite ~10 min)\n' "$rc_file"
for _ in $(seq 1 360); do [[ -f "$rc_file" ]] && break; sleep 15; done
[[ -f "$rc_file" ]] || die "no completion after 90 minutes; see $log_dir"
printf 'server lifecycle rc=%s\n' "$(cat "$rc_file")"
[[ -f "$run_dir/realistic-suite-v1-result.json" ]] || die "no realistic-suite-v1-result.json in $run_dir; see $log_dir/a${attempt}-driver.log"
python3 "$script_dir/check-replay-result.py" "$run_dir/realistic-suite-v1-result.json"
