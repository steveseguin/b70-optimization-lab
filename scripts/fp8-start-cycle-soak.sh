#!/usr/bin/env bash
# Two-card FP8 service stop/start soak: the same N cycles on every kernel, so kernels can be compared.
#
# Why this exists
# ---------------
# Every copy-engine (bcs) fault on the two-B70 host hit during a service START (weight load), never in steady
# serving. A kernel is therefore judged by "faults per start", not by uptime. This runner does one health probe,
# then N times: wait for a free port and stage lock, start the pinned two-card service in its own user unit, wait
# for ready, run the 12-prompt strict suite against the comm-2 no-MTP reference, stop the service, and count the
# kernel fault lines of that cycle by phase. It halts at the FIRST fault line and touches nothing afterwards
# (no reset, no reboot; it copies the device coredump out read-only if sudo is available).
#
# Usage (always inside a user unit; never from an agent shell, the harness kills long jobs):
#   systemd-run --user --unit fp8-soak-k31 --collect --working-directory=/home/steve/b70-optimization-lab \
#       bash scripts/fp8-start-cycle-soak.sh --label k31 --cycles 10 --out /mnt/fast-ai/bench-results/kernel-soak-20261003/k31
#   --leave-up     keep the service of the last cycle running (unit fp8-soak-<label>-cNN)
#   --wait-boot    first wait for /mnt/fast-ai and docker, then 60 s (for a post-boot one-shot unit)
#   --prior-work   free text recorded in identity.json: what GPU work this boot did before the soak
#
# Output: <out>/session.log, identity.json, cycles.tsv, summary.json, cNN/{service,strict,strict-vs-reference.json,
# swap.csv,faults.txt}. Exit 0 = all cycles clean and 12/12; 3 = halted on a fault; 1 = anything else.
set -uo pipefail

LAB="${LAB:-/home/steve/b70-optimization-lab}"
LABEL="soak"; CYCLES=10; OUT=""; LEAVE_UP=0; WAIT_BOOT=0; PRIOR="none (service-first)"
while [ $# -gt 0 ]; do
  case "$1" in
    --label) LABEL="$2"; shift 2 ;;
    --cycles) CYCLES="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --leave-up) LEAVE_UP=1; shift ;;
    --wait-boot) WAIT_BOOT=1; shift ;;
    --prior-work) PRIOR="$2"; shift 2 ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "${OUT}" ] || { echo "--out is required" >&2; exit 2; }

COMM2_STRICT="${COMM2_STRICT:-/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}"
MODEL_NAME="${MODEL_NAME:-qwen38-27b-fp8}"
PKG_TP2="${LAB}/packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py"
STRICT_SH="${LAB}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh"
COMPARE_STRICT="${LAB}/scripts/compare-strict-attempt-outputs.py"
HEALTH_SH="${LAB}/scripts/check-qwen36-xpu-xccl-health.sh"
SWAP_SH="${LAB}/scripts/measure-swap-during-start.sh"
XPU_PYTHON="${XPU_PYTHON:-${HOME}/.venvs/vllm-xpu/bin/python}"
STAGE_LOCK="${STAGE_LOCK:-/tmp/qwen-short-prefill-stage.lock}"
PORT=18124
MIN_HOST_AVAIL_MIB="${MIN_HOST_AVAIL_MIB:-9216}"
SUDO_FILE="${SUDO_FILE:-${HOME}/SUDO_PASSWORD.txt}"

if [ "${WAIT_BOOT}" -eq 1 ]; then
  until mountpoint -q /mnt/fast-ai && docker info >/dev/null 2>&1; do sleep 5; done
  sleep 60
fi
mkdir -p "${OUT}"
LOG="${OUT}/session.log"
TSV="${OUT}/cycles.tsv"
ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { printf '[%s] %s\n' "$(ts)" "$*" | tee -a "${LOG}"; }
avail_mib() { awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo; }
pswpout() { awk '/^pswpout / {print $2}' /proc/vmstat; }
port_busy() { ss -tan 2>/dev/null | awk '{print $4}' | grep -qE "(^|:)${PORT}\$"; }

FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup|hard LOCKUP'
faults_since() { journalctl -k --since "$1" --no-pager -o short-iso 2>/dev/null | grep -iE "${FAULT_RE}" || true; }

finish() {   # finish <rc> <reason>
  python3 - "${TSV}" "${OUT}/summary.json" "$1" "$2" "${LABEL}" "${CYCLES}" <<'PY' 2>>"${LOG}" || true
import csv, json, sys, statistics
tsv, out, rc, reason, label, planned = sys.argv[1:7]
rows = list(csv.DictReader(open(tsv), delimiter="\t")) if __import__("os").path.exists(tsv) else []
toks = [float(r["tok_s"]) for r in rows if r["tok_s"] not in ("", "?")]
json.dump({
    "label": label, "planned_cycles": int(planned), "completed_cycles": sum(r["result"] == "clean" for r in rows),
    "attempted_cycles": len(rows), "fault_cycles": sum(int(r["fault_lines"]) > 0 for r in rows),
    "fault_lines_total": sum(int(r["fault_lines"]) for r in rows),
    "all_exact": all(r["exact"] == "12/12" for r in rows) if rows else False,
    "tok_s_median": round(statistics.median(toks), 2) if toks else None,
    "tok_s_min": min(toks) if toks else None, "tok_s_max": max(toks) if toks else None,
    "ready_s_median": statistics.median([int(r["ready_s"]) for r in rows if r["ready_s"].isdigit()]) if rows else None,
    "host_swapout_mib_total": sum(int(r["host_swapout_mib"]) for r in rows),
    "min_mem_available_mib": min([int(r["min_avail_mib"]) for r in rows if r["min_avail_mib"].isdigit()] or [0]),
    "exit": int(rc), "reason": reason,
}, open(out, "w"), indent=2)
PY
  say "END rc=$1 ($2); summary ${OUT}/summary.json"
  exit "$1"
}

save_coredumps() {   # read-only evidence copy; the sysfs node expires after about an hour
  local d card
  for d in /sys/class/drm/card*/device/devcoredump/data; do
    [ -e "${d}" ] || continue
    card="${d#/sys/class/drm/}"; card="${card%%/*}"
    if [ -r "${SUDO_FILE}" ] && sudo -S -p '' cp "${d}" "${OUT}/devcoredump-${card}.txt" < "${SUDO_FILE}" 2>/dev/null; then
      sudo -S -p '' chown "$(id -u):$(id -g)" "${OUT}/devcoredump-${card}.txt" < "${SUDO_FILE}" 2>/dev/null
      say "copied the ${card} device coredump to ${OUT}/devcoredump-${card}.txt (the node itself is untouched)"
    else
      say "could not copy the ${card} device coredump (needs root): sudo cp ${d} ${OUT}/"
    fi
  done
}

halt_on_fault() {   # halt_on_fault <cycle dir> <phase> <since>
  local hits; hits="$(faults_since "$3")"
  [ -n "${hits}" ] || return 0
  printf '%s\n' "${hits}" > "$1/faults.txt"
  FAULT_LINES="$(printf '%s\n' "${hits}" | wc -l)"; FAULT_PHASE="$2"
  say "GPU FAULT in cycle ${c} during ${2}: ${FAULT_LINES} line(s), first: $(printf '%s\n' "${hits}" | head -1 | cut -c1-200)"
  save_coredumps
  journalctl -k -b --no-pager -o short-iso > "${OUT}/kernel-log-at-fault.txt" 2>/dev/null || true
  return 1
}

say "soak ${LABEL}: ${CYCLES} cycle(s), out ${OUT}, leave_up=${LEAVE_UP}"
python3 - "${OUT}/identity.json" "${LABEL}" "${PRIOR}" <<'PY' 2>>"${LOG}" || true
import json, subprocess, sys, platform
def sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e: return f"? {e}"
json.dump({
    "label": sys.argv[2], "kernel": platform.release(), "cmdline": open("/proc/cmdline").read().strip(),
    "boot_id": open("/proc/sys/kernel/random/boot_id").read().strip(), "uptime_s": float(open("/proc/uptime").read().split()[0]),
    "guc": sh("journalctl -k -b --no-pager | grep -o 'GuC firmware.*version [0-9.]*' | sort -u"),
    "compute_runtime": sh("dpkg-query -W -f='${Version}' libze-intel-gpu1"),
    "linux_firmware": sh("dpkg-query -W -f='${Version}' linux-firmware"),
    "swappiness": sh("cat /proc/sys/vm/swappiness"), "mem_total_kb": sh("awk '/MemTotal/{print $2}' /proc/meminfo"),
    "git": sh("git -C /home/steve/b70-optimization-lab rev-parse HEAD"),
    "fault_lines_before_soak_this_boot": sh("journalctl -k -b --no-pager | grep -ciE 'Fault response|CAT error|Timedout job'"),
    "gpu_work_before_soak_this_boot": sys.argv[3],
}, open(sys.argv[1], "w"), indent=2)
PY

# ---- preconditions (checks only)
fail=0
for d in /sys/class/drm/card*/device/devcoredump/data; do
  [ -e "${d}" ] && { say "PRECONDITION FAIL: uncleared device coredump at ${d}"; fail=1; }
done
port_busy && { say "PRECONDITION FAIL: ${PORT} is bound"; fail=1; }
[ "$(docker ps -q 2>/dev/null | wc -l)" -eq 0 ] || { say "PRECONDITION FAIL: a container is running"; fail=1; }
[ -d "${MODEL_DIR}" ] && [ -d "${COMM2_STRICT}" ] && [ -x "${XPU_PYTHON}" ] || { say "PRECONDITION FAIL: model, reference or venv missing"; fail=1; }
[ "$(avail_mib)" -ge "${MIN_HOST_AVAIL_MIB}" ] || { say "PRECONDITION FAIL: MemAvailable $(avail_mib) MiB < ${MIN_HOST_AVAIL_MIB}"; fail=1; }
[ "${fail}" -eq 0 ] || finish 1 "preconditions"

SOAK_START="$(date -Is)"
say "health probe (both cards, single-device smoke + two-rank all-reduce)"
if PYTHON="${XPU_PYTHON}" timeout 1200 bash "${HEALTH_SH}" > "${OUT}/health.log" 2>&1; then hrc=0; else hrc=$?; fi
say "health probe rc=${hrc}"
[ "${hrc}" -eq 0 ] || finish 1 "health probe failed"
[ -z "$(faults_since "${SOAK_START}")" ] || { faults_since "${SOAK_START}" > "${OUT}/faults-health.txt"; save_coredumps; finish 3 "fault during the health probe"; }

printf 'cycle\tstarted\tready_s\texact\ttok_s\tfault_lines\tfault_phase\thost_swapout_mib\tmin_avail_mib\tresult\n' > "${TSV}"

for c in $(seq 1 "${CYCLES}"); do
  cn="$(printf 'c%02d' "${c}")"; CD="${OUT}/${cn}"; mkdir -p "${CD}"
  UNIT="fp8-soak-${LABEL}-${cn}"
  FAULT_LINES=0; FAULT_PHASE="-"; exact="?"; tok_s="?"; ready_s="?"; result="clean"
  say "===== cycle ${c}/${CYCLES} (unit ${UNIT}) ====="

  for i in $(seq 1 60); do port_busy || break; sleep 5; done
  port_busy && { say "port ${PORT} never became free"; finish 1 "port busy before cycle ${c}"; }
  for i in $(seq 1 60); do
    [ ! -e "${STAGE_LOCK}" ] && break
    flock -n "${STAGE_LOCK}" true 2>/dev/null && break
    sleep 2
  done
  [ "$(docker ps -q 2>/dev/null | wc -l)" -eq 0 ] || finish 1 "a container is still running before cycle ${c}"

  CYCLE_START="$(date -Is)"; t0=$(date +%s); swp0=$(pswpout)
  bash "${SWAP_SH}" --unit "${UNIT}" --out "${CD}/swap.csv" --interval 0.5 --timeout 1200 > "${CD}/swap-sampler.log" 2>&1 &
  sampler=$!
  systemd-run --user --unit "${UNIT}" --working-directory "${LAB}" --collect \
      python3 "${PKG_TP2}" start --model-dir "${MODEL_DIR}" --state-dir "${CD}/service" --port "${PORT}" >> "${LOG}" 2>&1 \
      || finish 1 "systemd-run refused unit ${UNIT}"

  status=""
  for i in $(seq 1 480); do
    if [ -f "${CD}/service/state.json" ]; then
      status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "${CD}/service/state.json" 2>/dev/null || echo '')"
      case "${status}" in ready|failed|stopped) break ;; esac
    fi
    halt_on_fault "${CD}" start "${CYCLE_START}" || break
    systemctl --user is-active --quiet "${UNIT}" || { sleep 3; [ -f "${CD}/service/state.json" ] || { status="unit-exited"; break; }; }
    sleep 5
  done
  ready_s=$(( $(date +%s) - t0 ))
  kill "${sampler}" 2>/dev/null; wait "${sampler}" 2>/dev/null
  if ! halt_on_fault "${CD}" start "${CYCLE_START}"; then result="fault"; fi

  if [ "${result}" = "clean" ] && [ "${status}" != "ready" ]; then
    result="not-ready(${status:-none})"
  fi

  if [ "${result}" = "clean" ]; then
    say "ready after ${ready_s} s; strict suite"
    if OUT_DIR="${CD}/strict" BASE_URL="http://127.0.0.1:${PORT}" MODEL_NAME="${MODEL_NAME}" PROFILE_LABEL="service" \
       ATTEMPT_LABEL="${LABEL}-${cn}" timeout 2400 bash "${STRICT_SH}" > "${CD}/strict.log" 2>&1; then src=0; else src=$?; fi
    if ! halt_on_fault "${CD}" strict "${CYCLE_START}"; then result="fault"
    elif [ "${src}" -ne 0 ]; then result="strict-rc-${src}"
    else
      python3 "${COMPARE_STRICT}" "${CD}/strict" "${COMM2_STRICT}" --output "${CD}/strict-vs-reference.json" >> "${LOG}" 2>&1
      exact="$(python3 -c 'import json,sys; c=json.load(open(sys.argv[1]))["comparison"]; print("%d/%d" % (c["exact_prompts"], c["total_prompts"]))' "${CD}/strict-vs-reference.json" 2>/dev/null || echo '?')"
      tok_s="$(python3 -c 'import json,sys; s=json.load(open(sys.argv[1]))["summary"]; print(round(s["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"], 2))' "${CD}/strict/performance.json" 2>/dev/null || echo '?')"
      [ "${exact}" = "12/12" ] || result="parity-${exact}"
    fi
  fi

  last=0; [ "${c}" -eq "${CYCLES}" ] && last=1
  if [ "${result}" = "clean" ] && ! { [ "${last}" -eq 1 ] && [ "${LEAVE_UP}" -eq 1 ]; }; then
    python3 "${PKG_TP2}" stop --state-dir "${CD}/service" >> "${LOG}" 2>&1 || say "serve.py stop returned non-zero"
    for i in $(seq 1 60); do
      [ "$(docker ps -q 2>/dev/null | wc -l)" -eq 0 ] && ! systemctl --user is-active --quiet "${UNIT}" && break
      sleep 3
    done
    sleep 5
    if ! halt_on_fault "${CD}" stop "${CYCLE_START}"; then result="fault"; fi
  fi

  swp=$(( ( $(pswpout) - swp0 ) * 4 / 1024 ))
  minav="$(awk -F, 'NR>1 && $9+0>0 {v=int($9/1024); if (m=="" || v<m) m=v} END {print (m==""?"?":m)}' "${CD}/swap.csv" 2>/dev/null || echo '?')"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "${c}" "${CYCLE_START}" "${ready_s}" "${exact}" "${tok_s}" \
      "${FAULT_LINES}" "${FAULT_PHASE}" "${swp}" "${minav}" "${result}" >> "${TSV}"
  say "cycle ${c}: result=${result} ready=${ready_s}s exact=${exact} tok/s=${tok_s} faults=${FAULT_LINES} swapout=${swp}MiB min_avail=${minav}MiB"

  case "${result}" in
    clean) ;;
    fault) finish 3 "GPU fault in cycle ${c} (${FAULT_PHASE}); nothing was reset; service state left as it was" ;;
    *) finish 1 "cycle ${c}: ${result}" ;;
  esac
done

if [ "${LEAVE_UP}" -eq 1 ]; then say "service left UP on ${PORT}: unit fp8-soak-${LABEL}-$(printf 'c%02d' "${CYCLES}"), state ${OUT}/$(printf 'c%02d' "${CYCLES}")/service"; fi
finish 0 "all ${CYCLES} cycles clean"
