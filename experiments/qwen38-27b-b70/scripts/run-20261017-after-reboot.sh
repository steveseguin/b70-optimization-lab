#!/usr/bin/env bash
# After the owner's reboot (2026-10-17: second GPU fault on boot 66541315..., notes/2026-10-17-context-lane-public-remeasure.md).
# Refuses to run on the faulted boot. Then: kernel log of this boot clean -> ONE bounded health probe -> kernel log still
# clean -> the fault latch moved aside -> campaign 28f = campaign 28e unchanged (repair task K32 2x, depth 5, one launch,
# tail), cards left empty at the end. Any failure stops here and says why; nothing is retried.
#   SUDO_ASKPASS=/path/to/askpass bash run-20261017-after-reboot.sh        (short; the campaign runs in its own unit)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
E=$LAB/experiments/qwen38-27b-b70
O=/mnt/fast-ai/bench-results/context-longrun-20261016
FAULTED_BOOT=66541315-49f1-41f7-af1d-4756d6b89c9c
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
faults() { sudo -A journalctl -k -b --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }

boot=$(cat /proc/sys/kernel/random/boot_id)
[[ $boot == "$FAULTED_BOOT" ]] && { say "still the faulted boot ($boot): the owner has not rebooted; nothing run"; exit 1; }
[[ -n $(faults) ]] && { say "fault lines on this boot already:"; faults | head -5; exit 1; }
[[ -n $(docker ps -q) ]] && { say "containers running:"; docker ps --format '{{.Names}} {{.Image}}'; exit 1; }
if systemctl is-active --quiet gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service; then
  # the Gemma units are enabled, so they start at boot; stop them only when asked, as the campaign runners do
  [[ ${ALLOW_GEMMA_STOP:-0} == 1 ]] || { say "Gemma LAN service is up (starts at boot); ALLOW_GEMMA_STOP=1 to stop it first"; exit 1; }
  say "stopping the Gemma service"
  sudo -A systemctl stop gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service
  for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || break; sleep 2; done
  pgrep -x llama-server >/dev/null && { say "llama-server still running; nothing run"; exit 1; }
  sleep 60   # quiet minute before the probe
  [[ -n $(faults) ]] && { say "fault line after stopping Gemma:"; faults | head -5; exit 1; }
fi
say "boot $boot, kernel log clean, cards free; MemAvailable $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"

PYTHON=$HOME/.venvs/vllm-xpu/bin/python timeout 200 "$LAB/scripts/check-qwen36-xpu-xccl-health.sh" > "$O/health-after-reboot-$(date +%Y%m%dT%H%M%S).log" 2>&1
rc=$?
(( rc == 0 )) || { say "health probe FAILED (rc $rc); stop and tell the owner"; exit 1; }
sleep 30
[[ -n $(faults) ]] && { say "fault line after the health probe; stop and tell the owner"; faults | head -5; exit 1; }
say "health probe passed, kernel log clean"

[[ -e $O/server/FAULT.json ]] && mv "$O/server/FAULT.json" "$O/server/FAULT-20261017-c28e.json"
systemctl --user reset-failed ctx-campaign28f 2>/dev/null
systemd-run --user --unit=ctx-campaign28f --collect -p WorkingDirectory=$E/scripts \
  -p StandardOutput=append:$O/c28f.log -p StandardError=append:$O/c28f.log -E SUDO_ASKPASS="$SUDO_ASKPASS" \
  -E RUN=c28f -E MTP=5 -E SEQS=1 -E ONE_LAUNCH=1 -E TAIL=1 -E EDIT=0 -E RESTORE=0 -E IDLE_MAX=5 -E QUEUE=$O/QUEUE28d.txt \
  /usr/bin/bash $E/scripts/longrun-campaign28.sh
say "campaign 28f launched (unit ctx-campaign28f, log $O/c28f.log)"
