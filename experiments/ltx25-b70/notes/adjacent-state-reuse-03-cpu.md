# Adjacent state validation reuse03: CPU qualification

September 14, 2026. Inactive candidate; native GPU quality and speed are pending.

The [patch](../patches/multiblock-adjacent-state-03/README.md) removes only two
immediately repeated current-block state checks. Successful bound lifecycle
validation has already completed the stronger check at the same boundary.
All three lifecycle/registry boundaries remain, including the boundary after
original tensor routing and the native gate. Unbound routes retain both checks.
No arithmetic, compiler settings, model state, shape or sampling schedule changes.

Both parent and candidate passed all 60 checks using native CPU ModelPatcher
pre_run with a dispatch spy. The test counted five versus three current-block
state scans, with three registry scans in both versions. It also rejected late
hooks, wrong owners and mutations between routing and native execution.
Independent source review found no blocker and confirmed that reversing the
four narrow changes restores the parent whole-module AST exactly.

At 48 blocks and 11 calls per clip, this removes 1,056 state/hook scans. This
count is not a measured latency reduction. The previous all48 compilation path
was slower than original dispatch; this candidate must still pass native exact
output and matched timing checks before any promotion.

Evidence: [summary](../data/adjacent-state-reuse-03/summary.json),
[parent](../data/adjacent-state-reuse-03/parent-cpu.json),
[candidate](../data/adjacent-state-reuse-03/candidate-cpu.json).
The reports pin the test, adapter and native source identities. Full local test
snapshots are under `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/adjacent-state-{parent,candidate}-cpu-01`.

Commands, from this lane (replace the two explicit values for each arm):

```bash
/home/steve/.venvs/ltx25-baseline/bin/python scripts/test-adjacent-state-reuse-cpu.py \
  --adapter patches/multiblock-adjacent-state-03/original.py \
  --adapter-sha256 12ffb29cb4c8a61e8d9a22586a5f9f96ad170de882d62bfb4981f269d3b1bd3f \
  --expected-state-scans 5 \
  --output /mnt/fast-ai/bench-results/ltx25-baseline-20260913/adjacent-state-parent-cpu-01.json \
  --evidence /mnt/fast-ai/bench-results/ltx25-baseline-20260913/adjacent-state-parent-cpu-01
```

Candidate uses `candidate.py`, SHA
`79b4e76b10f49094f3ad11cc70ba62334c2ccf10e50960ac209fb5a0cdd2a584`,
expected scans `3`, and `adjacent-state-candidate-cpu-01` output paths.
Neither CPU test compiled kernels or used native checkpoint weights or GPUs.
