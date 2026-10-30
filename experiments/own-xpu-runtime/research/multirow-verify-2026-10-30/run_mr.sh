#!/usr/bin/env bash
# Device phase of research/multirow-verify-2026-10-30 (copy of research/decode-site-census-2026-10-30/run_census.sh; adds
# flag env=OWNRT_NAME=VALUE, MR_BIN for the engine binary, MR_RUNS for the run folder).
# Launched once as a transient unit that already holds the card locks it uses:
#   systemd-run --user --unit=decode-census-<phase> --collect -p Restart=no -p KillMode=process -p LimitNOFILE=1048576 \
#     -E CENSUS_RUNS=... flock -n -E 75 /dev/shm/card23.lock taskset -c 0-3,16-19 bash run_census.sh <phase> ARM...
# ARM = name:rank:flags   flags = comma list passed to census_driver.py run as --<flag> (trace, dump, route-dump, cycle) or
#   prefix=K window=W modes=a+b+c rowsin=ARMNAME|/abs/rows.bin (that arm's rows-d.bin) reversein=ARMNAME|/abs/rows.bin
# Per arm: MemAvailable/shm/root floors, fresh output, driver run, kernel-log check. Any fault line or nonzero exit halts;
# nothing is retried. Do not edit while it runs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/multirow-verify-2026-10-30
C=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/decode-site-census-2026-10-30
PS=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-speed-2026-10-29
KL=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/e2e-suite-2026-10-29/klog_check.py
RUNS=${MR_RUNS:-/dev/shm/multirow-20261030/runs}
BIN=${MR_BIN:?MR_BIN required}
CACHE=$(dirname "$RUNS")/cache
PHASE=$1; shift
exec >>"$D/logs/$PHASE.log" 2>&1
echo "=== phase $PHASE binary $BIN ($(sha256sum "$BIN" | cut -c1-12)) start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //') nofile $(ulimit -n)"
echo "started $PHASE" >"$D/logs/STATUS"
halt() { echo "HALT: $1"; echo "HALT $PHASE: $1" >"$D/logs/STATUS"; exit 1; }
flock -n /dev/shm/card23.lock true && halt "card23 lock is not held"
T0=$(date +%s)
python3 "$KL" "$PHASE-before-24h" $(( T0 - 86400 )) "$D/logs/kernel-log-$PHASE-before-24h.txt" || halt "kernel log not clean before phase"
mkdir -p "$RUNS"
for arm in "$@"; do
  IFS=: read -r name rank flags <<<"$arm"
  out="$RUNS/$name"
  [ -e "$out" ] && halt "$out exists (fresh outputs only)"
  avail=$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo); shm=$(df -B1 --output=avail /dev/shm | tail -1)
  echo "--- arm $name rank=$rank flags=$flags MemAvailable=$avail shm_free=$shm at $(date -Is)"
  [ "$avail" -ge 64000000000 ] || halt "MemAvailable $avail below 64 GB before $name"
  [ "$shm" -ge 12000000000 ] || halt "/dev/shm free $shm below 12 GB before $name"
  root=$(df -B1 --output=avail / | tail -1); [ "$root" -ge 27000000000 ] || halt "root free $root below 27 GB before $name"
  more=()
  for x in ${flags//,/ }; do case "$x" in
    trace) more+=(--trace) ;; dump) more+=(--dump) ;; route-dump) more+=(--route-dump) ;; cycle) more+=(--cycle) ;;
    env=*) v=${x#env=}; more+=(--env "${v//+/,}") ;;   # "+" stands for "," inside a value
    prefix=*) more+=(--prefix "${x#prefix=}") ;; window=*) more+=(--window "${x#window=}") ;;
    modes=*) v=${x#modes=}; more+=(--modes "${v//+/,}") ;;
    rowsin=*) v=${x#rowsin=}; [[ $v == /* ]] && more+=(--rows-in "$v") || more+=(--rows-in "$RUNS/$v/rows-d.bin") ;;
    reversein=*) v=${x#reversein=}; [[ $v == /* ]] && more+=(--reverse-in "$v") || more+=(--reverse-in "$RUNS/$v/rows-d.bin") ;;
    "") ;; *) halt "unknown flag $x" ;; esac; done
  L="$PS/rank$rank-launch-c65536-b51c9e8d803e.json"; [ -f "$L" ] || halt "no launch $L"
  t=$(date +%s)
  env NEOReadDebugKeys=1 EnableDeferBacking=0 python3 -B "$D/mr_driver.py" run --rank "$rank" --launch "$L" --binary "$BIN" \
    --out "$out" --tokens "$C/inputs/code-review-seq.json" --cache "$CACHE" "${more[@]}"
  rc=$?; echo "arm $name rc=$rc after $(( $(date +%s) - t )) s"
  python3 "$KL" "$PHASE-after-$name" "$t" "$D/logs/kernel-log-$PHASE-after-$name.txt" || halt "kernel log after $name"
  [ "$rc" -eq 0 ] || { tail -30 "$out/rank$rank.log"; halt "arm $name rc=$rc"; }
done
echo "=== phase $PHASE done $(date -Is)"
echo "done $PHASE" >"$D/logs/STATUS"
