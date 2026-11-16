#!/bin/bash
# preflight.sh: run before six-card work in the stable mode (and after every gap); read-only. Exit 0 = go.
# Stable mode (2026-11-15): BIOS 11.02, six GPU root links Gen4 x16 (gen4.sh), OWN_PX_SERIAL=1 (tp115 default;
# stable.env exports it for older binaries), default power limits (no cap), no fault line in this boot's kernel log.
set -u
W=/home/steve/dsv41-work; ok=0
b=$(cat /sys/class/dmi/id/bios_version); [ "$b" = 11.02 ] || { echo "preflight: BIOS $b (tested 11.02)"; ok=1; }
[ "$(cat /sys/devices/system/cpu/smt/active)" = 0 ] || { echo "preflight: SMT active (diagnostic config since 2026-11-15 15:09: SMT disabled in the BIOS)"; ok=1; }
pgrep -f '^/home/steve/dsv41-work/own_run_v41' > /dev/null && { echo "preflight: an engine runs"; exit 3; }
$W/stable/gen4.sh > /dev/null || { echo "preflight: root links not all Gen4 x16 (stable/gen4.sh --apply)"; ok=1; }
for h in /sys/class/hwmon/hwmon*; do [ "$(cat $h/name 2>/dev/null)" = xe ] || continue
  c=$(cat $h/power1_cap); case $c in 230000000|275000000) ;; *) echo "preflight: $(basename $(readlink -f $h/device)) power1_cap $c (default 230 / 275 W)"; ok=1;; esac; done
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event'
# acknowledged faults (stable/faults-acked.txt, one line "YYYY-MM-DD HH:MM:SS boot-id-8 reason"; only a fault we
# caused and understood, e.g. our own out-of-card-memory, never a hardware-looking one): this boot's kernel log is
# read from the newest acknowledgment of this boot on; any fault line after it still blocks
bid=$(cut -c1-8 /proc/sys/kernel/random/boot_id); since=$(awk -v b=$bid '$3 == b {t = $1 " " $2} END {print t}' $W/stable/faults-acked.txt 2>/dev/null)
if [ -n "$since" ]; then f=$(journalctl -k -b --since "$since" -o cat | grep -iE "$J" | grep -v '^\[Hardware Error\]' | head -3)
else f=$(journalctl -k -b -o cat | grep -iE "$J" | grep -v '^\[Hardware Error\]' | head -3); fi
[ -n "$f" ] && { echo "preflight: fault lines in this boot's kernel log${since:+ since the acknowledgment at $since}:"; echo "$f"; ok=1; }
[ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || { echo "preflight: MemAvailable < 7 GiB"; ok=1; }
[ $ok = 0 ] && echo "preflight: ok (BIOS $b, SMT off, Gen4 x16 x6, default power, clean kernel log${since:+ since $since})"
exit $ok
