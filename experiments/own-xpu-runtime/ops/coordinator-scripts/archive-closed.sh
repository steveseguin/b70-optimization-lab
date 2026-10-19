#!/bin/bash
# Archive UNTRACKED + IGNORED files of CLOSED packets to the RAID with a sha256 manifest; verify (tar -d) before removal; leave a tracked RESTORE-ARCHIVE.md.
set -u
cd /home/steve/llm-optimizations
D=/mnt/raid-models/own-xpu-runtime-archive/closed-packets-2026-10-19; mkdir -p $D
for p in "$@"; do
  P=experiments/own-xpu-runtime/stage2/$p
  { git ls-files --others --exclude-standard $P; git ls-files --others --ignored --exclude-standard $P; } | sort -u > $D/$p.files
  n=$(wc -l < $D/$p.files); [ "$n" -gt 0 ] || { echo "$p nothing"; continue; }
  nice -n 19 ionice -c3 xargs -d '\n' -a $D/$p.files sha256sum > $D/$p.sha256 2>/dev/null
  nice -n 19 ionice -c3 tar -cf $D/$p.tar -T $D/$p.files && nice -n 19 ionice -c3 tar -df $D/$p.tar >/dev/null 2>&1 || { echo "$p VERIFY FAILED; nothing removed"; continue; }
  sz=$(stat -c %s $D/$p.tar)
  xargs -d '\n' -a $D/$p.files rm -f; find $P -type d -empty -delete 2>/dev/null
  cat > $P/RESTORE-ARCHIVE.md <<EOT
# Archived untracked files ($(date -u +%F))

This packet is closed. Its untracked/ignored build outputs and device-run bulk ($n files, $sz bytes) were moved by the coordinator to
\`$D/$p.tar\` (verified with \`tar -d\` before removal). The file list is \`$p.files\` and sha256 manifest \`$p.sha256\` in the same folder.
Tracked files (sources, notes, committed summaries) are unchanged. Restore from the repository root:

\`\`\`bash
tar -xf $D/$p.tar
sha256sum -c $D/$p.sha256
\`\`\`
EOT
  echo "$p archived $n files $sz bytes"
done
