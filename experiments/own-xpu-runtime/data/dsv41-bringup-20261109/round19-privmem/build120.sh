#!/bin/bash
# tp120 build: tp118p (privmem-1 + tpd-2) + kvshard-1 + KvGather six members + kvshard push (OWN_KV_PUSH, default on
# with OWN_KV_SHARD) + privmem-2; worktree tp120 (fe2eae1ab2: + eng-gate-1 + tpd-3 + eng-warm-1 + eng-spread-1). Benches: test_kv_push, bench_attn_a1_kvs120, test_topk_shard120.
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp120.log
touch $W/locks/build-tp120; trap "rm -f $W/locks/build-tp120" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in fe2eae1ab2; do
  rm -rf $W/src120; mkdir -p $W/src120/tools
  git -C $W/tp120 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src120 || { echo "tp120 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src120 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp120: syntax check failed at $C" >> $L; continue; fi
  echo "tp120: source commit $C" >> $L
  (cd $W/src120 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp120 -lze_loader >> $L 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    for b in test_kv_push:test_kv_push bench_attn_a1:bench_attn_a1_kvs120 test_topk_shard:test_topk_shard120; do
      (cd $W/src120 && nice -n 5 icpx -fsycl $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/${b%%:*}.cpp -o $W/${b##*:} >> $L 2>&1) \
        && echo "tp120: bench ${b##*:} built" >> $L || echo "tp120: bench ${b##*:} FAILED" >> $L
    done
    break
  fi
  echo "tp120: device build failed at $C (exit $rc)" >> $L
done
echo "tp120 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
