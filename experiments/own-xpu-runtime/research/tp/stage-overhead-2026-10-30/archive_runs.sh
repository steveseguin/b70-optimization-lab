#!/usr/bin/env bash
# Move finished run directories from /dev/shm to the RAID archive with a sha256 list; the source is removed only after
# every file's hash verifies at the destination. Small evidence files are first copied into the repo folder (evidence/).
# Usage: archive_runs.sh NAME RUN...
set -euo pipefail
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/stage-overhead-2026-10-30
A=/mnt/raid-models/ownrt-experiment-archives/2026-10-30
name=$1; shift
dst=$A/stage-overhead-runs-$name; mkdir -p "$dst"
for run in "$@"; do
  b=$(basename "$run"); r=$(ls -d "$run"/rank? | head -1); e="$D/evidence/$b"; mkdir -p "$e"
  cp "$run/summary.json" "$e/" 2>/dev/null || true; for f in timings.jsonl tp-exchange.json tp-exchange-sites.json tp-exchange-slots.json tp-replicate-compare.json tp-submit-thread.json tp-shape-probe.json; do
    if [ -f "$r/$f" ]; then cp "$r/$f" "$e/"; fi; done
  [ -d "$r/draft-final-state" ] && cp "$r"/draft-final-state/*exchange*.json "$e/" 2>/dev/null || true
  cp -r --preserve=timestamps "$run" "$dst/"  # not -a: the NTFS archive refuses POSIX ACLs (EPERM, cp exits 1)
done
( cd "$dst" && find . -type f ! -name '*.sha256' -print0 | sort -z | xargs -0 sha256sum ) > "$A/stage-overhead-runs-$name.sha256"
for run in "$@"; do b=$(basename "$run")
  ( cd "$(dirname "$run")" && find "$b" -type f -print0 | sort -z | xargs -0 sha256sum ) | sed "s#  #  ./#" > /tmp/claude-1000/so-src-$b.sha256 || true
  grep -F "  ./$b/" "$A/stage-overhead-runs-$name.sha256" | diff -q - /tmp/claude-1000/so-src-$b.sha256 >/dev/null && rm -rf "$run" && echo "archived $b" || echo "VERIFY FAILED $b (source kept)"
  rm -f /tmp/claude-1000/so-src-$b.sha256
done
