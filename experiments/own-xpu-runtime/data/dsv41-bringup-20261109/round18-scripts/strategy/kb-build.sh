#!/bin/bash
# build one-card benches one after another (host has 15 GiB: one compile at a time)
set -u
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
ENG=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
cd $ENG
F="-fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 -options -ze-intel-enable-auto-large-GRF-mode -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src"
for b in "$@"; do
  t0=$(date +%s)
  case $b in
    bench_routed_m1) nice -n 10 icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/$b.cpp -o /home/steve/dsv41-work/kb/$b -lze_loader > /home/steve/dsv41-work/kb/$b.build.log 2>&1 ;;
    *) nice -n 10 icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/$b.cpp -o /home/steve/dsv41-work/kb/$b > /home/steve/dsv41-work/kb/$b.build.log 2>&1 ;;
  esac
  echo "$b exit $? in $(( $(date +%s) - t0 )) s" >> /home/steve/dsv41-work/kb/build.txt
done
echo BUILT >> /home/steve/dsv41-work/kb/build.txt
