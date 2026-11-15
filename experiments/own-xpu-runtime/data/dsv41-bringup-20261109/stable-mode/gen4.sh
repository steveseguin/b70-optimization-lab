#!/bin/bash
# gen4.sh [--apply]: the host-stability workaround's link half (owner 2026-11-15: "incorporate this solution").
# The six GPU root links (CPU root ports 00/20/40/80/a0/e0:01.1) run at Gen4 x16 through the kernel's PCIe link-speed
# cooling devices (cur_state 1 = one step below Gen5). Runtime-only: lost at every reboot, so re-apply after a boot
# BEFORE any six-card work. Without --apply: read-only check (exit 0 = all six at 16 GT/s x16 both ends).
# Never while an engine or a compiler runs (writes retrain links; reads are PCI config reads). Log: ../faults/gen4-links.txt
set -u
L=/home/steve/dsv41-work/faults/gen4-links.txt
R="00 20 40 80 a0 e0"
st() { local p=/sys/bus/pci/devices/0000:$1:01.1 ch; ch=$(ls -d $p/0000:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f].[0-7] 2>/dev/null | head -1)
  echo "$(cat $p/current_link_speed | cut -d' ' -f1)/x$(cat $p/current_link_width) peer $(cat $ch/current_link_speed | cut -d' ' -f1)/x$(cat $ch/current_link_width)"; }
cd_of() { for c in /sys/class/thermal/cooling_device*; do [ "$(cat $c/type)" = "PCIe_Port_Link_Speed_0000:$1:01.1" ] && echo $c; done; }
bad=0; for r in $R; do s=$(st $r); [ "$s" = "16.0/x16 peer 16.0/x16" ] || bad=1; echo "$r:01.1 $s"; done
[ $bad = 0 ] && { echo "gen4: all six root links Gen4 x16"; exit 0; }
[ "${1:-}" = --apply ] || { echo "gen4: NOT all at Gen4 x16 (run with --apply when no engine runs)"; exit 1; }
pgrep -f '^/home/steve/dsv41-work/own_run_v41' > /dev/null && { echo "gen4: an engine runs: not now"; exit 3; }
pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null && { echo "gen4: a compiler runs: not now"; exit 3; }
echo "== $(date '+%F %T') gen4 --apply (boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), BIOS $(cat /sys/class/dmi/id/bios_version))" >> $L
t0=$(date '+%F %T')
for r in $R; do
  c=$(cd_of $r); [ -n "$c" ] || { echo "$r: no link-speed cooling device" | tee -a $L; exit 4; }
  b=$(st $r); cs=$(cat $c/cur_state)
  if [ "$b" != "16.0/x16 peer 16.0/x16" ]; then
    sudo -S -p '' sh -c "echo 1 > $c/cur_state" < /home/steve/SUDO_PASSWORD.txt
    sleep 0.2
  fi
  echo "$r:01.1 before $b (state $cs) after $(st $r) (state $(cat $c/cur_state))" | tee -a $L
done
sudo -k
f=$(journalctl -k --since "$t0" -o cat | grep -iE 'AER:|PCIe Bus Error|Hardware Error|fault response|reset started')
[ -n "$f" ] && { echo "gen4: kernel lines after the change:" | tee -a $L; echo "$f" | head -5 | tee -a $L; exit 5; }
for r in $R; do [ "$(st $r)" = "16.0/x16 peer 16.0/x16" ] || { echo "gen4: $r not Gen4 x16 after apply" | tee -a $L; exit 6; }; done
echo "gen4: applied, all six Gen4 x16" | tee -a $L
