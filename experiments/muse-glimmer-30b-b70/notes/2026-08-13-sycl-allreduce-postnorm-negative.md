# SYCL final-allreduce + RMSNorm/MUL/ADD fusion: exact but neutral/slower

Date: 2026-08-13

Decision: **reject from the retained stack**. The implementation is exact on
the canonical suite and executes at all 103 eligible verifier boundaries, but
the full drift-controlled run is neutral to slightly slower.

## Experiment

The default-off prototype fused the second TP4 recursive-doubling F32 ADD with
the already-retained `RMS_NORM -> MUL -> ADD` post-projection chain. It kept the
first allreduce round and both P2P copies unchanged, used the incumbent RMS
workgroup/reduction tree, materialized the F32 allreduce result before RMSNorm,
and materialized the F32 MUL result before the residual ADD. Meta submitted a
UID-zero view of the next subgraph with the first three nodes skipped only
after the backend hook reported success.

The live allocator uses one exact in-place storage layout for partial, RMS
output, MUL output, and ADD output. The norm weight and residual are disjoint.
The initial strict alias guard therefore produced a safe no-op; bounded
diagnostics identified the exact alias, after which the guard admitted only
pointer/type/shape/stride-identical overlap.

Source history in `/home/steve/src/llama.cpp-muse-100`:

- experiment: `339df07f3` (`sycl: experiment with fused allreduce postnorm`);
- rejection/revert: `c692dd83a`.

Runtime gate: `GGML_SYCL_COMM_ALLREDUCE_RMS_MUL_ADD=1`. The retained
`GGML_SYCL_RMS_NORM_MUL_ADD_FUSION=1` was enabled in every arm. All other
identity fields matched the retained top15/tree512/heap/last-event stack.

## Bring-up

The first 64-token C/A/C was a no-op because the strict local alias guard
rejected the live allocation. Raw JSONL:

`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-allreduce-rms-mul-add-smoke-cac-20260813.jsonl`

SHA-256: `4baf555c396750af2929ef62760e0e8e2cc6670a90835eecad19483baff1897f`.

After exact-alias support, the second 64-token C/A/C logged both required
markers:

- hit 1: `l_out-0`, `[6656,16]`, last-event readiness;
- hit 103: `l_out-50`, `[6656,16]`, last-event readiness.

All three hashes and proposal counts matched:

| Class | Hash | Drafted / accepted |
|---|---|---:|
| prose | `f45a2f2c58f1ca34` | 155 / 48 |
| code | `2ca4135046a15a71` | 126 / 53 |
| JSON | `32dc3aebb11684a4` | 65 / 58 |

The short run suggested 0.21--0.46 ms/round savings, but this was not stable.
Raw JSONL:

`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-allreduce-rms-mul-add-smoke2-cac-20260813.jsonl`

SHA-256: `13bb6ec683638917418ca7854d2aab7f009bd73caccacbd39c3aedbedf917cd4`.

## Full 256-token C/A/C

| Arm | Prose | Code | JSON | Arithmetic mean |
|---|---:|---:|---:|---:|
| control before | 57.570 | 83.081 | 101.355 | 80.669 |
| fusion | 57.542 | 83.126 | 101.113 | 80.594 |
| control after | 57.502 | 83.109 | 101.542 | 80.718 |

Canonical hashes were exact in every arm:

- prose `914f754747d0edaa`;
- code `cf2b2c4fd9e36fe5`;
- JSON `4f813a9706abc163`.

Accepted counts stayed 172 / 197 / 207. Prose drafted count varied by one
(1199 / 1198 / 1198), a previously observed proposal-accounting boundary that
did not change output or accepted count.

Using `round_ms = 1000 * 256 / (tok_s * (256 - accepted))`, the candidate
minus drift-interpolated control deltas were:

- prose: `-0.005542 ms/round`;
- code: `-0.019475 ms/round`;
- JSON: `+0.170833 ms/round`;
- unweighted class mean: `+0.048605 ms/round` (slower).

Raw JSONL:

`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-allreduce-rms-mul-add-full-cac-20260813.jsonl`

SHA-256: `ffedd95c2dfda95796d69ffe65952a31944f4b581d0e343a90d8936bb59a85ab`.

## Conclusion

Removing the standalone final allreduce ADD and postnorm/residual submissions
does not reduce the fixed-shape verifier critical path on this stack. The
larger one-workgroup fused kernel offsets the saved dispatches. Do not retry
this exact cross-boundary fusion or infer a win from the noisy 64-token smoke.
Retain the simpler allreduce last-event readiness optimization instead.
