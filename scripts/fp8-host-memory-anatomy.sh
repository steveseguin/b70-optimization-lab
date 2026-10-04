#!/usr/bin/env bash
# What is the two-card FP8 server's host memory made of? Starts the package server once, waits for ready, records per
# process and per mapping where the container's ~9 GiB of anonymous host memory sits, then stops the server gracefully.
# The server exists only for this measurement; nothing is left running.
#
# Why: on the 15 GiB host a loaded two-card server leaves ~3 GiB available, half a GiB above the research launcher's
# memory guard, and that margin caused two guard stops on 2026-10-03. Knowing what the memory is decides whether it can
# be given back (allocator arenas, leftover load buffers) or is real working state.
#
#   systemd-run --user --unit fp8-mem-anatomy --collect --working-directory=$PWD bash scripts/fp8-host-memory-anatomy.sh <out dir>
set -uo pipefail
LAB=/home/steve/b70-optimization-lab; OUT="${1:?out dir}"; mkdir -p "${OUT}"
SUDO_FILE="${HOME}/SUDO_PASSWORD.txt"; root() { sudo -S -p '' "$@" < "${SUDO_FILE}"; }
log() { printf '[%s] %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "${OUT}/session.log"; }
FAULT_RE='Fault response|CAT error|Engine reset|Timedout job|coredump has been created|hard LOCKUP|soft lockup'
SINCE="$(date -Is)"
[ "$(docker ps -q | wc -l)" -eq 0 ] || { log "a container is running; not starting"; exit 1; }
cd "${LAB}" || exit 1
systemd-run --user --unit fp8-mem-anatomy-server --collect --working-directory "${LAB}" \
    python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start --model-dir /mnt/fast-ai/llm-models/qwen3.8-27b-fp8 \
    --state-dir "${OUT}/service" --port 18124 >> "${OUT}/session.log" 2>&1 || { log "could not start"; exit 1; }
st=""
for i in $(seq 1 200); do
  st="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "${OUT}/service/state.json" 2>/dev/null || true)"
  case "${st}" in ready|failed|stopped) break ;; esac
  journalctl -k --since "${SINCE}" --no-pager | grep -qiE "${FAULT_RE}" && { log "GPU fault line during start; stopping here"; exit 3; }
  sleep 5
done
log "server status: ${st}"
if [ "${st}" = "ready" ]; then
  # one short request so every lazily created buffer exists
  curl -s -m 120 http://127.0.0.1:18124/v1/completions -H 'Content-Type: application/json' \
      -d '{"model":"qwen38-27b-fp8","prompt":"The capital of France is","max_tokens":64,"temperature":0}' > "${OUT}/one-request.json" 2>&1
  cid="$(docker ps -q | head -1)"
  cg="/sys/fs/cgroup/system.slice/docker-$(docker inspect -f '{{.Id}}' "${cid}").scope"
  cat "${cg}/memory.stat" > "${OUT}/cgroup-memory.stat" 2>/dev/null
  cat "${cg}/memory.current" "${cg}/memory.peak" > "${OUT}/cgroup-memory-current-peak.txt" 2>/dev/null
  grep -E 'MemTotal|MemAvailable|AnonPages|Cached|Shmem|Mlocked|Unevictable|GPUActive' /proc/meminfo > "${OUT}/meminfo.txt"
  docker top "${cid}" -eo pid,ppid,rss,vsz,args > "${OUT}/docker-top.txt" 2>&1
  for pid in $(awk 'NR>1 {print $1}' "${OUT}/docker-top.txt"); do
    root cat "/proc/${pid}/smaps_rollup" > "${OUT}/smaps-rollup-${pid}.txt" 2>/dev/null
    root cat "/proc/${pid}/status" 2>/dev/null | grep -E 'Name|VmRSS|RssAnon|RssFile|RssShmem|VmSwap|VmLck|Threads' > "${OUT}/status-${pid}.txt"
    root cat "/proc/${pid}/cmdline" 2>/dev/null | tr '\0' ' ' | cut -c1-200 > "${OUT}/cmdline-${pid}.txt"
    # the largest resident mappings, with their kind (heap, anonymous, a file, a device)
    root cat "/proc/${pid}/smaps" 2>/dev/null | awk '
      /^[0-9a-f]+-[0-9a-f]+ / { name = (NF >= 6) ? $6 : "[anon]"; for (i = 7; i <= NF; i++) name = name " " $i; perms = $2 }
      /^Rss:/ { rss = $2 } /^Anonymous:/ { an = $2 } /^Locked:/ { printf "%d %d %d %s %s\n", rss, an, $2, perms, name }' \
      | sort -nr | head -25 > "${OUT}/top-mappings-${pid}.txt"
  done
  root chown -R "$(id -u):$(id -g)" "${OUT}" 2>/dev/null
  log "collected $(ls "${OUT}"/smaps-rollup-*.txt 2>/dev/null | wc -l) process snapshots"
  python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py stop --state-dir "${OUT}/service" >> "${OUT}/session.log" 2>&1
  for i in $(seq 1 60); do [ "$(docker ps -q | wc -l)" -eq 0 ] && break; sleep 3; done
fi
log "containers left: $(docker ps -q | wc -l); fault lines since start: $(journalctl -k --since "${SINCE}" --no-pager | grep -ciE "${FAULT_RE}")"
