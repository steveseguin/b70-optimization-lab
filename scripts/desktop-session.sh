#!/usr/bin/env bash
# Stop or start the graphical desktop on the 15 GiB two-B70 host, to give a host-RAM-heavy load the memory
# the desktop holds and to take the desktop out of systemd-oomd's reach (it killed the desktop on 2026-09-17
# and 2026-09-20). Run it from an ssh session: `off` ends the graphical login and every app in it.
#
#   scripts/desktop-session.sh status      what the desktop holds right now
#   scripts/desktop-session.sh off         sudo systemctl stop gdm     (ssh, user units and GPU jobs keep running: linger is on)
#   scripts/desktop-session.sh on          sudo systemctl start gdm    (back to the login screen)
set -euo pipefail
SUDO_FILE="${SUDO_FILE:-${HOME}/SUDO_PASSWORD.txt}"
root() { if [ -r "${SUDO_FILE}" ]; then sudo -S -p '' "$@" < "${SUDO_FILE}"; else sudo "$@"; fi; }
case "${1:-status}" in
  status)
    echo "gdm: $(systemctl is-active gdm 2>/dev/null || true); MemAvailable $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
    systemd-cgtop -b -n 1 --order=memory 2>/dev/null | grep -E 'user-1000|gdm' | head -8 || true
    ;;
  off)
    [ -n "${SSH_CONNECTION:-}" ] || [ "${FORCE:-0}" = "1" ] || { echo "not an ssh session; this would end your own desktop. FORCE=1 to do it anyway." >&2; exit 2; }
    before="$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)"
    root systemctl stop gdm; sleep 5
    echo "desktop stopped; MemAvailable ${before} -> $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
    ;;
  on)
    root systemctl start gdm; echo "desktop started (login screen)"
    ;;
  *) sed -n '2,9p' "$0"; exit 2 ;;
esac
