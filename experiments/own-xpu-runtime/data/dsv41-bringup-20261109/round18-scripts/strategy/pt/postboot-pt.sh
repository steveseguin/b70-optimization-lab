#!/bin/bash
# One-shot after the planned iommu=pt reboot (owner approved 2026-11-12 ~09:50): boot checks, health probe,
# peer benches (after), then gate tg105pt. Started by the user unit dsv41-postboot-pt (flag file below).
W=/home/steve/dsv41-work; O=$W/runs/pt; F=$W/pt/POSTBOOT_FLAG
rm -f $F
L=$O/postboot.log
{ echo "postboot start $(date '+%F %T')"; journalctl --list-boots --no-pager | tail -3; echo "cmdline: $(cat /proc/cmdline)"
  echo "card iommu domain: $(cat /sys/bus/pci/devices/0000:03:00.0/iommu_group/type)"
  echo "hardware error lines this boot: $(journalctl -b 0 -k -o cat | grep -c 'Hardware Error')"; } >> $L
rm -f $W/six.active; rm -f $W/locks/* 2>/dev/null
sleep 90
PO=$O/health-probe-pt.txt
touch $W/six.active
systemd-run --user --unit=probept --wait --collect -p WorkingDirectory=/home/steve/b70-optimization-lab \
  bash -c "timeout 600 scripts/check-qwen36-xpu-xccl-health.sh > $PO 2>&1; echo \"rc \$?\" >> $PO"
rm -f $W/six.active
echo "probe: $(tail -1 $PO) $(date +%T)" >> $L
grep -q "^rc 0" $PO || { echo "PROBE FAILED: stopping" >> $L; exit 1; }
$W/pt/pt-bench.sh after; echo "pt-bench after exit $? $(date +%T)" >> $L
systemd-run --user --unit=tg105pt --collect -p StandardOutput=file:$W/runs/tg105pt.unit.log -p StandardError=file:$W/runs/tg105pt.unit.log $W/tg105pt.sh
echo "tg105pt started $(date +%T)" >> $L
