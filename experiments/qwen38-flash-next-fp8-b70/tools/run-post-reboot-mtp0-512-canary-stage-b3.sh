#!/usr/bin/env bash
set -Eeuo pipefail

root=/home/steve/llm-optimizations
lane="${root}/experiments/qwen38-flash-next-fp8-b70"
source_supervisor="${lane}/tools/supervise-post-reset-mtp0-512-canary.sh"
source_client="${lane}/tools/run-post-reset-mtp0-512-canary.sh"
stage_a=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reboot-recovery-qualification-20260828-stage-a3
stage_b=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reboot-recovery-qualification-20260828-stage-b3
controller="${stage_b}/controller"
state=/tmp/q38-post-reboot-mtp0-512-supervisor-stage-b3
run_dir="${stage_b}/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1-attempt29"
port=19667
supervisor_pid=""
temporary=""

write_atomic() {
  local path=$1 value=$2 tmp
  tmp="${path}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}

cleanup() {
  local rc=$?
  set +e
  if [[ "$supervisor_pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$supervisor_pid" 2>/dev/null; then
    kill -TERM "$supervisor_pid" 2>/dev/null || true
    for _ in $(seq 1 60); do
      kill -0 "$supervisor_pid" 2>/dev/null || break
      sleep 1
    done
  fi
  [[ -z "$temporary" ]] || rm -f -- "${temporary}/supervisor.sh" "${temporary}/client.sh"
  [[ -z "$temporary" ]] || rmdir -- "$temporary" 2>/dev/null || true
  if [[ -d "$controller" ]]; then
    write_atomic "${controller}/orchestrator.rc" "$rc"
    find "$controller" -maxdepth 1 -type f ! -name evidence.sha256 -printf '%f\0' \
      | sort -z | xargs -0 -r -I{} sha256sum "${controller}/{}" \
      >"${controller}/evidence.sha256"
  fi
  if [[ -d "$stage_b" ]]; then
    find "$stage_b" -type f ! -name stage-b3-evidence.sha256 -printf '%P\0' \
      | sort -z | xargs -0 -r -I{} sha256sum "${stage_b}/{}" \
      >"${stage_b}/stage-b3-evidence.sha256"
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

[[ $# == 0 ]] || { printf 'FAIL: Stage B3 takes no arguments\n' >&2; exit 2; }
[[ "$(hostname)" == steve-b70s ]] || { printf 'FAIL: measuring host required\n' >&2; exit 1; }
[[ ! -e "$stage_b" ]] || { printf 'FAIL: refusing to reuse %s\n' "$stage_b" >&2; exit 1; }
[[ "$(sha256sum "$source_supervisor" | cut -d' ' -f1)" == 2b2a172a94fc23d910e99ea7bbf73200aeb59ee902176e660cb9c1e8fcfe28c4 ]] || {
  printf 'FAIL: reviewed supervisor source changed\n' >&2; exit 1;
}
[[ "$(sha256sum "$source_client" | cut -d' ' -f1)" == 5790945842fd3a6c6c7e599df7fbbc6b69b1de40d46d9848ed53939508410f6e ]] || {
  printf 'FAIL: reviewed canary client source changed\n' >&2; exit 1;
}
[[ "$(cat "${stage_a}/command.rc")" == 0 ]] || { printf 'FAIL: Stage A3 did not pass\n' >&2; exit 1; }
grep -Fxq 'PASS post-reboot source storage per-card peer XCCL and journal gates' \
  "${stage_a}/gates-passed.txt" || { printf 'FAIL: Stage A3 pass marker absent\n' >&2; exit 1; }
(cd "$stage_a" && sha256sum -c evidence.sha256 >/dev/null) || {
  printf 'FAIL: Stage A3 evidence does not verify\n' >&2; exit 1;
}
cd "$root"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || {
  printf 'FAIL: clean main required\n' >&2; exit 1;
}
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || {
  printf 'FAIL: local main must equal origin/main\n' >&2; exit 1;
}
for path in "${state}.pid" "${state}.child.pid" "${state}.launcher.pid" \
  "${state}.server.pid" "${state}.server.pgid" "${state}.rc" "${state}.log" \
  "${state}.stop"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: stale Stage B3 state %s\n' "$path" >&2; exit 1; }
done
! ss -ltn 2>/dev/null | grep -q ":${port} " || { printf 'FAIL: port is occupied\n' >&2; exit 1; }

mkdir -p "$controller"
cat "${stage_a}/evidence.sha256" >"${controller}/stage-a3-evidence.sha256"
sha256sum "$source_supervisor" "$source_client" \
  "${lane}/tools/launch-tp4-ep4-eager-mtp0-512.sh" \
  >"${controller}/reviewed-inputs.sha256"
git rev-parse HEAD >"${controller}/repo-head.txt"
temporary=$(mktemp -d /tmp/q38-stage-b3-render.XXXXXX)

sed \
  -e 's#^script_dir=.*#script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools#' \
  -e 's#/tmp/q38-post-reset-mtp0-512-supervisor#/tmp/q38-post-reboot-mtp0-512-supervisor-stage-b3#g' \
  -e 's#post-reset-recovery-qualification-20260828-stage-b#post-reboot-recovery-qualification-20260828-stage-b3#g' \
  -e 's#attempt=28#attempt=29#g' \
  -e 's#19666#19667#g' \
  "$source_supervisor" >"${temporary}/supervisor.sh"
sed \
  -e 's#/tmp/q38-post-reset-mtp0-512-supervisor#/tmp/q38-post-reboot-mtp0-512-supervisor-stage-b3#g' \
  -e 's#post-reset-recovery-qualification-20260828-stage-b#post-reboot-recovery-qualification-20260828-stage-b3#g' \
  -e 's#attempt28#attempt29#g' \
  -e 's#19666#19667#g' \
  "$source_client" >"${temporary}/client.sh"
chmod 700 "${temporary}/supervisor.sh" "${temporary}/client.sh"
sha256sum "${temporary}/supervisor.sh" "${temporary}/client.sh" \
  >"${controller}/rendered-inputs.sha256"

timeout --signal=TERM --kill-after=90s 1800s "${temporary}/supervisor.sh" \
  >"${controller}/supervisor.stdout" 2>"${controller}/supervisor.stderr" &
supervisor_pid=$!
write_atomic "${controller}/supervisor.pid" "$supervisor_pid"

healthy=0
for _ in $(seq 1 1200); do
  kill -0 "$supervisor_pid" 2>/dev/null || break
  if curl --connect-timeout 2 --max-time 5 -fsS "http://127.0.0.1:${port}/health" \
    >"${controller}/health-ready.json.tmp" 2>/dev/null; then
    mv "${controller}/health-ready.json.tmp" "${controller}/health-ready.json"
    healthy=1
    break
  fi
  sleep 1
done
(( healthy == 1 )) || { printf 'FAIL: Stage B3 server never became healthy\n' >&2; exit 1; }

"${temporary}/client.sh" >"${controller}/client.stdout" 2>"${controller}/client.stderr"
grep -Fxq 'PASS exact OK hash usage cache-zero normal-stop recovery canary' \
  "${run_dir}/post-reset-canary-gates-passed.txt"
jq -e '.status == "passed" and .normalized == "OK" and
  .speed_credit == false and .quality_credit == false and .matrix_credit == false' \
  "${run_dir}/post-reset-canary.json" >/dev/null
write_atomic "${state}.stop" 'STOP after passed post-reset MTP0 canary'

set +e
wait "$supervisor_pid"
supervisor_rc=$?
set -e
supervisor_pid=""
write_atomic "${controller}/supervisor.rc" "$supervisor_rc"
(( supervisor_rc == 0 )) || { printf 'FAIL: Stage B3 supervisor rc=%s\n' "$supervisor_rc" >&2; exit 1; }
[[ "$(cat "${state}.rc")" == 0 ]] || { printf 'FAIL: Stage B3 state did not pass\n' >&2; exit 1; }
write_atomic "${controller}/gates-passed.txt" \
  'PASS post-reboot exact OK cache-zero generation canary and clean teardown'
printf 'PASS: post-reboot Stage B3 generation canary\n'
