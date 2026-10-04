#!/usr/bin/env bash
# One-shot after a kernel-change reboot: the two-card FP8 service is the FIRST GPU work on the fresh boot,
# measured with the same ten stop/start cycles as the baseline (scripts/fp8-start-cycle-soak.sh), and the
# last cycle's service is left UP. Runs from the user unit b70-kernel-soak-once.service (linger is on), and
# only when the flag file exists; it removes the flag first so it can never run twice.
#
#   flag file content: "<expected kernel release> <label> <out dir> <cycles>"
#   optional ~/.b70-postboot-next: one shell command run after a clean soak (for example a queued campaign)
#   e.g.  7.0.0-38-generic k38 /mnt/fast-ai/bench-results/kernel-soak-20261003/k38 10
set -u
FLAG="${HOME}/.b70-kernel-soak-once"
[ -f "${FLAG}" ] || exit 0
read -r WANT LABEL OUT CYCLES < "${FLAG}"
rm -f "${FLAG}"
LAB=/home/steve/b70-optimization-lab
until mountpoint -q /mnt/fast-ai; do sleep 5; done
mkdir -p "${OUT}"
{
  echo "$(date -Is) postboot kernel soak: running $(uname -r), expected ${WANT}, label ${LABEL}, uptime $(uptime -p)"
  if [ "$(uname -r)" != "${WANT}" ]; then
    echo "$(date -Is) NOT RUNNING: the machine booted $(uname -r), not ${WANT}. Nothing was started."
    exit 1
  fi
  cd "${LAB}" && bash scripts/fp8-start-cycle-soak.sh --wait-boot --leave-up --label "${LABEL}" --cycles "${CYCLES:-10}" --out "${OUT}"
  rc=$?
  echo "$(date -Is) soak rc=${rc}"
  # Optional follow-up, queued before the reboot: one shell command in ~/.b70-postboot-next. It runs only after a clean
  # soak (service up, no fault lines) and the file is removed first, so it can never run twice.
  NEXT="${HOME}/.b70-postboot-next"
  if [ "${rc}" -eq 0 ] && [ -f "${NEXT}" ]; then
    cmd="$(cat "${NEXT}")"; rm -f "${NEXT}"
    echo "$(date -Is) follow-up: ${cmd}"
    bash -c "${cmd}"
    echo "$(date -Is) follow-up rc=$?"
  elif [ -f "${NEXT}" ]; then
    echo "$(date -Is) follow-up NOT run (soak rc=${rc}); ${NEXT} left in place"
  fi
} >> "${OUT}/postboot.log" 2>&1
