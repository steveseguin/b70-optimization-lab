#!/bin/bash
# Before the server starts the engine: the stable-mode checks (stable/preflight.sh), then claim the six cards
# (six.active = dsv41-server). A six.active left by a run that died with a freeze (no engine process) is removed.
# A research run that holds the cards blocks the start. Right after a boot the Gen4 setting may still be applying:
# up to 10 tries 30 s apart, except for fault lines in the kernel log (never retried).
W=/home/steve/dsv41-work
g=$(cat $W/six.active 2>/dev/null)
if [ -n "$g" ] && [ "$g" != dsv41-server ]; then
  if pgrep -f '^/home/steve/dsv41-work/own_run_v41' > /dev/null; then echo "the cards are in use by $g"; exit 1; fi
  echo "removing a stale six.active ($g; no engine runs)"; rm -f $W/six.active
fi
# after an engine stops, the driver gives its host memory back over some seconds: wait (up to 3 min) until at least
# 12 GiB is available, so the new engine's host-memory floor check does not refuse the load
for i in $(seq 1 36); do
  [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 12 ] && break
  [ $i = 1 ] && echo "waiting for host memory to settle ($(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MiB available)"
  sleep 5
done
# A freeze's machine-check record (BERT / mce "Machine Check ... Bank") is printed again in the first second of the
# next boot: that is the previous boot's fault (the freeze itself), not one in this boot. Acknowledge exactly those
# early lines (stable/faults-acked.txt, from 1 s after the last of them) so the server comes back after a freeze;
# any other fault line, or any line later in the boot, still blocks the start.
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event'
bid=$(cut -c1-8 /proc/sys/kernel/random/boot_id)
if ! awk -v b=$bid '$3 == b' $W/stable/faults-acked.txt 2>/dev/null | grep -q .; then
  lines=$(journalctl -k -b -o short-monotonic --no-pager | grep -iE "$J" | grep -v 'kernel: \[Hardware Error\]')
  if [ -n "$lines" ]; then
    late=$(echo "$lines" | awk '{match($0, /\[ *[0-9.]+\]/); t = substr($0, RSTART + 1, RLENGTH - 2) + 0; if (t >= 30) n++} END {print n + 0}')
    other=$(echo "$lines" | grep -vcE 'mce: \[Hardware Error\]: (Machine check events logged|CPU [0-9]+: Machine Check: .*Bank)')
    if [ "$late" = 0 ] && [ "$other" = 0 ]; then
      last=$(journalctl -k -b -o short-unix --no-pager | grep -iE "$J" | grep -v 'kernel: \[Hardware Error\]' | tail -1 | awk '{print int($1) + 1}')
      echo "$(date -d @$last '+%Y-%m-%d %H:%M:%S') $bid the previous boot's machine-check record printed at boot (the freeze itself; acknowledged by dsv41-serve preflight-serve.sh)" >> $W/stable/faults-acked.txt; sync
      echo "acknowledged the previous boot's machine-check record printed at boot: $(echo "$lines" | tail -1 | cut -c1-140)"
    fi
  fi
fi
for i in 1 2 3 4 5 6 7 8 9 10; do
  out=$($W/stable/preflight.sh 2>&1); rc=$?
  [ $rc = 0 ] && break
  echo "$out" | grep -q 'fault lines\|an engine runs' && { echo "$out"; exit 1; }
  [ $i = 10 ] && { echo "$out"; exit 1; }
  sleep 30
done
echo dsv41-server > $W/six.active; sync
echo "$out"
