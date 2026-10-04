#!/usr/bin/env bash
# Is the two-card FP8 server's host heap reclaimable? Starts the package server once, measures each process's
# anonymous memory, asks glibc to return free heap pages in every process (`malloc_trim(0)`, called from outside with
# gdb so no server code changes), measures again, checks the server still gives the same answer, and stops it.
# A measurement only: nothing is left running.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab; OUT="${1:?out dir}"; mkdir -p "${OUT}"
SUDO_FILE="${HOME}/SUDO_PASSWORD.txt"; root() { sudo -S -p '' "$@" < "${SUDO_FILE}"; }
log() { printf '[%s] %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "${OUT}/session.log"; }
FAULT_RE='Fault response|CAT error|Engine reset|Timedout job|coredump has been created|hard LOCKUP|soft lockup'
SINCE="$(date -Is)"
ask() { curl -s -m 180 http://127.0.0.1:18124/v1/completions -H 'Content-Type: application/json' \
        -d '{"model":"qwen38-27b-fp8","prompt":"Explain in three sentences why the sky is blue.","max_tokens":96,"temperature":0}'; }
snap() {  # snap <label>
  for pid in ${PIDS}; do
    printf '%s %s %s %s\n' "$1" "${pid}" "$(root cat /proc/${pid}/status | awk '/^Name/{n=$2} /^RssAnon/{a=$2} END{print n, a}')" \
        "$(root cat /proc/${pid}/smaps | awk '/\[heap\]/{h=1;next} h&&/^Rss:/{print $2; exit}')" >> "${OUT}/rss.txt"
  done
  printf '%s cgroup_anon %s host_available_kb %s\n' "$1" "$(awk '/^anon /{print $2}' "${CG}/memory.stat")" "$(awk '/MemAvailable/{print $2}' /proc/meminfo)" >> "${OUT}/rss.txt"
}
[ "$(docker ps -q | wc -l)" -eq 0 ] || { log "a container is running; not starting"; exit 1; }
cd "${LAB}" || exit 1
systemd-run --user --unit fp8-mem-trim-server --collect --working-directory "${LAB}" \
    python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start --model-dir /mnt/fast-ai/llm-models/qwen3.8-27b-fp8 \
    --state-dir "${OUT}/service" --port 18124 >> "${OUT}/session.log" 2>&1 || { log "could not start"; exit 1; }
st=""
for i in $(seq 1 200); do
  st="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "${OUT}/service/state.json" 2>/dev/null || true)"
  case "${st}" in ready|failed|stopped) break ;; esac
  journalctl -k --since "${SINCE}" --no-pager | grep -qiE "${FAULT_RE}" && { log "GPU fault line during start"; exit 3; }
  sleep 5
done
log "server status: ${st}"
if [ "${st}" = "ready" ]; then
  cid="$(docker ps -q | head -1)"; CG="/sys/fs/cgroup/system.slice/docker-$(docker inspect -f '{{.Id}}' "${cid}").scope"
  PIDS="$(docker top "${cid}" -eo pid,args | awk 'NR>1 && !/resource_tracker/ {print $1}')"
  ask > "${OUT}/answer-before.json"; ask > "${OUT}/answer-before2.json"
  snap before
  for pid in ${PIDS}; do
    t0=$(date +%s.%N)
    root gdb -p "${pid}" -batch -ex 'call (int)malloc_trim(0)' > "${OUT}/gdb-${pid}.log" 2>&1
    log "malloc_trim in pid ${pid}: gdb rc=$? in $(python3 -c "import time,sys; print(round(time.time()-float(sys.argv[1]),1))" "${t0}") s, result $(grep -E '^\$1' "${OUT}/gdb-${pid}.log" | tail -1)"
  done
  sleep 3; snap after-trim
  ask > "${OUT}/answer-after.json"; ask > "${OUT}/answer-after2.json"
  snap after-two-requests
  # twenty more requests, to see whether the heap grows straight back
  for i in $(seq 1 20); do ask > /dev/null; done
  snap after-22-requests
  python3 - "${OUT}" <<'PY' | tee -a "${OUT}/session.log"
import json, sys
o = sys.argv[1]
t = [json.load(open(f"{o}/answer-{n}.json"))["choices"][0]["text"] for n in ("before", "before2", "after", "after2")]
print("same answer before and after the trim:", len(set(t)) == 1, "| answer length", len(t[0]))
PY
  root chown -R "$(id -u):$(id -g)" "${OUT}" 2>/dev/null
  python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py stop --state-dir "${OUT}/service" >> "${OUT}/session.log" 2>&1
  for i in $(seq 1 60); do [ "$(docker ps -q | wc -l)" -eq 0 ] && break; sleep 3; done
fi
log "containers left: $(docker ps -q | wc -l); fault lines since start: $(journalctl -k --since "${SINCE}" --no-pager | grep -ciE "${FAULT_RE}")"
