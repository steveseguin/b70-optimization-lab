#!/usr/bin/env bash
#
# move-to-cold-storage.sh -- move model directories off the fast disk to an external cold-storage drive,
# verified by a second rsync pass before the source is removed.
#
# First run: 2026-09-19, after `scripts/disk-cleanup-20260919.sh --tier 0,1,2,3`, on the user's direction to
# keep only the Qwen3.8-27B FP8 and MiniMax-H3 lanes on /mnt/fast-ai. 17 directories, 0 mismatches.
# See notes/2026-09-19-disk-review.md and the README next to this script.
#
# Discipline (do not shortcut it): rsync -> verify with a dry-run rsync -> only then remove. A directory whose
# verify pass still lists files is KEPT, and the run continues; nothing is ever removed on an unverified copy.
#
# Reuse: set DATE (and, if needed, COLD_ROOT / DEST / LOG) and edit the two model lists below.
#
#   DATE=20261101 ./move-to-cold-storage.sh
#   DEST=/media/steve/other-disk/cold ./move-to-cold-storage.sh
#
set -u

DATE="${DATE:-20260919}"
COLD_ROOT="${COLD_ROOT:-/media/steve/extended-ssd/model-cold-storage}"
DEST="${DEST:-$COLD_ROOT/b70-host-$DATE}"
LOG="${LOG:-/mnt/fast-ai/bench-results/move-to-cold-storage-$DATE.log}"
FAST_MODELS_DIR="${FAST_MODELS_DIR:-/mnt/fast-ai/llm-models}"
ROOT_MODELS_DIR="${ROOT_MODELS_DIR:-/home/steve/llm-models}"
SUDO_PW="${SUDO_PW:-/home/steve/SUDO_PASSWORD.txt}"   # lab convention; never printed

# The 2026-09-19 lists. Everything NOT listed stayed on the fast disk: the FP8 lane, the INT4 lane and
# the MiniMax-H3 video lane.
FAST_MODELS=(
    nemotron-3.5-lightning-30b-a3b-udq4km
    qwen3.6-35b-a3b-int4-autoround-abhinand
    qwen3.6-27b-int4-autoround
    qwen3.6-27b-q8_0-gguf
    qwen3.6-27b-dflash-q8_0-gguf
    qwen36-27b-dflash-q8
    qwen35-9b-q8-gguf
    ornith-1.5-9b-q8
    lfm2.5-2.6b-q8
    qwen35-0.8b-q8-tp-probe
    qwen3.8-27b-gguf
    qwen3.8-27b-unsloth-gguf
)
ROOT_MODELS=(
    gemma4-26b-a4b-it-q8-gguf
    qwen35-9b-fp8-dynamic
    qwen35-9b-w4a16
    qwen35-4b-fp8-dynamic
    qwen35-4b-w4a16
)

mkdir -p "$DEST/llm-models-fast-ai" "$DEST/llm-models-root"

# remove_verified <path> -- remove as the user; retry as root when the tree holds container-written
# (root-owned) files. Only ever called after the verify pass has passed.
remove_verified() {
    local p="$1"
    rm -rf -- "$p" 2>/dev/null
    if [ -e "$p" ] && [ -r "$SUDO_PW" ]; then
        # shellcheck disable=SC2024  # the redirect feeds sudo's OWN stdin, where -S reads the password
        sudo -S -p '' rm -rf -- "$p" < "$SUDO_PW" 2>/dev/null
    fi
    [ -e "$p" ] && return 1
    return 0
}

move() {  # move <src-dir> <dest-parent>
  local src=$1 dst=$2 name n; name=$(basename "$src")
  [ -d "$src" ] || { echo "$(date -Is) skip (missing) $src"; return; }
  echo "$(date -Is) move $src -> $dst/$name ($(du -sh "$src" | cut -f1))"
  rsync -a --no-inc-recursive "$src/" "$dst/$name/" || { echo "$(date -Is) rsync FAILED for $src (rc=$?); source kept"; return; }
  # verification pass: nothing left to transfer means sizes and mtimes match
  n=$(rsync -a -n -i "$src/" "$dst/$name/" | grep -c "^>f" || true)
  if [ "$n" = 0 ]; then
    if remove_verified "$src"; then echo "$(date -Is) verified and removed $src"
    else echo "$(date -Is) verified but REMOVE FAILED for $src (copy is safe in $dst/$name)"; fi
  else
    echo "$(date -Is) VERIFY MISMATCH ($n files) for $src; source kept"
  fi
  df -h /mnt/fast-ai / | tail -n 2 | awk '{print "   "$6" "$4" free"}'
}

{
echo "$(date -Is) start; dest $DEST"
for m in "${FAST_MODELS[@]}";  do move "$FAST_MODELS_DIR/$m" "$DEST/llm-models-fast-ai"; done
for m in "${ROOT_MODELS[@]}";  do move "$ROOT_MODELS_DIR/$m" "$DEST/llm-models-root"; done
echo "$(date -Is) models done"
} >> "$LOG" 2>&1
