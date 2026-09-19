#!/usr/bin/env bash
#
# archive-bench-results.sh -- move campaign output directories older than CUTOFF that no script in the repo
# references out to cold storage, verified by a second rsync pass before removal.
#
# First run: 2026-09-19. 1,250 directories were selected; this pass archived 902 and left 348 that the
# user-level rsync could not read (container-written, root-owned caches inside) for the sudo pass --
# see archive-bench-results-sudo.sh. 0 verify mismatches.
#
# Selection method (the "reference list"):
#   candidates = directories in BENCH_DIR whose mtime is older than CUTOFF
#   referenced = every path that appears in experiments/*/scripts, packages/*/scripts and scripts/
#   archive    = comm -23 <(candidates) <(referenced)
# plus two hard keeps: anything matching KEEP_GLOBS (gpu-fault*, host-oom* -- incident evidence).
# Build the list with --build-list (it is written to LIST and printed); review it before running the move.
#
# Discipline: rsync -> dry-run rsync verify -> remove. Any directory whose verify pass still lists files is
# kept, and the run continues.
#
# Reuse:
#   DATE=20261101 CUTOFF=2026-10-25 ./archive-bench-results.sh --build-list
#   DATE=20261101 CUTOFF=2026-10-25 ./archive-bench-results.sh
#
set -u

DATE="${DATE:-20260919}"
CUTOFF="${CUTOFF:-2026-09-14}"          # dirs with an mtime older than this are candidates
COLD_ROOT="${COLD_ROOT:-/media/steve/extended-ssd/model-cold-storage}"
DEST="${DEST:-$COLD_ROOT/b70-host-$DATE/bench-results-pre-${CUTOFF//-/}}"
BENCH_DIR="${BENCH_DIR:-/mnt/fast-ai/bench-results}"
LIST="${LIST:-$BENCH_DIR/archive-bench-dirs-$DATE.txt}"
FAILED_LIST="${FAILED_LIST:-$BENCH_DIR/archive-failed-$DATE.txt}"
LOG="${LOG:-$BENCH_DIR/archive-bench-results-$DATE.log}"
SUDO_PW="${SUDO_PW:-/home/steve/SUDO_PASSWORD.txt}"   # lab convention; never printed
REPO_ROOT="${REPO_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
WAIT_UNIT="${WAIT_UNIT:-}"              # optional systemd --user unit to wait out first (same USB disk)
KEEP_GLOBS=('gpu-fault*' 'host-oom*')

build_list() {
    local tmp_c tmp_r
    tmp_c="$(mktemp)"; tmp_r="$(mktemp)"
    find "$BENCH_DIR" -mindepth 1 -maxdepth 1 -type d ! -newermt "$CUTOFF" -printf '%f\n' | sort > "$tmp_c"
    # Every bench-results directory name any runner still names. Grep the basenames out of the script trees.
    grep -rhoE '[A-Za-z0-9._/-]*bench-results/[A-Za-z0-9._-]+' \
        "$REPO_ROOT"/experiments/*/scripts "$REPO_ROOT"/packages/*/scripts "$REPO_ROOT"/scripts 2>/dev/null \
        | awk -F'bench-results/' '{print $2}' | sort -u > "$tmp_r"
    comm -23 "$tmp_c" "$tmp_r" > "$LIST"
    echo "candidates older than $CUTOFF: $(wc -l < "$tmp_c")"
    rm -f "$tmp_c" "$tmp_r"
    echo "to archive: $(wc -l < "$LIST")  ->  $LIST"
    echo "Review this list before running the move. Evidence dirs (${KEEP_GLOBS[*]}) are skipped at move time too."
}

if [ "${1:-}" = "--build-list" ]; then build_list; exit 0; fi
[ -s "$LIST" ] || { echo "No list at $LIST; run '$0 --build-list' first." >&2; exit 2; }

mkdir -p "$DEST"
if [ -n "$WAIT_UNIT" ]; then
    until ! systemctl --user is-active "$WAIT_UNIT" >/dev/null 2>&1; do sleep 30; done
fi

is_kept() {
    local d="$1" g
    for g in "${KEEP_GLOBS[@]}"; do
        # shellcheck disable=SC2053
        [[ "$d" == $g ]] && return 0
    done
    return 1
}

{
echo "$(date -Is) start; $(wc -l < "$LIST") dirs; dest $DEST"
: > "$FAILED_LIST"
cd "$BENCH_DIR" || exit 1
while read -r d; do
  [ -d "$d" ] || continue
  if is_kept "$d"; then echo "$(date -Is) keep evidence $d"; continue; fi
  rsync -a --no-inc-recursive "$d/" "$DEST/$d/" || { echo "$(date -Is) rsync FAILED $d; kept"; echo "$d" >> "$FAILED_LIST"; continue; }
  n=$(rsync -a -n -i "$d/" "$DEST/$d/" | grep -c "^>f" || true)
  if [ "$n" = 0 ]; then
    rm -rf -- "$d" 2>/dev/null
    # shellcheck disable=SC2024  # the redirect feeds sudo's OWN stdin, where -S reads the password
    if [ -e "$d" ] && [ -r "$SUDO_PW" ]; then sudo -S -p '' rm -rf -- "$d" < "$SUDO_PW" 2>/dev/null; fi
    if [ -e "$d" ]; then echo "$(date -Is) REMOVE FAILED $d (copy is safe in $DEST/$d)"; echo "$d" >> "$FAILED_LIST"
    else echo "$(date -Is) archived $d"; fi
  else
    echo "$(date -Is) VERIFY MISMATCH ($n) $d; kept"; echo "$d" >> "$FAILED_LIST"
  fi
done < "$LIST"
echo "$(date -Is) done; $(wc -l < "$FAILED_LIST") dir(s) left for the sudo pass -> $FAILED_LIST"
df -h "$BENCH_DIR" | tail -1
} >> "$LOG" 2>&1
