#!/bin/bash
# Launch p168 + p169 Codex when run-p58aq thaws Codex; launch p166b when codex-p166 exits (review 42 recs 1-3).
LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log; log(){ echo "$(date -u +%T) after-p58aq $*" >> $LOG; }
L=/tmp/claude-1000/-home-steve/fn-run/codex-launch2.sh; dl=$(( $(date +%s) + 3*3600 ))
until grep -q "run-p58aq codex thawed" $LOG; do [ $(date +%s) -gt $dl ] && { log "deadline waiting for thaw"; exit 3; }; sleep 15; done
for n in p168 p169; do U=codex-$n-$(date +%H%M%S); systemd-run --user --unit=$U /usr/bin/bash $L $n >/dev/null 2>&1; log "launched $U"; sleep 2; done
while systemctl --user is-active -q codex-p166-030831.service; do [ $(date +%s) -gt $dl ] && { log "deadline waiting for p166"; exit 3; }; sleep 20; done
U=codex-p166b-$(date +%H%M%S); systemd-run --user --unit=$U /usr/bin/bash $L p166b >/dev/null 2>&1; log "p166 exited; launched $U"
