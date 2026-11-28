#!/bin/bash
# run-wave.sh <arms-file> <out-dir>:
# Parallel single-card experiment wave dispatcher across cards 0-5 (override via WAVE_CARDS="0 1 2 3 4 5").
#
# Arms file format (blank lines and '#' comments ignored):
#   <arm_name>|<extra_env_assignments>|<binary> <args with {CARD} placeholder>
# Example:
#   ctrl|INK_DRAFT=/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/dspark-Inkling-2-Mini-Q8_0.gguf INK_SPEC=7|/home/steve/inkling-work/bin/ink_run /mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf {CARD} /home/steve/inkling-work/prompts/c200k.tokens 512 204800
#
# Guarantees:
# - Dispatches up to len(WAVE_CARDS) arms in parallel (one job per card via on-card.sh).
# - Records stdout (.ids), stderr (.err), exit code (.rc), wall seconds (.sec), and SHA-256 of .ids.
# - Checks exact ID parity of every arm against the first arm (or WAVE_REF_SHA256 if set).
# - Scans kernel journal for GPU faults after the wave finishes.
# - Never silently skips arms: any failed/missing arm returns non-zero.
set -u
arms_file=${1:?usage: run-wave.sh <arms-file> <out-dir>}
out_dir=${2:?usage: run-wave.sh <arms-file> <out-dir>}
HERE=$(cd "$(dirname "$0")" && pwd)
ON_CARD="$HERE/on-card.sh"
COMMON="$HERE/../../common"

[ -f "$arms_file" ] || { echo "run-wave: missing arms file: $arms_file"; exit 2; }
mkdir -p "$out_dir"

read -r -a CARDS <<< "${WAVE_CARDS:-0 1 2 3 4 5}"
[ "${#CARDS[@]}" -gt 0 ] || { echo "run-wave: WAVE_CARDS is empty"; exit 2; }

mapfile -t LINES < <(grep -vE '^[[:space:]]*(#|$)' "$arms_file")
[ "${#LINES[@]}" -gt 0 ] || { echo "run-wave: no arms in $arms_file"; exit 2; }

start_ts=$(date '+%Y-%m-%d %H:%M:%S')
echo "run-wave: ${#LINES[@]} arm(s) across cards [${CARDS[*]}] -> $out_dir (start $start_ts)"

# Dispatch in waves of size ${#CARDS[@]} so each card runs at most one job at a time
idx=0
arm_names=()
while [ "$idx" -lt "${#LINES[@]}" ]; do
    pids=()
    for card in "${CARDS[@]}"; do
        [ "$idx" -lt "${#LINES[@]}" ] || break
        line="${LINES[$idx]}"
        IFS='|' read -r name env_str cmd_tmpl <<< "$line"
        name=$(echo "$name" | xargs)
        arm_names+=("$name")
        cmd="${cmd_tmpl//\{CARD\}/$card}"
        echo "  launch [$name] on card $card"
        (
            t0=$(date +%s.%N)
            # shellcheck disable=SC2086
            env $env_str "$ON_CARD" "$card" bash -c "$cmd" \
                > "$out_dir/$name.ids" 2> "$out_dir/$name.err"
            rc=$?
            t1=$(date +%s.%N)
            python3 -c "print(f'{$t1 - $t0:.2f}')" > "$out_dir/$name.sec"
            echo "$rc" > "$out_dir/$name.rc"
            echo "$card" > "$out_dir/$name.card"
            sha256sum "$out_dir/$name.ids" | awk '{print $1}' > "$out_dir/$name.sha256"
        ) &
        pids+=("$!")
        idx=$((idx + 1))
    done
    for p in "${pids[@]}"; do wait "$p"; done
done

echo ""
echo "| Arm | Card | RC | Wall (s) | Speed line | ID SHA-256 | Parity |"
echo "|---|---:|---:|---:|---|---|---|"

ref_sha="${WAVE_REF_SHA256:-}"
overall_rc=0
for name in "${arm_names[@]}"; do
    card=$(cat "$out_dir/$name.card" 2>/dev/null || echo "?")
    rc=$(cat "$out_dir/$name.rc" 2>/dev/null || echo "1")
    sec=$(cat "$out_dir/$name.sec" 2>/dev/null || echo "?")
    sha=$(cat "$out_dir/$name.sha256" 2>/dev/null || echo "missing")
    spd=$(grep -hE "generated|tok/s" "$out_dir/$name.err" | tail -1 | tr '|' '/' | cut -c1-140)
    [ -z "$ref_sha" ] && [ "$rc" = "0" ] && ref_sha="$sha"
    if [ "$rc" != "0" ]; then
        parity="FAIL(rc=$rc)"
        overall_rc=1
    elif [ "$sha" = "$ref_sha" ]; then
        parity="EXACT"
    else
        parity="DIFF"
        overall_rc=1
    fi
    echo "| $name | $card | $rc | $sec | ${spd:-n/a} | \`${sha:0:12}\` | $parity |"
done

if [ -x "$COMMON/check-journal-faults.sh" ]; then
    echo ""
    "$COMMON/check-journal-faults.sh" "$start_ts" || overall_rc=1
fi

exit $overall_rc
