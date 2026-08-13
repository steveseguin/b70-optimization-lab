# Muse fixed-shape native BF16 GEMM falsification

This standalone experiment compares the incumbent oneDNN BF16/BF16/F32
matmul with a fixed-shape ESIMD XMX/DPAS kernel for one TP4 Muse FFN shard:
`M=4992`, `N=16`, `K=6656`. It does not modify llama.cpp or production.

The custom path uses a separate static VNNI-packed copy of the weight. That is
acceptable only for the first falsification; it is not an integration design,
because duplicating every FFN projection would consume multiple GiB per card.

Advance only if both gates pass on the first synthetic screen:

- every F32 output bit equals oneDNN;
- steady batched time is at most 80% of oneDNN time.

If either gate fails, bank the result and close the native-GEMM lane. If both
pass, the next gates are real captured activations, adversarial BF16 inputs,
and a no-duplicate-weight loading design.

## Result: closed

The first isolated B70 screen failed both gates:

| path | batched mean |
| --- | ---: |
| incumbent oneDNN | `0.116769 ms` |
| fixed-shape DPAS | `0.154349 ms` |

The custom path was `1.321836x` as slow as oneDNN. It also differed in
`73,048 / 79,872` F32 output elements. The first mismatch was one low bit
(`0xbe0460d9` versus `0xbe0460da`), consistent with a different accumulation
order rather than a layout error, but it still violates the exactness gate.

Do not integrate or tune this kernel further. It had the advantage of an
already-VNNI-packed duplicate weight and still lost; an integration-safe path
would also have to eliminate that multi-GiB duplication. The external log is
`/mnt/fast-ai/bench-results/muse-glimmer-30b/native-bf16-gemm/synthetic-first-20260813.log`,
SHA256 `14605d7cc23a298a5eae3e4951c7f9c8aa0a106fa39c7a7d56e117cd2348bf06`.
Production was restored without reboot and passed the full model,
cache-zero/code, and vision gate in
`data/muse-health-20260813-native-bf16-gemm-restore.json`.

Operational note: the first launch wrapper enabled `set -u` before sourcing
oneAPI and exited before the benchmark; because it lacked an EXIT trap, the
services required an immediate manual restart. A second selector typo
(`level_zero:gpu:0` instead of this runtime's `level_zero:0`) was caught under
the corrected cleanup trap. Neither attempt submitted GPU work. The measured
screen used `level_zero:0`, and the final full health gate above is the restore
authority. Future standalone windows must install the cleanup trap before
stopping production and must not source oneAPI under nounset.

## Activation-reuse recheck: still closed

The lane was reopened once after target-only profiling separated roughly
`27 ms` of steady oneDNN GEMM service from a larger `44-46 ms` target pass.
That made a graph-recordable native kernel potentially useful even if it only
matched, rather than beat, oneDNN. Two bounded activation-reuse designs were
tested at the same `4992x16x6656` shape:

- an SLM design sharing `K` blocks across a workgroup of output-row tiles;
- a no-barrier design computing 2, 4, or 8 adjacent row tiles per ESIMD
  workitem while loading each activation tile once.

The best SLM configuration was workgroup 8, `K` block 256. In its dedicated
sweep it measured `0.130106 ms` against `0.120399 ms` for oneDNN (`1.081x`).
In the final multi-row sweep the same SLM path measured `0.129190 ms` against
`0.123319 ms` (`1.048x`) in the row-tiles-2 binary. The multi-row path was
worse: `1.554x`, `2.584x`, and `21.315x` oneDNN for 2, 4, and 8 row tiles.
Every custom variant retained the same `73,048 / 79,872` F32 bit mismatches.

This stronger recheck closes the native kernel lane again. Sharing activation
traffic does not recover oneDNN performance, larger per-workitem accumulator
sets quickly spill or otherwise collapse occupancy, and none of the designs
preserves the incumbent accumulation identity. The implementation and tuning
macros remain here as a durable negative artifact.

External logs and SHA256 values:

- `synthetic-slm-v2-20260813.log`:
  `08470e16b155d71adb5d4bbd7e9f3c2439d50a971532b4358207036331711414`;
- `synthetic-slm-tile-sweep-20260813.log`:
  `8d967870d2c2eb670994318017eb0dda51099700c1a29cd28b23b70e3b3c09d3`;
- `synthetic-multirow-tile-sweep-20260813.log`:
  `a576e2d357d09cd302f7276680e066106633eb1972ae8e6f14731fedbcc1a240`.

They are under
`/mnt/fast-ai/bench-results/muse-glimmer-30b/native-bf16-gemm/`.
Production was restored without reboot and passed the full gate in
`data/muse-health-20260813-native-bf16-multirow-restore.json`.

An additional oneDNN mixed-input screen attempted to remove the explicit
activation conversion by supplying the exact BF16-rounded activation values
widened back to F32 (`BF16 weight x F32 activation -> F32`). The descriptor
compiled, but runtime did not complete even the eight warmups plus first call
within 60 seconds; the incumbent completes 200 calls in about 24 ms. The run
was interrupted under the cleanup trap and is a decisive implementation-path
negative. Its partial external log is
`synthetic-onednn-f32src-20260813.log`, SHA256
`f75da134634c1ed91cf4316f45fc8f9a7a057ba72140cd660cda6ba6fa14ade3`.
The exact attempted code is preserved in Git history and then removed from the
default harness because it makes every invocation unusable. Production again
passed the full gate in
`data/muse-health-20260813-onednn-f32src-restore.json`.

## Scheduler-mode screen

The only remaining card-level scheduling hypothesis was also closed. All
cards reported `timeslice`, interval `1000 us`, yield timeout `640000 us`.
The driver rejected `xpu-smi ... --scheduler exclusive` with
`not support this scheduler mode`, and a config read immediately afterward
proved that GPU 0 remained in the original timeslice mode. The two 200-call
oneDNN measurements were correspondingly identical (`0.116331` and
`0.116413 ms`). This was a capability/no-op screen, not a candidate A/B.

External log hashes are
`d865a52f4f83faab078fa1ae917d4907e0d46dccf32e850dc612761d9bb26010`
for the timeslice control and
`067e251b6d4ad1c0d244bd2f7eb8a9c94b00e4acf326a7fdb23e9fcf2f72c6ee`
for the rejected-exclusive repeat. The cleanup command's attempt to write the
already-current three-field timeslice tuple was itself rejected as invalid;
because the exclusive write never succeeded, no restoration mutation was
needed. A final read reconfirmed the exact original tuple. Production then
passed the full gate in
`data/muse-health-20260813-scheduler-screen-restore.json`.
