#!/bin/bash
# b70-gen4-boot.sh (2026-11-16, owner OK): put the six B70 root links (CPU root ports 00/20/40/80/a0/e0:01.1) at
# Gen4 x16 at every boot, through the kernel's PCIe link-speed cooling devices (cur_state 1 = one step below Gen5).
# Then keeps the cards' audio functions awake (see below). Same link change as /home/steve/dsv41-work/stable/gen4.sh --apply, done by root at boot so it never depends on a session.
# Waits until the xe driver has bound all six cards, then 10 s more, so links retrain while the cards sit idle.
set -u
R="00 20 40 80 a0 e0"
for i in $(seq 1 180); do
  n=$(ls -d /sys/bus/pci/drivers/xe/0000:* 2>/dev/null | wc -l)
  [ "$n" -ge 6 ] && break
  sleep 1
done
echo "xe cards bound: $n (after ${i} s)"
sleep 10
st() { local p=/sys/bus/pci/devices/0000:$1:01.1 ch; ch=$(ls -d $p/0000:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f].[0-7] 2>/dev/null | head -1)
  echo "$(cut -d' ' -f1 $p/current_link_speed)/x$(cat $p/current_link_width) peer $(cut -d' ' -f1 $ch/current_link_speed)/x$(cat $ch/current_link_width)"; }
rc=0
for r in $R; do
  c=""
  for d in /sys/class/thermal/cooling_device*; do [ "$(cat $d/type)" = "PCIe_Port_Link_Speed_0000:$r:01.1" ] && c=$d; done
  [ -n "$c" ] || { echo "$r:01.1 no link-speed cooling device"; rc=4; continue; }
  b=$(st $r)
  [ "$b" = "16.0/x16 peer 16.0/x16" ] || { echo 1 > $c/cur_state; sleep 0.2; }
  a=$(st $r)
  echo "$r:01.1 before $b after $a (state $(cat $c/cur_state))"
  [ "$a" = "16.0/x16 peer 16.0/x16" ] || rc=6
done
[ $rc = 0 ] && echo "gen4-boot: all six Gen4 x16" || echo "gen4-boot: NOT all six Gen4 x16 (rc $rc)"
# Cards' audio functions + their internal bridges kept in D0 (owner OK 2026-11-16, every boot): no kernel PME polling
# of them (pci_pme_list_scan's config reads, ~6/s through the cards, = the stuck CPU access in most reset records).
for d in 0000:02:02.0 0000:22:02.0 0000:42:02.0 0000:82:02.0 0000:a2:02.0 0000:e2:02.0 \
         0000:04:00.0 0000:24:00.0 0000:44:00.0 0000:84:00.0 0000:a4:00.0 0000:e4:00.0; do
  f=/sys/bus/pci/devices/$d/power/control
  if [ -w $f ]; then echo on > $f; echo "$d power/control $(cat $f) $(cat /sys/bus/pci/devices/$d/power/runtime_status)"
  else echo "$d missing"; rc=7; fi
done
exit $rc
