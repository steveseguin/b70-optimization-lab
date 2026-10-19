#!/bin/bash
# Review 35: after the packet58ah chain-b waiter thaws Codex, replace p151b with p151c (upper-bound finish) and launch p154 + p58aj.
LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log; log(){ echo "$(date -u +%T) post-58ahb $*" >> $LOG; }
n=$(wc -l < $LOG); dl=$(( $(date +%s) + 3600 ))
until tail -n +$((n+1)) $LOG | grep -q 'onecard-chain-quiet\[packet58ah-onecard-record\] \(codex thawed\|ALERT\|CHECK/ALERT\)'; do
  [ $(date +%s) -gt $dl ] && { log "deadline waiting for chain-b thaw; nothing launched"; exit 3; }; sleep 10; done
systemctl --user stop codex-p151b-201145.service; log "stopped codex-p151b (superseded by p151c)"
for n2 in p151c p154 p58aj; do systemd-run --user --unit=codex-$n2-$(date +%H%M%S) --property=Restart=no /usr/bin/bash /tmp/claude-1000/-home-steve/fn-run/codex-launch.sh $n2 >/dev/null 2>&1 && log "launched codex-$n2"; sleep 2; done
