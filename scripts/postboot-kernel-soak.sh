#!/usr/bin/env bash
# One-shot after a kernel-change reboot: the two-card FP8 service is the FIRST GPU work on the fresh boot,
# measured with the same ten stop/start cycles as the baseline (scripts/fp8-start-cycle-soak.sh), and the
# last cycle's service is left UP. Runs from the user unit b70-kernel-soak-once.service (linger is on), and
# only when the flag file exists; it removes the flag first so it can never run twice.
#
#   flag file content: "<expected kernel release> <label> <out dir> <cycles>"
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
  echo "$(date -Is) soak rc=$?"
} >> "${OUT}/postboot.log" 2>&1
