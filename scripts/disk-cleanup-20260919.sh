#!/usr/bin/env bash
#
# disk-cleanup-20260919.sh -- tiered reclaim for the two-B70 host, per notes/2026-09-19-disk-review.md
#
#   ./scripts/disk-cleanup-20260919.sh --tier 0,1,2          # DRY RUN: prints what it would remove
#   ./scripts/disk-cleanup-20260919.sh --tier 0,1,2 --yes    # actually removes those tiers
#   ./scripts/disk-cleanup-20260919.sh --tier 4              # tier 4 only ever lists
#   ./scripts/disk-cleanup-20260919.sh --tier 4 --yes --model /mnt/fast-ai/llm-models/<dir>
#   ./scripts/disk-cleanup-20260919.sh --tier 5              # tier 5 only ever prints commands
#
# Without --yes nothing is removed: every path/image is printed with its size, the tier total, and the
# projected free space on both disks. With --yes only the selected tiers run, every action is logged with
# a timestamp to /mnt/fast-ai/bench-results/disk-cleanup-20260919.log, and `df -h` for both disks is
# printed before and after.
#
# Safety rules this script obeys (AGENTS.md):
#   * it never touches a running container and never kills anything by pattern;
#   * the FP8 service container (neural-fp8-*) may be up or down -- if it is up it is left strictly alone;
#   * it refuses to run at all when the host is short on memory or a GPU fault coredump is present;
#   * tiers 4 and 5 never delete on their own (tier 4 needs an explicit --model, tier 5 only prints).
#
set -uo pipefail

LOG_FILE=/mnt/fast-ai/bench-results/disk-cleanup-20260919.log
FAST_MOUNT=/mnt/fast-ai
ROOT_MOUNT=/
BUILDS_CUTOFF=2026-09-10          # /home/steve/builds/* older than this is a tier 2 candidate
CACHE_MIN_AGE_DAYS=2              # a bench-results cache younger than this is kept (tier 1)
INCOMPLETE_MIN_MB=100             # only *.incomplete files above this are tier 0 candidates
VLLM_CACHE_KEEP_RECENT=2          # see the note in tier 1 about the per-state compile cache

# Tier 3 keep list, by image id (resolved to full ids at run time). Five package pins, the pristine base,
# the r312c parent, the r312d-a/b builders and the r312d-b multiq image.
KEEP_ID_PREFIXES=(
    521eb277   # R276 package pin
    7cd7bb16   # R304 package pin
    eb816507   # R310 package pin (fp8-tp2)
    7baa32bd   # R311b package pin
    ea61e698   # R312d-c package pin (fp8-tp1, the shipped one-card lane)
    96db42e2   # pristine vllm/vllm-openai-xpu:latest
    4f3d5bb8   # r312c parent
    a9a6dcd2   # neural-download/vllm-xpu-kernels-builder:r312d-a
    283311ab   # neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r312d-b-multiq
)
KEEP_TAGS=(
    'neural-download/vllm-xpu-kernels-builder:r312d-b'
    'gemma4-26b-q8-record:oneapi-2026.0-b9769'
)

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

APPLY=0
TIERS=""
MODEL_DIR=""

usage() {
    sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --tier)   TIERS="${2:-}"; shift 2 || usage 2 ;;
        --tier=*) TIERS="${1#--tier=}"; shift ;;
        --yes)    APPLY=1; shift ;;
        --model)   MODEL_DIR="${2:-}"; shift 2 || usage 2 ;;
        --model=*) MODEL_DIR="${1#--model=}"; shift ;;
        -h|--help) usage 0 ;;
        *) echo "Unknown argument: $1" >&2; usage 2 ;;
    esac
done

[ -n "$TIERS" ] || { echo "Nothing to do: pass --tier N[,N...]" >&2; usage 2; }

SELECTED=()
IFS=',' read -r -a _raw_tiers <<< "$TIERS"
for t in "${_raw_tiers[@]}"; do
    t="${t// /}"
    [ -n "$t" ] || continue
    case "$t" in
        0|1|2|3|4|5) SELECTED+=("$t") ;;
        *) echo "Unknown tier: $t (valid: 0 1 2 3 4 5)" >&2; exit 2 ;;
    esac
done
[ ${#SELECTED[@]} -gt 0 ] || { echo "Nothing to do: --tier listed no valid tier" >&2; exit 2; }

tier_selected() {
    local want="$1" t
    for t in "${SELECTED[@]}"; do [ "$t" = "$want" ] && return 0; done
    return 1
}

# ---------------------------------------------------------------------------- output helpers

MODE_LABEL="DRY RUN (nothing will be removed)"
[ "$APPLY" -eq 1 ] && MODE_LABEL="APPLY (removals are real)"

ts() { date '+%Y-%m-%dT%H:%M:%S%z'; }

log() {
    # Prints to stdout; in apply mode also appends a timestamped line to the log file.
    printf '%s\n' "$*"
    if [ "$APPLY" -eq 1 ] && [ -n "${LOG_READY:-}" ]; then
        printf '%s %s\n' "$(ts)" "$*" >> "$LOG_FILE"
    fi
}

human() {
    # bytes -> human string
    local b="${1:-0}"
    awk -v b="$b" 'BEGIN{
        split("B KiB MiB GiB TiB", u, " "); i=1;
        while (b >= 1024 && i < 5) { b /= 1024; i++ }
        if (i == 1) printf "%d %s", b, u[i]; else printf "%.2f %s", b, u[i];
    }'
}

avail_bytes() { df -B1 --output=avail "$1" 2>/dev/null | tail -1 | tr -d ' '; }

# ---------------------------------------------------------------------------- preflight

preflight() {
    local mem_kb coredumps
    mem_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
    if [ -z "$mem_kb" ] || [ "$mem_kb" -lt $((2 * 1024 * 1024)) ]; then
        echo "REFUSING: MemAvailable is $((mem_kb / 1024)) MiB, below the 2 GiB floor." >&2
        exit 3
    fi
    coredumps="$(ls -d /sys/class/drm/card*/device/devcoredump/data 2>/dev/null)"
    if [ -n "$coredumps" ]; then
        echo "REFUSING: a GPU fault halt marker is present -- a device coredump is waiting to be collected:" >&2
        printf '  %s\n' $coredumps >&2
        echo "Collect and record it first (AGENTS.md fault-halt rule); do not clean up over an open fault." >&2
        exit 3
    fi
    if ! command -v docker >/dev/null 2>&1; then
        echo "REFUSING: docker is not on PATH; tiers 0 and 3 cannot be evaluated safely." >&2
        exit 3
    fi
    echo "Preflight OK: MemAvailable $((mem_kb / 1024)) MiB, no GPU devcoredump present."
}

# Running containers: never touched, and their images are never removed.
RUNNING_IDS=""
RUNNING_IMAGES=""
FOREIGN_RUNNING=""
survey_containers() {
    local line cid cname cimage
    RUNNING_IDS=""; RUNNING_IMAGES=""; FOREIGN_RUNNING=""
    while IFS=$'\t' read -r cid cname cimage; do
        [ -n "$cid" ] || continue
        RUNNING_IDS+="$cid"$'\n'
        RUNNING_IMAGES+="$cimage"$'\n'
        case "$cname" in
            neural-fp8-*) echo "  running: $cname ($cid) -- the FP8 service; left strictly alone." ;;
            *) FOREIGN_RUNNING+="$cname ($cid)"$'\n'
               echo "  running: $cname ($cid) -- NOT the FP8 service." ;;
        esac
    done < <(docker ps --no-trunc --format '{{.ID}}\t{{.Names}}\t{{.Image}}' 2>/dev/null)
    if [ -z "$RUNNING_IDS" ]; then
        echo "  no containers are running."
    fi
}

# ---------------------------------------------------------------------------- plan bookkeeping

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/disk-cleanup-20260919.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT
PLAN="$WORKDIR/plan"                 # tier<TAB>disk<TAB>bytes<TAB>path
IMAGE_PLAN="$WORKDIR/image-plan"     # tier<TAB>family<TAB>repo:tag<TAB>id
DOCKER_IMAGES="$WORKDIR/docker-images"   # the `docker images` dump; must NOT be the plan file
: > "$PLAN"; : > "$IMAGE_PLAN"

ALLOWED_PREFIXES=()

disk_of() {
    case "$1" in
        "$FAST_MOUNT"/*) echo fast ;;
        *) echo root ;;
    esac
}

# add_target <path> -- validate, size, and record. Refuses anything outside ALLOWED_PREFIXES.
add_target() {
    local p="$1" ok=0 pref depth
    case "$p" in
        /*) : ;;
        *) echo "  SKIP (not absolute): $p" >&2; return 1 ;;
    esac
    [ -e "$p" ] || return 1
    if [ -L "$p" ]; then echo "  SKIP (symlink): $p" >&2; return 1; fi
    depth="$(awk -F/ '{print NF-1}' <<< "${p%/}")"
    if [ "$depth" -lt 2 ]; then echo "  SKIP (too shallow): $p" >&2; return 1; fi
    if mountpoint -q -- "$p" 2>/dev/null; then echo "  SKIP (mount point): $p" >&2; return 1; fi
    for pref in "${ALLOWED_PREFIXES[@]}"; do
        case "$p" in "$pref"*) ok=1; break ;; esac
    done
    if [ "$ok" -ne 1 ]; then echo "  SKIP (outside this tier's allowed roots): $p" >&2; return 1; fi
    printf '%s\n' "$p" >> "$WORKDIR/pending.$CURRENT_TIER"
    return 0
}

# flush_pending <tier> -- size every pending path in one du pass and append to the plan. The count is
# verified: anything du did not size is sized individually, so a tier is never quietly under-reported.
flush_pending() {
    local tier="$1" f="$WORKDIR/pending.$1" out="$WORKDIR/sizes.$1" err="$WORKDIR/du-err.$1"
    local bytes path want got
    [ -s "$f" ] || { rm -f "$f"; return 0; }
    want="$(wc -l < "$f")"
    : > "$out"
    if ! tr '\n' '\0' < "$f" | du -sb --files0-from=- > "$out" 2>"$err"; then
        echo "  NOTE: du reported a problem while sizing tier $tier:" >&2
        sed 's/^/    du: /' "$err" >&2
    fi
    got="$(wc -l < "$out")"
    if [ "$got" -ne "$want" ]; then
        echo "  NOTE: du sized $got of $want tier-$tier path(s); sizing the remainder one at a time." >&2
        cut -f2- "$out" > "$WORKDIR/sized.$tier"
        while IFS= read -r path; do
            grep -qxF -- "$path" "$WORKDIR/sized.$tier" && continue
            bytes="$(du -sb -- "$path" 2>/dev/null | cut -f1)"
            printf '%s\t%s\n' "${bytes:-0}" "$path" >> "$out"
        done < "$f"
        rm -f "$WORKDIR/sized.$tier"
    fi
    while IFS=$'\t' read -r bytes path; do
        [ -n "$path" ] || continue
        printf '%s\t%s\t%s\t%s\n' "$tier" "$(disk_of "$path")" "$bytes" "$path" >> "$PLAN"
    done < "$out"
    rm -f "$f" "$out" "$err"
}

# ---------------------------------------------------------------------------- tier 0: safe

tier0_docker_prune() {
    local exited created
    if [ -n "$FOREIGN_RUNNING" ]; then
        log "TIER 0: REFUSED -- a container that is not the FP8 service is running:"
        log "$(printf '  %s\n' $FOREIGN_RUNNING)"
        log "TIER 0: skipping both prunes. Nothing was touched."
        return 1
    fi
    exited="$(docker ps -a --filter status=exited -q 2>/dev/null | wc -l)"
    created="$(docker ps -a --filter status=created -q 2>/dev/null | wc -l)"
    log "TIER 0: docker container prune -f  -- $exited exited + $created created containers (running ones are never pruned)"
    log "TIER 0: docker image prune -f      -- dangling images only"
    if [ "$APPLY" -eq 1 ]; then
        log "TIER 0: running docker container prune -f"
        docker container prune -f 2>&1 | while IFS= read -r l; do log "    $l"; done
        log "TIER 0: running docker image prune -f"
        docker image prune -f 2>&1 | while IFS= read -r l; do log "    $l"; done
        log "TIER 0: df -h / after the docker prunes:"
        df -h "$ROOT_MOUNT" | while IFS= read -r l; do log "    $l"; done
    fi
    return 0
}

plan_tier0() {
    CURRENT_TIER=0
    ALLOWED_PREFIXES=("$FAST_MOUNT/")
    local p
    while IFS= read -r p; do
        add_target "$p"
    done < <(find "$FAST_MOUNT" -xdev -type f -name '*.incomplete' -size +"${INCOMPLETE_MIN_MB}"M 2>/dev/null)
    [ -d "$FAST_MOUNT/vllm-cache-exp" ] && add_target "$FAST_MOUNT/vllm-cache-exp"
    flush_pending 0
}

# ---------------------------------------------------------------------------- tier 1: caches

# A bench-results cache is kept when its state dir is live (state.json status ready/starting) or when the
# cache itself is younger than CACHE_MIN_AGE_DAYS.
state_status() {
    local sj="$1"
    [ -f "$sj" ] || { echo ""; return; }
    python3 - "$sj" <<'PY' 2>/dev/null || echo "unreadable"
import json, sys
try:
    print(json.load(open(sys.argv[1])).get('status', ''))
except Exception:
    print('unreadable')
PY
}

plan_tier1() {
    CURRENT_TIER=1
    ALLOWED_PREFIXES=("$FAST_MOUNT/bench-results/" "$FAST_MOUNT/vllm-cache/")
    local c parent status kept_live=0 kept_fresh=0 d n=0

    while IFS= read -r c; do
        parent="$(dirname "$c")"
        status="$(state_status "$parent/state.json")"
        case "$status" in
            ready|starting)
                kept_live=$((kept_live + 1))
                echo "  keep (state.json status=$status, a live server): $c"
                continue ;;
        esac
        if [ -n "$(find "$c" -maxdepth 0 -mtime -"$CACHE_MIN_AGE_DAYS" 2>/dev/null)" ]; then
            kept_fresh=$((kept_fresh + 1))
            echo "  keep (younger than ${CACHE_MIN_AGE_DAYS} days): $c"
            continue
        fi
        add_target "$c"
    done < <(find "$FAST_MOUNT/bench-results" -maxdepth 4 -type d -name cache 2>/dev/null)
    echo "  tier 1: kept $kept_live live-server cache(s) and $kept_fresh cache(s) newer than ${CACHE_MIN_AGE_DAYS} days."

    # vllm-cache: NOTE -- neither live package mounts /mnt/fast-ai/vllm-cache. Both FP8 launchers
    # (packages/qwen38-27b-fp8-tp{1,2}-b70/scripts/serve.py) bind-mount a PER-STATE cache,
    # "<state-dir>/cache" -> /root/.cache/vllm, created fresh by `serve.py start`. So no tag here is
    # live, and per the review note the two most recent dirs are kept anyway as a margin.
    if [ -d "$FAST_MOUNT/vllm-cache" ]; then
        echo "  tier 1: the live FP8 packages mount <state-dir>/cache, not $FAST_MOUNT/vllm-cache;"
        echo "          keeping the $VLLM_CACHE_KEEP_RECENT most recent $FAST_MOUNT/vllm-cache entries as a margin."
        while IFS= read -r d; do
            n=$((n + 1))
            if [ "$n" -le "$VLLM_CACHE_KEEP_RECENT" ]; then
                echo "  keep (one of the $VLLM_CACHE_KEEP_RECENT most recent): $d"
                continue
            fi
            add_target "$d"
        done < <(ls -1dt "$FAST_MOUNT"/vllm-cache/* 2>/dev/null)
    fi
    flush_pending 1
}

# ---------------------------------------------------------------------------- tier 2: build trees

BUILD_KEEP_GLOBS=('kernels-*' 'cutlass-sycl' 'diffusers-src' 'sycl-tla-87f6850' 'r312d-builder')

build_is_kept() {
    local base="$1" g
    for g in "${BUILD_KEEP_GLOBS[@]}"; do
        # shellcheck disable=SC2053
        [[ "$base" == $g ]] && return 0
    done
    return 1
}

plan_tier2() {
    CURRENT_TIER=2
    ALLOWED_PREFIXES=("$FAST_MOUNT/src/" "$FAST_MOUNT/build/" "$FAST_MOUNT/artifacts" "/home/steve/builds/")
    local p base

    # a) /mnt/fast-ai/src/<worktree>/build*  -- objects only, the sources stay
    while IFS= read -r p; do add_target "$p"; done \
        < <(find "$FAST_MOUNT/src" -mindepth 2 -maxdepth 2 -type d -name 'build*' 2>/dev/null)

    # b) /mnt/fast-ai/build/qwen38-* trees, with the keep list guarded explicitly
    while IFS= read -r p; do
        base="$(basename "$p")"
        if build_is_kept "$base"; then echo "  keep (build keep list): $p"; continue; fi
        add_target "$p"
    done < <(find "$FAST_MOUNT/build" -mindepth 1 -maxdepth 1 -type d -name 'qwen38-*' 2>/dev/null)

    # c) the August q8 kernel artifacts
    [ -d "$FAST_MOUNT/artifacts" ] && add_target "$FAST_MOUNT/artifacts"

    # d) /home/steve/builds/* older than the cutoff
    while IFS= read -r p; do add_target "$p"; done \
        < <(find /home/steve/builds -mindepth 1 -maxdepth 1 ! -newermt "$BUILDS_CUTOFF" 2>/dev/null)

    flush_pending 2
}

# ---------------------------------------------------------------------------- tier 3: research images

KEEP_IDS_FILE=""

resolve_keep_ids() {
    local pfx tag id
    KEEP_IDS_FILE="$WORKDIR/keep-ids"
    : > "$KEEP_IDS_FILE"
    docker images --no-trunc --format '{{.Repository}}:{{.Tag}}\t{{.ID}}' 2>/dev/null > "$DOCKER_IMAGES"

    for pfx in "${KEEP_ID_PREFIXES[@]}"; do
        id="$(awk -F'\t' -v p="sha256:$pfx" 'index($2, p) == 1 {print $2}' "$DOCKER_IMAGES" | sort -u | head -1)"
        if [ -z "$id" ]; then
            echo "  keep-list id $pfx... is not present locally (nothing to protect)."
        else
            echo "$id" >> "$KEEP_IDS_FILE"
        fi
    done
    for tag in "${KEEP_TAGS[@]}"; do
        id="$(awk -F'\t' -v t="$tag" '$1 == t {print $2}' "$DOCKER_IMAGES" | head -1)"
        [ -n "$id" ] && echo "$id" >> "$KEEP_IDS_FILE"
    done

    # Every image referenced by a package launcher or manifest.
    while IFS= read -r id; do
        [ -n "$id" ] && echo "$id" >> "$KEEP_IDS_FILE"
    done < <(
        {
            grep -rhoE 'sha256:[0-9a-f]{64}' "$REPO_ROOT"/packages/*/scripts/serve.py "$REPO_ROOT"/packages/*/package.json 2>/dev/null
            # tags named by a package, resolved to their local ids
            while IFS= read -r t; do
                awk -F'\t' -v t="$t" '$1 == t {print $2}' "$DOCKER_IMAGES"
            done < <(grep -rhoE '(neural-download|rebase|cleanclone|upstream-repro|prefill)/[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+' \
                        "$REPO_ROOT"/packages/*/scripts/serve.py "$REPO_ROOT"/packages/*/package.json 2>/dev/null | sort -u)
        } | sort -u
    )

    # Every image used by a running container.
    while IFS= read -r id; do
        [ -n "$id" ] && echo "$id" >> "$KEEP_IDS_FILE"
    done < <(docker ps --no-trunc --format '{{.Image}}' 2>/dev/null | while IFS= read -r img; do
                docker image inspect --format '{{.Id}}' "$img" 2>/dev/null
             done)

    sort -u -o "$KEEP_IDS_FILE" "$KEEP_IDS_FILE"
    echo "  tier 3 keep list resolves to $(wc -l < "$KEEP_IDS_FILE") image id(s)."
}

family_of() {
    case "$1" in
        neural-download/*) echo "neural-download" ;;
        rebase/*) echo "rebase" ;;
        upstream-repro/*) echo "upstream-repro" ;;
        cleanclone/*) echo "cleanclone" ;;
        *) echo "other" ;;
    esac
}

plan_tier3() {
    resolve_keep_ids
    local tag id fam
    while IFS=$'\t' read -r tag id; do
        [ -n "$tag" ] || continue
        case "$tag" in
            *:'<none>') continue ;;   # dangling; tier 0's image prune owns those
        esac
        # families in scope
        if [[ "$tag" =~ ^neural-download/vllm-openai-xpu:.*-r[0-9]+ ]] \
           || [[ "$tag" == rebase/* ]] || [[ "$tag" == upstream-repro/* ]] || [[ "$tag" == cleanclone/* ]]; then
            if grep -qxF "$id" "$KEEP_IDS_FILE"; then
                continue
            fi
            fam="$(family_of "$tag")"
            printf '3\t%s\t%s\t%s\n' "$fam" "$tag" "$id" >> "$IMAGE_PLAN"
        fi
    done < "$DOCKER_IMAGES"
}

report_tier3() {
    local fam n total ids
    if [ ! -s "$IMAGE_PLAN" ]; then
        log "TIER 3: nothing matches -- no research image outside the keep list."
        return 0
    fi
    total="$(wc -l < "$IMAGE_PLAN")"
    ids="$(awk -F'\t' '{print $4}' "$IMAGE_PLAN" | sort -u | wc -l)"
    log "TIER 3: $total tag(s) covering $ids distinct image(s), grouped by family:"
    while IFS= read -r fam; do
        n="$(awk -F'\t' -v f="$fam" '$2 == f' "$IMAGE_PLAN" | wc -l)"
        log "  --- family $fam ($n tag(s)) ---"
        awk -F'\t' -v f="$fam" '$2 == f {printf "      %s  %s\n", $3, substr($4, 1, 19)}' "$IMAGE_PLAN" \
            | while IFS= read -r l; do log "$l"; done
    done < <(awk -F'\t' '{print $2}' "$IMAGE_PLAN" | sort -u)
    log "TIER 3: size cannot be projected -- with the containerd snapshotter these images share base layers and"
    log "        \`docker system df\` mis-reports them; the real reclaim is measured by df after each family."
    log "TIER 3: images kept: the five package pins, the pristine base, the r312c parent, the r312d-a/b builders,"
    log "        gemma4-26b-q8-record:oneapi-2026.0-b9769, anything a package references, anything a running container uses."

    if [ "$APPLY" -eq 1 ]; then
        while IFS= read -r fam; do
            log "TIER 3: removing family $fam"
            while IFS=$'\t' read -r _ _ tag _; do
                log "  docker rmi $tag"
                # No -f: an image still referenced by a container is left alone rather than forced out.
                docker rmi "$tag" 2>&1 | while IFS= read -r l; do log "      $l"; done
            done < <(awk -F'\t' -v f="$fam" '$2 == f' "$IMAGE_PLAN")
            log "TIER 3: df -h / after family $fam:"
            df -h "$ROOT_MOUNT" | while IFS= read -r l; do log "    $l"; done
        done < <(awk -F'\t' '{print $2}' "$IMAGE_PLAN" | sort -u)
    fi
}

# ---------------------------------------------------------------------------- tier 4: models (listing only)

TIER4_CANDIDATES=(
    "$FAST_MOUNT/llm-models/minimax-h3/transformer"
    "$FAST_MOUNT/llm-models/nemotron-3.5-lightning-30b-a3b-udq4km"
    "$FAST_MOUNT/llm-models/qwen3.6-35b-a3b-int4-autoround-abhinand"
    "$FAST_MOUNT/llm-models/qwen3.6-27b-int4-autoround"
    "$FAST_MOUNT/llm-models/qwen35-9b-q8-gguf"
    "$FAST_MOUNT/llm-models/ornith-1.5-9b-q8"
    "/home/steve/llm-models/gemma4-26b-a4b-it-q8-gguf"
    "/home/steve/llm-models/qwen35-9b-fp8-dynamic"
    "/home/steve/llm-models/qwen35-9b-w4a16"
    "/home/steve/llm-models/qwen35-4b-fp8-dynamic"
    "/home/steve/llm-models/qwen35-4b-w4a16"
)

tier4() {
    local p present=() bytes line
    log "TIER 4 (models -- user decision). This tier NEVER deletes on its own; it lists."
    log "  Candidates from notes/2026-09-19-disk-review.md:"
    for p in "${TIER4_CANDIDATES[@]}"; do
        [ -d "$p" ] || { log "    (absent)  $p"; continue; }
        present+=("$p")
    done
    if [ ${#present[@]} -gt 0 ]; then
        while IFS=$'\t' read -r bytes p; do
            log "    $(printf '%10s' "$(human "$bytes")")  $p"
        done < <(du -sb -- "${present[@]}" 2>/dev/null)
    fi
    log "  Caveats that still stand:"
    log "    * minimax-h3/transformer is the BF16 reference the exactness checks read; keep it until the video"
    log "      lane has a good clip and the int8 comparison is done (CURRENT.md decision 3)."
    log "    * qwen3.8-27b-int4-autoround is NOT listed here: the INT4 lane's relabel dir sits next to it;"
    log "      check the package before touching either."
    log "    * the /home/steve/llm-models set backs the Qwen3.5 quick lanes and the Gemma container lane."
    log "  To delete exactly one of these, name it:"
    log "    $0 --tier 4 --yes --model <dir>"

    if [ "$APPLY" -eq 1 ]; then
        if [ -z "$MODEL_DIR" ]; then
            log "TIER 4: --yes given without --model; nothing deleted (this is the designed behaviour)."
            return 0
        fi
        local target ok=0
        target="$(cd -- "$MODEL_DIR" 2>/dev/null && pwd)"
        if [ -z "$target" ]; then
            log "TIER 4: REFUSED -- --model $MODEL_DIR is not an existing directory."
            return 1
        fi
        for p in "${TIER4_CANDIDATES[@]}"; do [ "$p" = "$target" ] && ok=1; done
        if [ "$ok" -ne 1 ]; then
            log "TIER 4: REFUSED -- $target is not in the candidate list from the review note."
            return 1
        fi
        bytes="$(du -sb -- "$target" 2>/dev/null | cut -f1)"
        log "TIER 4: deleting $target ($(human "${bytes:-0}"))"
        rm -rf --one-file-system -- "$target"
        log "TIER 4: done; df -h:"
        df -h "$FAST_MOUNT" "$ROOT_MOUNT" | while IFS= read -r line; do log "    $line"; done
    fi
}

# ---------------------------------------------------------------------------- tier 5: swap (print only)

tier5() {
    local used
    used="$(awk '/swapfile-b70/ {print $4}' /proc/swaps 2>/dev/null)"
    log "TIER 5 (swap). This script NEVER executes any of this -- it prints the commands for you to run by hand."
    log "  $FAST_MOUNT/swapfile-b70 is active at priority 10; currently ${used:-unknown} KiB in use."
    log "  Shrinking it from 32 GiB to 8 GiB frees 24 GiB on $FAST_MOUNT. Do it on a quiet host, with enough"
    log "  free RAM to absorb whatever is paged out, and update /etc/fstab in the same sitting."
    log ""
    log "    sudo swapoff $FAST_MOUNT/swapfile-b70"
    log "    sudo rm -f $FAST_MOUNT/swapfile-b70"
    log "    sudo fallocate -l 8G $FAST_MOUNT/swapfile-b70"
    log "    sudo chmod 600 $FAST_MOUNT/swapfile-b70"
    log "    sudo mkswap $FAST_MOUNT/swapfile-b70"
    log "    sudo swapon --priority 10 $FAST_MOUNT/swapfile-b70"
    log "    swapon --show"
    log ""
    log "  The /etc/fstab line (replace the existing swapfile-b70 entry; size is not in the line, so it only"
    log "  needs to be present and correct):"
    log "    $FAST_MOUNT/swapfile-b70  none  swap  sw,pri=10  0  0"
    log ""
    log "  AGENTS.md note: the user asked that swap and page-cache settings be left alone for the stability"
    log "  effort, so treat this tier as a proposal that needs an explicit go-ahead, not routine housekeeping."
}

# ---------------------------------------------------------------------------- reporting / commit

report_paths() {
    local tier="$1" bytes path disk n=0 sum=0 fast=0 root=0 line rows
    # NOTE: do not pipe this into `grep -q` -- grep exits on the first match, awk takes SIGPIPE, and under
    # `set -o pipefail` the pipeline then reports failure for a *large* tier only, which silently turned a
    # 507-path tier into "no matching path" once. Count with awk itself instead.
    rows="$(awk -F'\t' -v t="$tier" '$1 == t {n++} END {print n+0}' "$PLAN")"
    if [ "$rows" -eq 0 ]; then
        log "TIER $tier: no matching path."
        return 0
    fi
    log "TIER $tier: paths to remove"
    while IFS=$'\t' read -r _ disk bytes path; do
        n=$((n + 1)); sum=$((sum + bytes))
        [ "$disk" = fast ] && fast=$((fast + bytes)) || root=$((root + bytes))
        log "    $(printf '%10s' "$(human "$bytes")")  $path"
    done < <(awk -F'\t' -v t="$tier" '$1 == t' "$PLAN" | sort -t$'\t' -k3,3nr)
    log "TIER $tier TOTAL: $n path(s), $(human "$sum")  [$FAST_MOUNT: $(human "$fast") | $ROOT_MOUNT: $(human "$root")]"
    printf '%s\t%s\t%s\n' "$tier" "$fast" "$root" >> "$WORKDIR/tier-totals"
}

apply_paths() {
    local tier="$1" bytes path n=0
    while IFS=$'\t' read -r _ _ bytes path; do
        [ -n "$path" ] || continue
        n=$((n + 1))
        log "TIER $tier: rm -rf $path ($(human "$bytes"))"
        rm -rf --one-file-system -- "$path"
        if [ -e "$path" ]; then
            log "TIER $tier: WARNING -- $path still exists after removal"
        fi
    done < <(awk -F'\t' -v t="$tier" '$1 == t' "$PLAN")
    log "TIER $tier: removed $n path(s)."
}

# ---------------------------------------------------------------------------- main

echo "=============================================================================="
echo " disk-cleanup-20260919  --  $MODE_LABEL"
echo " tiers: ${SELECTED[*]}     host: $(hostname)     $(ts)"
echo "=============================================================================="
preflight
echo
echo "Containers:"
survey_containers
echo

if [ "$APPLY" -eq 1 ]; then
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null
    if : >> "$LOG_FILE" 2>/dev/null; then
        LOG_READY=1
        printf '%s ===== disk-cleanup-20260919 start, tiers %s, pid %s =====\n' "$(ts)" "${SELECTED[*]}" "$$" >> "$LOG_FILE"
    else
        echo "REFUSING: cannot write the log at $LOG_FILE; apply mode must be logged." >&2
        exit 4
    fi
    echo "df -h BEFORE:"
    df -h "$FAST_MOUNT" "$ROOT_MOUNT" | while IFS= read -r l; do log "    $l"; done
    echo
fi

FAST_AVAIL_BEFORE="$(avail_bytes "$FAST_MOUNT")"
ROOT_AVAIL_BEFORE="$(avail_bytes "$ROOT_MOUNT")"
: > "$WORKDIR/tier-totals"

TIER0_OK=1
if tier_selected 0; then
    echo "--- tier 0: safe (docker prunes, orphan downloads, the May compile-size experiments) ---"
    tier0_docker_prune || TIER0_OK=0
    if [ "$TIER0_OK" -eq 1 ]; then
        plan_tier0
        report_paths 0
        [ "$APPLY" -eq 1 ] && apply_paths 0
    fi
    echo
fi

if tier_selected 1; then
    echo "--- tier 1: caches (torch-compile caches under bench-results, and vllm-cache) ---"
    plan_tier1
    report_paths 1
    [ "$APPLY" -eq 1 ] && apply_paths 1
    echo
fi

if tier_selected 2; then
    echo "--- tier 2: build trees (rebuildable objects; sources are kept) ---"
    plan_tier2
    report_paths 2
    [ "$APPLY" -eq 1 ] && apply_paths 2
    echo
fi

if tier_selected 3; then
    echo "--- tier 3: research images ---"
    plan_tier3
    report_tier3
    echo
fi

if tier_selected 4; then
    echo "--- tier 4: models ---"
    tier4
    echo
fi

if tier_selected 5; then
    echo "--- tier 5: swap ---"
    tier5
    echo
fi

# ---------------------------------------------------------------------------- summary

GRAND_FAST=0; GRAND_ROOT=0
if [ -s "$WORKDIR/tier-totals" ]; then
    GRAND_FAST="$(awk -F'\t' '{s+=$2} END{print s+0}' "$WORKDIR/tier-totals")"
    GRAND_ROOT="$(awk -F'\t' '{s+=$3} END{print s+0}' "$WORKDIR/tier-totals")"
fi

echo "=============================================================================="
if [ "$APPLY" -eq 1 ]; then
    log "df -h AFTER:"
    df -h "$FAST_MOUNT" "$ROOT_MOUNT" | while IFS= read -r l; do log "    $l"; done
    log "Freed on $FAST_MOUNT: $(human $(( $(avail_bytes "$FAST_MOUNT") - FAST_AVAIL_BEFORE )) )"
    log "Freed on $ROOT_MOUNT: $(human $(( $(avail_bytes "$ROOT_MOUNT") - ROOT_AVAIL_BEFORE )) )"
    printf '%s ===== disk-cleanup-20260919 end =====\n' "$(ts)" >> "$LOG_FILE"
    echo "Log: $LOG_FILE"
else
    echo " DRY RUN SUMMARY -- tiers ${SELECTED[*]}"
    while IFS=$'\t' read -r t f r; do
        printf '   tier %s: %s on %s, %s on %s\n' "$t" "$(human "$f")" "$FAST_MOUNT" "$(human "$r")" "$ROOT_MOUNT"
    done < "$WORKDIR/tier-totals"
    if [ -s "$IMAGE_PLAN" ]; then
        printf '   tier 3: %s tag(s) / %s image(s) on %s, size not projectable (containerd snapshotter)\n' \
            "$(wc -l < "$IMAGE_PLAN")" "$(awk -F'\t' '{print $4}' "$IMAGE_PLAN" | sort -u | wc -l)" "$ROOT_MOUNT"
    fi
    echo "   ----------------------------------------------------------------------"
    printf '   TOTAL: %s on %s, %s on %s (tier 3 images not included)\n' \
        "$(human "$GRAND_FAST")" "$FAST_MOUNT" "$(human "$GRAND_ROOT")" "$ROOT_MOUNT"
    printf '   projected free, %s: %s  ->  %s\n' "$FAST_MOUNT" \
        "$(human "$FAST_AVAIL_BEFORE")" "$(human $((FAST_AVAIL_BEFORE + GRAND_FAST)))"
    printf '   projected free, %s: %s  ->  %s\n' "$ROOT_MOUNT" \
        "$(human "$ROOT_AVAIL_BEFORE")" "$(human $((ROOT_AVAIL_BEFORE + GRAND_ROOT)))"
    echo "   Nothing was removed. Re-run with --yes to act on these tiers."
fi
echo "=============================================================================="
