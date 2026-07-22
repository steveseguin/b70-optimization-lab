# DeepSeek V4 Flash K160 closed paths

The complete negative-result inventory remains in the
[experiment ledger](../../experiments/deepseek-v4-flash-reap-xpu-b70/results/experiment-ledger.md)
and dated lane notes. The closeout groups the most important findings:

- M=1 decode is occupancy/latency starved; tile prepacking, split-N workgroup
  expansion, GRF tuning, and submission collapse did not improve the endpoint.
- Option 4 proved fixed raw Level Zero command-list replay feasible, but the
  guarded M1 attention endpoint regressed and failed cross-run exact-token
  identity.
- MHC arithmetic shortcuts changed greedy tokens and are quality-rejected.
- Full draft replay and combined sampler/model replay corrupted outputs.
- Fixed DSpark5 and several exact DSpark7 fusion/transport candidates were
  slower than the record despite positive isolated gates.
- Earlier oneCCL readiness rollover and large-SYCL-allreduce corruption were
  repaired by the pinned wide-epoch, size-routed oneCCL identity. Do not use
  the pre-repair 40.136 row as repeatability authority.
- No post-record endpoint exceeded 80.820052 tok/s. Values near 90 tok/s are
  projections contingent on a much larger EAGLE training corpus; 151 tok/s is
  a nonspeculative bandwidth roofline, not a measured result.

Read the [frontier closeout](../../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md)
before reopening any path.
