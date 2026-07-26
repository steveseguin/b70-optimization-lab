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

# The interface carrying the cluster IP is resolved at runtime, not hardcoded.
# A reboot on 2026-07-26 swapped the onboard NIC names: the port holding
# 10.0.0.65 (MAC 3c:ec:ef:ce:5a:7e) moved from eno1 to eth1, and a different
# port took the name eno1 and stayed down. oneCCL then failed with
# "can't find interface eno1 to get host IP", which aborts KVS and PMI
# bootstrap before any GPU transport is created. Deriving the name keeps the
# harness correct across renames. This affects only CCL's rendezvous, not the
# GPU data path.
laguna_cluster_iface() {
  local ip="${LAGUNA_CLUSTER_IP:-10.0.0.65}" iface
  iface="$(ip -o -4 addr show 2>/dev/null | awk -v ip="$ip" '$4 ~ "^"ip"/" {print $2; exit}')"
  [[ -n "$iface" ]] || { echo "no interface carries $ip" >&2; return 1; }
  [[ "$(cat "/sys/class/net/$iface/operstate" 2>/dev/null)" == up ]] \
    || { echo "interface $iface carrying $ip is not up" >&2; return 1; }
  printf '%s\n' "$iface"
}

[[ -x "$leg" ]] || die "measurement leg missing: $leg"
cluster_iface="$(laguna_cluster_iface)" || die "cannot resolve the cluster interface"
readonly cluster_iface
echo "cluster interface: $cluster_iface"

# --- preflight -------------------------------------------------------------
# A per-card matmul is NOT sufficient. Cards can pass single-device work while
# the 4-rank collective is still wedged, and a leg that gets that far hangs for
# fifteen minutes in init_device's warm-up all_reduce before timing out. The
# preflight therefore runs the same collective the leg will run.
echo "== preflight: single-card execution =="
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

echo "== preflight: 4-rank collective (the check that actually gates a leg) =="
probe="$script_dir/run_xccl_collective_probe.sh"
[[ -x "$probe" ]] || die "collective probe missing: $probe"
probe_scratch="${XCCL_PROBE_SCRATCH:-/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/ladder-preflight-$tag}"
probe_log="$probe_scratch/launcher.log"
mkdir -p -- "$probe_scratch" || die "cannot create collective preflight root: $probe_scratch"
[[ ! -e "$probe_log" ]] \
  || die "collective preflight log already exists; choose a fresh tag or scratch: $probe_log"
XCCL_PROBE_SCRATCH="$probe_scratch" \
  timeout 240 "$probe" ladder-preflight \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 \
  CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE="$cluster_iface" CCL_KVS_IFACE="$cluster_iface" \
  >"$probe_log" 2>&1
probe_rc=$?
if ((probe_rc != 0)); then
  probe_result="$(grep -E '^PROBE_RESULT=' "$probe_log" 2>/dev/null | tail -1)"
  die "4-rank preflight failed (rc=$probe_rc; ${probe_result:-no classified result}); inspect $probe_log; do not infer a recovery action from a harness or startup failure"
fi
grep -Eq '^PROBE_RESULT=PASS clean_teardowns=4/4 ' "$probe_log" \
  || die "collective probe exited zero without a complete PASS marker; inspect $probe_log"
echo "  4-rank all_reduce ok"

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
