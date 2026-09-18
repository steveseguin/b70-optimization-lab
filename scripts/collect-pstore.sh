#!/bin/bash
# Archive kernel pstore (ERST/EFI) records after a host freeze and print the backtrace head.
# Reads /sys/fs/pstore with sudo (password file), copies every record into
# experiments/ltx25-b70/notes/pstore/<boot-id-of-THIS-boot>/, never deletes from pstore.
set -u
DEST=/home/steve/llm-optimizations/experiments/ltx25-b70/notes/pstore/$(cat /proc/sys/kernel/random/boot_id)
PW=/home/steve/SUDOPASSWORD.txt
records=$(sudo -S -p '' ls /sys/fs/pstore/ < $PW 2>/dev/null)
if [ -z "$records" ]; then echo "pstore: no records"; exit 0; fi
mkdir -p "$DEST"
for r in $records; do
  sudo -S -p '' cat "/sys/fs/pstore/$r" < $PW > "$DEST/$r" 2>/dev/null && echo "archived $r ($(wc -c < "$DEST/$r") bytes)"
done
echo "--- backtrace head:"
grep -hE "Kernel panic|hard LOCKUP|soft lockup|RIP:|Call Trace|xe_|guc_|intel_|Oops|BUG:" "$DEST"/* 2>/dev/null | head -25
