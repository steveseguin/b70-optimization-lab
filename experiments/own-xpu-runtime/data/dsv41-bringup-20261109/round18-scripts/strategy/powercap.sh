#!/bin/bash
# powercap.sh WATTS (owner-approved GPU power cap test, 2026-11-13: 200 W, 175 W next if host resets continue).
# Sets power1_cap on every xe card to WATTS and logs before/after to faults/powercap-20261113.txt.
# Run only when no card job runs (it reads/writes card power registers). After any boot while the test runs:
#   /home/steve/dsv41-work/powercap.sh 200
# Uses the sudo password file through stdin only; never prints it.
set -u
w=${1:?watts}; case $w in 175|200) ;; *) echo "only 175 or 200 W are owner-approved"; exit 2;; esac
L=/home/steve/dsv41-work/faults/powercap-20261113.txt
pgrep '^own_run_v41' > /dev/null && { echo "an engine run is active: not now"; exit 3; }
echo "== $(date '+%F %T') power1_cap -> $w W (boot $(cut -c1-8 /proc/sys/kernel/random/boot_id))" >> $L
for h in /sys/class/hwmon/hwmon*; do
  [ "$(cat $h/name 2>/dev/null)" = xe ] || continue
  d=$(basename "$(readlink -f $h/device)"); b=$(cat $h/power1_cap)
  sudo -S -p '' sh -c "echo $((w*1000000)) > $h/power1_cap" < /home/steve/SUDO_PASSWORD.txt
  echo "${d:5:2} $(basename $h) power1_cap before $b after $(cat $h/power1_cap) crit $(cat $h/power1_crit)" >> $L
done
sudo -k
tail -7 $L
