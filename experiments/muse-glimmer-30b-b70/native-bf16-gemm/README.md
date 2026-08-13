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
