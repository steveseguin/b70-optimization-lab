#!/usr/bin/env bash
# Run the post-reboot Laguna ladder unattended, cheapest lever first.
#
# Each rung is a sealed measurement leg with its own cold start, exactness gate,
# and idle verification -- this only sequences them and stops early once a rung
# clears the objective. It makes no measurement of its own and relaxes nothing.
#
# usage: run_laguna_post_reboot_ladder.sh [TAG]
set -uo pipefail
umask 077

readonly tag="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly leg="$script_dir/run_laguna_mwide_measurement_leg.sh"
readonly runs=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly objective=102.0

die() { echo "ladder: $*" >&2; exit 2; }
[[ -x "$leg" ]] || die "measurement leg missing: $leg"

# --- preflight: every card must execute, or a leg will wedge the set ---------
echo "== preflight: all four cards must run a real kernel =="
for d in 0 1 2 3; do
  out="$(timeout 60 env -i \
    PATH=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/bin:/bin \
    LD_LIBRARY_PATH=/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib \
    HOME=/tmp "$python" -c "
import torch
a = torch.randn(1024, 1024, device='xpu:$d', dtype=torch.bfloat16)
torch.xpu.synchronize(); print('OK')" 2>&1 | tail -1)"
  [[ "$out" == OK ]] || die "xpu:$d is not healthy ($out) -- reboot before running the ladder"
  echo "  xpu:$d ok"
done

# Rung: LABEL TREATMENT M SPEC METADATA DRAFTGRAPH  -- cheapest lever first.
# Rung 1 is the control that re-establishes the record on the recovered host;
# it is never skipped, because a candidate without a same-session control is
# not evidence.
rungs=(
  "control  A1 8  7  1 0   record-control"
  "candidate B1 8  7  1 1   draft-graph-capture"
  "candidate B2 16 15 1 0   width16-chain"
  "control  A2 8  7  1 0   record-control-closing"
)

score() {  # median scored decode rate from a leg's bench.json
  "$python" - "$1" <<'PY'
import json, sys
b = json.load(open(sys.argv[1]))
def find(o, k):
    if isinstance(o, dict):
        for kk, vv in o.items():
            if kk == k: return vv
            r = find(vv, k)
            if r is not None: return r
    elif isinstance(o, list):
        for vv in o:
            r = find(vv, k)
            if r is not None: return r
for key in ("tok_s_out", "median_decode_tokens_per_second"):
    v = find(b, key)
    if v is not None:
        print(f"{float(v):.6f}"); break
else:
    print("nan")
PY
}

summary="$runs/ladder-$tag-summary.txt"
: > "$summary"
best=0

for rung in "${rungs[@]}"; do
  read -r treatment label m spec metadata draftgraph name <<<"$rung"
  run_dir="$runs/ladder-$tag-$name"
  echo
  echo "== rung: $name (M=$m spec=$spec metadata=$metadata draftgraph=$draftgraph) =="
  if "$leg" "$treatment" "$label" "$run_dir" "$m" "$spec" "$metadata" "$draftgraph"; then
    s="$(score "$run_dir/bench.json")"
    printf '%-26s PASS tok_s=%s\n' "$name" "$s" | tee -a "$summary"
    awk -v a="$s" -v b="$best" 'BEGIN{exit !(a>b)}' && best="$s"
    if awk -v a="$s" -v o="$objective" 'BEGIN{exit !(a>=o)}'; then
      echo "OBJECTIVE MET by $name at $s tok/s" | tee -a "$summary"
      # Still run the closing control: a record that never re-establishes its
      # own baseline in the same session is not a defensible submission.
      [[ "$name" == record-control-closing ]] && break
    fi
  else
    printf '%-26s FAIL (see %s)\n' "$name" "$run_dir" | tee -a "$summary"
    # A failed rung may have left workers or a wedged card; stop rather than
    # stack another leg on top of it.
    die "rung $name failed -- inspect before continuing"
  fi
done

echo
echo "== ladder complete, best measured $best tok/s =="
cat "$summary"
