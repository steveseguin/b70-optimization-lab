#!/bin/bash
# codex-freeze-heavy.sh <stop-file> [max-seconds]: during DEVICE-BOUND SCREENS (not record chains, not host-wait
# diagnostics, which keep the full freeze), freeze only Codex units that read model files (*.gguf, *.safetensors,
# /mnt/raid-models), run a compiler/linker, or exceed 4 GB; re-check every 20 s; thaw all when <stop-file> exists
# or max-seconds (default 7200) elapse. Review 42 rec 5 (2026-10-19).
STOP=$1; MAX=${2:-7200}; LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log; end=$(( $(date +%s) + MAX )); declare -A FROZEN
heavy(){ local cg; cg=/sys/fs/cgroup$(systemctl --user show -p ControlGroup --value "$1"); [ -d "$cg" ] || return 1
  [ "$(cat $cg/memory.current 2>/dev/null || echo 0)" -gt 4000000000 ] && { echo mem; return 0; }
  for p in $(cat $(find $cg -name cgroup.procs) 2>/dev/null); do
    case "$(cat /proc/$p/comm 2>/dev/null)" in icpx|icx|clang*|ld|ld.lld|ocloc|cc1plus|llvm-*) echo compile; return 0;; esac
    ls -l /proc/$p/fd 2>/dev/null | grep -qE '\.gguf|\.safetensors|/mnt/raid-models' && { echo model-read; return 0; }
  done; return 1; }
while [ ! -e "$STOP" ] && [ $(date +%s) -lt $end ]; do
  for u in $(systemctl --user list-units --state=active --no-legend 'codex-*' | sed 's/^●//' | awk '{print $1}'); do
    [ -n "${FROZEN[$u]:-}" ] && continue; why=$(heavy $u) && systemctl --user freeze $u && FROZEN[$u]=1 && echo "$(date -u +%T) freeze-heavy: froze $u ($why)" >> $LOG
  done; sleep 20; done
for u in "${!FROZEN[@]}"; do systemctl --user thaw $u 2>/dev/null; done; echo "$(date -u +%T) freeze-heavy: thawed ${!FROZEN[*]}" >> $LOG
