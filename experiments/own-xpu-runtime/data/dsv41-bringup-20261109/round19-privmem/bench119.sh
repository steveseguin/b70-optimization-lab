#!/bin/bash
# bench119: only the two kvshard benches from tp119 (no engine build: the kvshard gate waits for the push form, tp120).
# tp119 = tp118p (privmem-1 + tpd-2) + kvshard-1 (OWN_KV_SHARD, opt-in; the agent's 3 commits cherry-picked)
# + KvGather six pointer members; worktree tp119. Also the two kvshard benches (test_topk_shard, bench_attn_a1_kvs).
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-bench119.log
touch $W/locks/build-tp119; trap "rm -f $W/locks/build-tp119" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in a8a24c0268; do
  rm -rf $W/src119; mkdir -p $W/src119/tools
  git -C $W/tp119 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src119 || { echo "tp119 build exit 9 (source export $C)" >> $L; exit 9; }
  echo "tp119: source commit $C (benches only)" >> $L
  rc=0
  if [ $rc -eq 0 ]; then
    for b in test_topk_shard:test_topk_shard bench_attn_a1:bench_attn_a1_kvs; do
      (cd $W/src119 && nice -n 5 icpx -fsycl $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/${b%%:*}.cpp -o $W/${b##*:} >> $L 2>&1) \
        && echo "tp119: bench ${b##*:} built" >> $L || echo "tp119: bench ${b##*:} FAILED" >> $L
    done
    break
  fi
  echo "tp119: device build failed at $C (exit $rc)" >> $L
done
echo "tp119 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
