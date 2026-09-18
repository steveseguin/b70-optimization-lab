#!/usr/bin/env bash
#===============================================================================================
# Resume session after the 2026-09-18 GPU fault halt.
#
# WHAT THIS DOES, in order, stopping at the first failure:
#
#   phase 0  refuse to start unless the host is actually clear: no uncleared device coredump on
#            any card, nothing listening on 18124, no running container, the venvs and the model
#            present, enough host RAM and enough disk.
#   phase 1  bash scripts/check-qwen36-xpu-xccl-health.sh   -- both cards, single-device smoke
#            plus the two-rank XCCL all-reduce. Stop if rc != 0.
#   phase 2  MiniMax-H3 pruned control: smoke_h3.sh `one` (the host-staged cross-card route,
#            expandable segments, the 8-step turbo LoRA, STEPS=9 as the smoke script derives it),
#            then smoke_h3.sh `repeat` -- two runs at the same seed, hashes compared. This is the
#            run that tests the copy-engine hypothesis: session 10 faulted at the exact moment
#            hidden states first crossed from xpu:0 to xpu:1, and B70_H3_XFER=host is the control.
#   phase 3  the int8 A/B, only if phase 2 passed: same seed, same prompt, same canvas, one
#            difference (B70_H3_DENOISER=int8). Compared against the phase-2 pruned clip with
#            compare-h3-runs.py: the four receipt hashes and then frame by frame.
#   phase 4  restore the two-card FP8 service on 18124 the way the lc-3/lc-4 sessions did --
#            health probe, port-free wait on `ss -tan`, systemd-run --user the package serve.py,
#            poll state.json for `ready`, then the strict suite against the comm-2 no-MTP
#            reference (12/12 is the pass).
#
#   --only-service   skip phases 2 and 3 and go straight from the health probe to the service.
#                    Use this for a plain recovery when the MiniMax lane is not the point.
#
# Everything lands under /mnt/fast-ai/bench-results/resume-20260918/ (override with RESUME_ROOT).
#
#-----------------------------------------------------------------------------------------------
# DO NOT RUN THIS UNTIL THE USER HAS DECIDED. Read this block first.
#
# The devcoredump this script gates on is already dealt with. It was READ (copied out at 11:08 EDT
# to /mnt/fast-ai/bench-results/gpu-fault-20260918T1506/devcoredump-card2.txt, 503,704 bytes,
# sha256 5605d576...), and the driver then expired the sysfs node on its own:
#
#   Sep 18 11:03:56 EDT  xe 0000:03:00.0: [drm] Xe device coredump has been created
#   Sep 18 11:08    EDT  copied to the evidence folder
#   Sep 18 12:06:48 EDT  xe 0000:03:00.0: [drm] Xe device coredump has been deleted.
#
# So the phase-0 coredump gate below now PASSES, and there is nothing left to clear. (For the NEXT
# fault, these dumps expire after roughly an hour, so copy promptly:
#     sudo cp /sys/class/drm/cardN/device/devcoredump/data <evidence-dir>/devcoredump.bin
#     sudo sh -c 'echo 1 > /sys/class/drm/cardN/device/devcoredump/data'
#  -- writing to the node is what clears it early. This script never writes to that node.)
#
# What is left for the user to decide is whether to REBOOT FIRST. Two reasons it is not obvious:
#
#   * BOTH B70s logged a copy-engine CAT error, not one. card2 = 0000:03:00.0 (renderD129, xpu:0)
#     at 11:03:56 with the reset, the timed-out job and the coredump; and card0 = 0000:e3:00.0
#     (renderD128, xpu:1) at 11:08:00 with `Engine memory CAT error [18]: class=bcs` and
#     `Fault response: Unsuccessful -EINVAL`, four minutes later, as the hung python was being
#     killed. Both ends of the cross-card copy faulted. That is the strongest evidence yet for
#     the peer-to-peer blitter hypothesis -- and it also means the driver state on BOTH cards is
#     suspect, not just on xpu:0.
#   * The host has been up since 2026-09-17 08:56 and has taken copy-engine faults on 09-16,
#     09-17 (twice) and 09-18.
#
#   (a) NO REBOOT: run this script as it stands. Phase 1's health probe is the gate -- if the
#       driver state is bad, the probe fails and the script stops before any real work.
#   (b) REBOOT FIRST: the stronger reset, and it clears whatever the faults left behind. After a
#       reboot the post-boot route for the service is the autolauncher, not this script's phase 4:
#         nohup scripts/autolaunch-fp8-service.sh &
#       Then run this script WITHOUT --only-service if you still want phases 2 and 3 (it will
#       refuse at phase 0 because 18124 is bound -- stop the service first, or set RESUME_ROOT and
#       skip to what you want).
#
# HOW TO LAUNCH IT (never from an interactive Claude/terminal session -- the harness kills long
# jobs, and phase 2 alone is tens of minutes):
#
#   systemd-run --user --unit h3-resume-20260918 --collect \
#       --working-directory=/home/steve/b70-optimization-lab \
#       bash experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh
#
#   # plain recovery, service only:
#   systemd-run --user --unit fp8-resume-20260918 --collect \
#       --working-directory=/home/steve/b70-optimization-lab \
#       bash experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh --only-service
#
#   journalctl --user -u h3-resume-20260918 -f       # watch it
#   tail -f /mnt/fast-ai/bench-results/resume-20260918/session.log
#
# WHAT IT NEVER DOES: it never clears a coredump, never resets a card, never reboots, never stops
# a service or a container, never kills a process. Every one of those is a user decision
# (AGENTS.md). If the host is not in the state it expects, it stops and says why.
#
# If a GPU fault appears in the kernel log at any point, the script stops immediately and does NOT
# restore the service -- the evidence is left untouched for the user, exactly as on 2026-09-18.
#===============================================================================================
set -uo pipefail

LAB="${LAB:-/home/steve/b70-optimization-lab}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESUME_ROOT="${RESUME_ROOT:-/mnt/fast-ai/bench-results/resume-20260918}"
H3_OUT="${RESUME_ROOT}/minimax"
SERVICE_STATE="${RESUME_ROOT}/service"
STRICT_OUT="${RESUME_ROOT}/service-strict"
SESSION_LOG="${RESUME_ROOT}/session.log"

# The reference the two-card service has been gated against all week: comm-2, no MTP.
COMM2_STRICT="${COMM2_STRICT:-/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}"
MODEL_NAME="${MODEL_NAME:-qwen38-27b-fp8}"
PKG_TP2="${LAB}/packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py"
STRICT_SH="${LAB}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh"
COMPARE_STRICT="${LAB}/scripts/compare-strict-attempt-outputs.py"
HEALTH_SH="${LAB}/scripts/check-qwen36-xpu-xccl-health.sh"
XPU_PYTHON="${XPU_PYTHON:-${HOME}/.venvs/vllm-xpu/bin/python}"
SERVICE_UNIT="${SERVICE_UNIT:-fp8-service-20260918-resume}"

# The MiniMax run parameters. Pinned here rather than left to smoke_h3.sh's defaults so the
# pruned control and the int8 arm are provably the same run with one variable changed.
TURBO_LORA="${TURBO_LORA:-/mnt/fast-ai/llm-models/minimax-h3-comfy/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors}"
H3_SEED="${H3_SEED:-42}"
H3_HEIGHT="${H3_HEIGHT:-256}"
H3_WIDTH="${H3_WIDTH:-448}"
H3_FRAMES="${H3_FRAMES:-124}"
H3_PROMPT="${H3_PROMPT:-A slow dolly-in on a rain-slicked city street at night; neon signs reflect in the puddles, a lone figure with an umbrella walks away from camera. Ambient rain, distant traffic, a low synth drone.}"
H3_TIMEOUT="${H3_TIMEOUT:-5400}"          # one clip
H3_REPEAT_TIMEOUT="${H3_REPEAT_TIMEOUT:-10800}"  # the repeat gate is two clips back to back
CPU_VENV="${CPU_VENV:-/mnt/fast-ai/venvs/minimax-h3-cpu}"
GPU_VENV="${GPU_VENV:-/mnt/fast-ai/venvs/minimax-h3}"

MIN_DISK_MIB="${MIN_DISK_MIB:-8192}"
MIN_HOST_AVAIL_MIB="${MIN_HOST_AVAIL_MIB:-11264}"

ONLY_SERVICE=0
for arg in "$@"; do
  case "${arg}" in
    --only-service) ONLY_SERVICE=1 ;;
    -h|--help) sed -n '2,95p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: ${arg}" >&2; echo "usage: $0 [--only-service]" >&2; exit 2 ;;
  esac
done

mkdir -p "${RESUME_ROOT}"
SESSION_START="$(date -Is)"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { printf '[%s] %s\n' "$(ts)" "$*" | tee -a "${SESSION_LOG}"; }
phase() {
  printf '\n[%s] ===== PHASE %s =====\n' "$(ts)" "$*" | tee -a "${SESSION_LOG}"
}
die() {
  printf '\n[%s] STOP: %s\n' "$(ts)" "$*" | tee -a "${SESSION_LOG}" >&2
  printf '[%s] nothing was reset, cleared, stopped or killed. Session log: %s\n' \
      "$(ts)" "${SESSION_LOG}" | tee -a "${SESSION_LOG}" >&2
  exit 1
}

# A GPU fault anywhere in this session halts it, and phase 4 does NOT run afterwards.
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup'
fault_check() {   # fault_check <label>
  local hits
  hits="$(journalctl -k --since "${SESSION_START}" --no-pager 2>/dev/null | grep -iE "${FAULT_RE}" || true)"
  if [ -n "${hits}" ]; then
    printf '%s\n' "${hits}" | tail -40 > "${RESUME_ROOT}/FAULT-HALT.txt"
    say "GPU FAULT after $1 -- see ${RESUME_ROOT}/FAULT-HALT.txt"
    die "GPU fault detected after $1. The service is NOT being restored; the evidence is untouched."
  fi
}

#-----------------------------------------------------------------------------------------------
phase "0  preconditions (checks only -- this phase changes nothing)"
say "session root ${RESUME_ROOT}; only_service=${ONLY_SERVICE}; git $(git -C "${LAB}" rev-parse --short HEAD 2>/dev/null || echo '?')"

fail=0

# (a) an uncleared device coredump means a card faulted and nothing has cleared it. READ ONLY.
for dump in /sys/class/drm/card*/device/devcoredump/data; do
  [ -e "${dump}" ] || continue
  card="${dump#/sys/class/drm/}"; card="${card%%/*}"
  say "PRECONDITION FAIL: ${card} still holds an uncleared device coredump at ${dump}"
  say "  failing device: $(readlink -f "$(dirname "${dump}")/failing_device" 2>/dev/null || echo unknown)"
  say "  Read it and clear it as root, or reboot -- both are the user's decision. See the header."
  fail=1
done

# (b) port 18124 must be completely free: not listening, and not in teardown either.
if ss -tan 2>/dev/null | awk '{print $4}' | grep -qE '(^|:)18124$'; then
  say "PRECONDITION FAIL: 18124 is still bound (a service is up, or its socket is in teardown):"
  ss -tan 2>/dev/null | awk 'NR==1 || $4 ~ /(^|:)18124$/' | sed 's/^/    /' | tee -a "${SESSION_LOG}"
  fail=1
fi

# (c) no container may hold the cards.
if command -v docker >/dev/null 2>&1; then
  running="$(docker ps -q 2>/dev/null | wc -l)"
  if [ "${running}" -gt 0 ]; then
    say "PRECONDITION FAIL: ${running} container(s) running:"
    docker ps --format '    {{.ID}}  {{.Image}}  {{.Status}}  {{.Names}}' 2>/dev/null | tee -a "${SESSION_LOG}"
    fail=1
  else
    say "no containers running"
  fi
else
  say "PRECONDITION FAIL: docker is not on PATH"; fail=1
fi

# (d) the render nodes must be idle.
if command -v fuser >/dev/null 2>&1; then
  if fuser /dev/dri/renderD* >/dev/null 2>&1; then
    say "PRECONDITION FAIL: something still holds a render node:"
    fuser -v /dev/dri/renderD* 2>&1 | sed 's/^/    /' | tee -a "${SESSION_LOG}"
    fail=1
  fi
fi

# (e) the things each phase needs, checked up front so a 40-minute phase 2 is not followed by a
#     phase 4 that dies on a missing reference.
for path in "${PKG_TP2}" "${STRICT_SH}" "${COMPARE_STRICT}" "${HEALTH_SH}" "${XPU_PYTHON}" \
            "${MODEL_DIR}" "${COMM2_STRICT}"; do
  [ -e "${path}" ] || { say "PRECONDITION FAIL: missing ${path}"; fail=1; }
done
if [ "${ONLY_SERVICE}" -eq 0 ]; then
  for path in "${HERE}/smoke_h3.sh" "${HERE}/compare-h3-runs.py" "${HERE}/mem-watchdog.sh" \
              "${GPU_VENV}/bin/python" "${CPU_VENV}/bin/python" "${TURBO_LORA}"; do
    [ -e "${path}" ] || { say "PRECONDITION FAIL: missing ${path}"; fail=1; }
  done
fi
[ -d "${SERVICE_STATE}" ] && { say "PRECONDITION FAIL: ${SERVICE_STATE} already exists (serve.py needs a fresh state dir)"; fail=1; }
[ -d "${STRICT_OUT}" ] && { say "PRECONDITION FAIL: ${STRICT_OUT} already exists (the strict wrapper refuses to overwrite)"; fail=1; }

# (f) host RAM and disk. /mnt/fast-ai was at 98% on 2026-09-18; a phase that cannot write its
#     receipt is worse than one that never started.
avail="$(awk '/^MemAvailable:/ {printf "%d", $2/1024; exit}' /proc/meminfo)"
say "MemAvailable ${avail} MiB (need >= ${MIN_HOST_AVAIL_MIB})"
[ "${avail}" -ge "${MIN_HOST_AVAIL_MIB}" ] || { say "PRECONDITION FAIL: not enough free host RAM"; fail=1; }
disk="$(df -Pm /mnt/fast-ai | awk 'NR==2 {print $4}')"
say "/mnt/fast-ai free ${disk} MiB (need >= ${MIN_DISK_MIB})"
[ "${disk}" -ge "${MIN_DISK_MIB}" ] || { say "PRECONDITION FAIL: not enough free disk on /mnt/fast-ai"; fail=1; }

[ "${fail}" -eq 0 ] || die "preconditions not met (see above). Nothing was changed."
say "phase 0 OK"
fault_check "phase 0"

#-----------------------------------------------------------------------------------------------
phase "1  XPU + XCCL health probe on both cards"
say "running ${HEALTH_SH}"
if PYTHON="${XPU_PYTHON}" timeout 1200 bash "${HEALTH_SH}" 2>&1 | tee -a "${RESUME_ROOT}/health.log" | tee -a "${SESSION_LOG}"; then
  health_rc=0
else
  health_rc="${PIPESTATUS[0]}"
fi
say "health probe rc=${health_rc}"
[ "${health_rc}" -eq 0 ] || die "the health probe failed (rc=${health_rc}). Both cards must pass before any work. See ${RESUME_ROOT}/health.log"
fault_check "phase 1"

#-----------------------------------------------------------------------------------------------
# Common environment for every MiniMax GPU run. Both are preconditions, not preferences:
#   PYTORCH_ALLOC_CONF=expandable_segments:True -- without it, with both cards visible, every GiB
#       placed on a card costs a GiB of HOST RAM (+8,125 MiB for 8 GiB, measured 2026-09-18).
#   B70_H3_XFER=host -- cross-card tensor moves staged through host RAM instead of a peer-to-peer
#       PCIe copy on the blitter. Bit-exact either way; this is the control for the fault.
#   B70_H3_LOADER=pread -- the streaming reader that keeps RssFile flat (mmap reached 6.3 GiB).
h3_env=(
  B70_H3_LOADER=pread
  B70_H3_XFER=host
  PYTORCH_ALLOC_CONF=expandable_segments:True
  OUT_ROOT="${H3_OUT}"
  LORA="${TURBO_LORA}"
  SEED="${H3_SEED}"
  HEIGHT="${H3_HEIGHT}"
  WIDTH="${H3_WIDTH}"
  FRAMES="${H3_FRAMES}"
  PROMPT="${H3_PROMPT}"
  GPU_VENV="${GPU_VENV}"
  CPU_VENV="${CPU_VENV}"
)
# STEPS is deliberately NOT set: smoke_h3.sh derives it from the LoRA (9 = 8 NFE, the turbo
# adapter's distillation point; 51 without it). Letting it derive is the point of the 09-18 fix.

# smoke_h3.sh names each run itself (`smoke-<stamp>`, `repeat-<stamp>-a/-b`). Find the newest one.
newest_run() {
  find "${H3_OUT}" -mindepth 2 -maxdepth 2 -name receipt.json -printf '%T@ %h\n' 2>/dev/null \
    | sort -rn | head -1 | cut -d' ' -f2-
}

if [ "${ONLY_SERVICE}" -eq 1 ]; then
  phase "2/3  SKIPPED (--only-service)"
  PRUNED_RUN=""
else
  mkdir -p "${H3_OUT}"

  phase "2  MiniMax-H3 pruned control -- one clip, then the repeat gate"
  say "denoiser=pruned  ${H3_WIDTH}x${H3_HEIGHT}  ${H3_FRAMES} frames  seed ${H3_SEED}  LoRA=$(basename "${TURBO_LORA}")"
  say "  (smoke_h3.sh runs its own preflight and wraps each run in mem-watchdog.sh at a 2048 MiB floor)"

  if env "${h3_env[@]}" B70_H3_DENOISER=pruned \
        timeout "${H3_TIMEOUT}" bash "${HERE}/smoke_h3.sh" one 2>&1 | tee -a "${SESSION_LOG}"; then
    one_rc=0
  else
    one_rc="${PIPESTATUS[0]}"
  fi
  say "smoke one rc=${one_rc}"
  fault_check "phase 2 (one)"
  [ "${one_rc}" -eq 0 ] || die "the pruned single clip failed (rc=${one_rc}). rc 4 = preflight refused; a watchdog KILL line in ${H3_OUT}/*.watchdog.log means host RAM, not the GPU."

  PRUNED_RUN="$(newest_run)"
  [ -n "${PRUNED_RUN}" ] || die "smoke one returned 0 but no receipt.json was written under ${H3_OUT}"
  say "pruned control clip: ${PRUNED_RUN}"

  if env "${h3_env[@]}" B70_H3_DENOISER=pruned \
        timeout "${H3_REPEAT_TIMEOUT}" bash "${HERE}/smoke_h3.sh" repeat 2>&1 | tee -a "${SESSION_LOG}"; then
    repeat_rc=0
  else
    repeat_rc="${PIPESTATUS[0]}"
  fi
  say "smoke repeat rc=${repeat_rc}"
  fault_check "phase 2 (repeat)"
  [ "${repeat_rc}" -eq 0 ] || die "the repeat gate failed (rc=${repeat_rc}). If the two runs' hashes differ, that is a RESULT to record, not a reason to re-run."
  say "phase 2 OK -- the pruned path renders and repeats bytewise"

  #---------------------------------------------------------------------------------------------
  phase "3  the int8 A/B against that pruned clip"
  say "same seed, same prompt, same canvas, same LoRA; one difference: B70_H3_DENOISER=int8"
  say "  (--denoiser int8 is selected through the environment, not an extra argument: smoke_h3.sh's"
  say "   'one' mode does not forward trailing arguments to the runner.)"

  if env "${h3_env[@]}" B70_H3_DENOISER=int8 \
        timeout "${H3_TIMEOUT}" bash "${HERE}/smoke_h3.sh" one 2>&1 | tee -a "${SESSION_LOG}"; then
    int8_rc=0
  else
    int8_rc="${PIPESTATUS[0]}"
  fi
  say "smoke one (int8) rc=${int8_rc}"
  fault_check "phase 3"
  [ "${int8_rc}" -eq 0 ] || die "the int8 clip failed (rc=${int8_rc}). An XPU OOM at ~2x the planned residency points at the compute_dtype=bfloat16 pin on the 50 AdaLN ConvRotLinears -- a code bug, not a capacity one."

  INT8_RUN="$(newest_run)"
  [ -n "${INT8_RUN}" ] || die "the int8 run returned 0 but wrote no receipt.json"
  say "int8 clip: ${INT8_RUN}"

  say "comparing int8 against the pruned control, hashes then frame by frame"
  "${CPU_VENV}/bin/python" "${HERE}/compare-h3-runs.py" "${PRUNED_RUN}" "${INT8_RUN}" \
      --json "${RESUME_ROOT}/int8-vs-pruned.json" 2>&1 | tee -a "${RESUME_ROOT}/int8-vs-pruned.log" | tee -a "${SESSION_LOG}"
  cmp_rc="${PIPESTATUS[0]}"
  say "compare rc=${cmp_rc} (0 = every frame bitwise identical; nonzero is EXPECTED here and is a measurement, not a failure)"
  [ -s "${RESUME_ROOT}/int8-vs-pruned.json" ] || die "the comparison wrote no report; do not read a verdict into phase 3"
  say "phase 3 OK -- report at ${RESUME_ROOT}/int8-vs-pruned.json"
fi

#-----------------------------------------------------------------------------------------------
phase "4  restore the two-card FP8 service on 18124, then the strict suite"

say "second health probe before the service takes both cards"
if PYTHON="${XPU_PYTHON}" timeout 1200 bash "${HEALTH_SH}" 2>&1 | tee -a "${RESUME_ROOT}/service-health.log" | tee -a "${SESSION_LOG}"; then
  svc_health_rc=0
else
  svc_health_rc="${PIPESTATUS[0]}"
fi
say "service health probe rc=${svc_health_rc}"
[ "${svc_health_rc}" -eq 0 ] || die "health probe failed before the service start (rc=${svc_health_rc}); NOT starting it."
fault_check "phase 4 (health)"

# The port-free wait is not decoration: the 02:43 restore on 2026-09-17 died on `[Errno 98]
# Address already in use` because serve.py binds without SO_REUSEADDR, and a just-stopped socket
# sits in teardown for some seconds. `ss -tan` (not -ltn) is what shows those non-LISTEN states.
say "waiting for 18124 to be completely free (ss -tan, up to 300 s)"
for i in $(seq 1 60); do
  ss -tan 2>/dev/null | awk '{print $4}' | grep -qE '(^|:)18124$' || break
  [ "${i}" -eq 1 ] && say "  18124 still in use, waiting..."
  sleep 5
done
if ss -tan 2>/dev/null | awk '{print $4}' | grep -qE '(^|:)18124$'; then
  ss -tan 2>/dev/null | awk 'NR==1 || $4 ~ /(^|:)18124$/' | sed 's/^/    /' | tee -a "${SESSION_LOG}"
  die "18124 did not become free within 300 s"
fi
say "18124 free"

mkdir -p "$(dirname "${SERVICE_STATE}")"
service_argv=(systemd-run --user --unit "${SERVICE_UNIT}" --working-directory "${LAB}" --collect
              python3 "${PKG_TP2}" start
              --model-dir "${MODEL_DIR}" --state-dir "${SERVICE_STATE}" --port 18124)
TS_NOW="$(ts)" OUTFILE="${RESUME_ROOT}/service.command.json" python3 -c '
import json, os, sys
json.dump({"argv": sys.argv[1:], "started": os.environ["TS_NOW"]}, open(os.environ["OUTFILE"], "w"), indent=2)
' "${service_argv[@]}" || say "(could not write service.command.json; continuing)"
say "starting: ${service_argv[*]}"
"${service_argv[@]}" 2>&1 | tee -a "${SESSION_LOG}" || die "systemd-run refused to start ${SERVICE_UNIT} (is the unit name already taken? systemctl --user reset-failed ${SERVICE_UNIT})"

# serve.py runs in the foreground inside its unit and writes its state receipt as it goes; there
# is no `wait` subcommand, so poll the receipt exactly as the lc-3/lc-4 runners do.
say "waiting for the service to report ready (up to 2400 s)"
status=""
for i in $(seq 1 240); do
  if [ -f "${SERVICE_STATE}/state.json" ]; then
    status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "${SERVICE_STATE}/state.json" 2>/dev/null || echo '')"
    case "${status}" in ready|failed|stopped) break ;; esac
  fi
  sleep 10
done
say "service status=${status:-<no receipt>}"
fault_check "phase 4 (start)"
[ "${status}" = "ready" ] || die "the service did not come ready (status=${status:-none}). See ${SERVICE_STATE}/server.log and \`python3 ${PKG_TP2} status --state-dir ${SERVICE_STATE}\`"
say "service ready on http://127.0.0.1:18124/v1  (unit ${SERVICE_UNIT}, state ${SERVICE_STATE})"

say "strict suite against the comm-2 no-MTP reference ${COMM2_STRICT}"
if OUT_DIR="${STRICT_OUT}" BASE_URL="http://127.0.0.1:18124" MODEL_NAME="${MODEL_NAME}" \
   PROFILE_LABEL="service" ATTEMPT_LABEL="resume-20260918" \
   timeout 2400 bash "${STRICT_SH}" 2>&1 | tee -a "${RESUME_ROOT}/service-strict.log" | tee -a "${SESSION_LOG}"; then
  strict_rc=0
else
  strict_rc="${PIPESTATUS[0]}"
fi
say "strict suite rc=${strict_rc}"
fault_check "phase 4 (strict)"
[ "${strict_rc}" -eq 0 ] || die "the strict suite failed (rc=${strict_rc}). The service is UP; see ${RESUME_ROOT}/service-strict.log"

python3 "${COMPARE_STRICT}" "${STRICT_OUT}" "${COMM2_STRICT}" \
    --output "${RESUME_ROOT}/service-strict-vs-reference.json" 2>&1 | tee -a "${SESSION_LOG}"
exact="$(python3 -c '
import json, sys
c = json.load(open(sys.argv[1]))["comparison"]
print("%d/%d" % (c["exact_prompts"], c["total_prompts"]))
' "${RESUME_ROOT}/service-strict-vs-reference.json" 2>/dev/null || echo '?')"
tok_s="$(python3 -c '
import json, sys
s = json.load(open(sys.argv[1]))["summary"]
print(round(s["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"], 2))
' "${STRICT_OUT}/performance.json" 2>/dev/null || echo '?')"
say "STRICT PARITY: ${exact} vs the comm-2 no-MTP reference, at ${tok_s} tok/s"
[ "${exact}" = "12/12" ] || die "strict parity is ${exact}, not 12/12. The service is UP but it does NOT reproduce the reference -- write this up before using it."

#-----------------------------------------------------------------------------------------------
phase "DONE"
say "health probe: clean on both cards"
if [ "${ONLY_SERVICE}" -eq 0 ]; then
  say "MiniMax-H3: pruned clip ${PRUNED_RUN}, repeat gate passed, int8 A/B in ${RESUME_ROOT}/int8-vs-pruned.json"
fi
say "FP8 two-card service: UP on 18124, unit ${SERVICE_UNIT}, state ${SERVICE_STATE}, strict ${exact} at ${tok_s} tok/s"
say "everything is under ${RESUME_ROOT}"
say "remember to update CURRENT.md with the outcome"
exit 0
