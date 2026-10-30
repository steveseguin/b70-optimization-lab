#!/usr/bin/env bash
# Merge the fixed-cost-2 lab changes onto the shared engine/src at HEAD (after the other agent's commit), file by file:
# new files are copied; changed files get a 3-way `git merge-file` (current HEAD content, base f10c30c4a, lab copy).
# Writes the merged files into the shared working tree and reports conflicts (exit 1 on any). CPU only.
set -eu
R=/home/steve/llm-optimizations; E=experiments/own-xpu-runtime/engine/src
BASE=/dev/shm/fc2-2026-10-30/base-f10c30c4a/$E; LAB=/dev/shm/fc2-2026-10-30/$E
cd "$R"
[ -z "$(git status --porcelain -- "$E")" ] || { echo "shared engine/src has uncommitted changes; refusing"; git status --short -- "$E"; exit 1; }
bad=0
while IFS= read -r f; do
  rel=${f#"$LAB/"}
  if [ ! -e "$BASE/$rel" ]; then cp "$LAB/$rel" "$E/$rel"; echo "new    $rel"; continue; fi
  cmp -s "$BASE/$rel" "$LAB/$rel" && continue
  if cmp -s "$BASE/$rel" "$E/$rel"; then cp "$LAB/$rel" "$E/$rel"; echo "copied $rel"; continue; fi
  tmp=$(mktemp); cp "$E/$rel" "$tmp"
  if git merge-file -L HEAD -L f10c30c4a -L fc2-lab "$tmp" "$BASE/$rel" "$LAB/$rel"; then cp "$tmp" "$E/$rel"; echo "merged $rel"
  else echo "CONFLICT $rel (left untouched; merge result in $tmp)"; bad=1; fi
done < <(find "$LAB" -type f | sort)
exit $bad
