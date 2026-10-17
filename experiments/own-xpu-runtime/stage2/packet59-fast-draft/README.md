# Packet 59: faster draft, unchanged target

CPU-prepared candidate based on packet56. Only `mtp.hpp` and the new
`p59_draft.hpp` / `p59_hc.hpp` change inference. The target source, dispatch,
selection, weight readers, controller, BF16 KV and packet49 oracle remain
unchanged. The draft head still reads exactly **91,392** rows. Draft arithmetic
may differ: every proposed token must pass the unchanged target verifier.

[Coordinator screen command](WINDOW.md) · [CPU preparation](CPU-BUILD.md) ·
[CPU gates](cpu-gates.json) · [planning budget](budget.json) ·
[task note](../../../../notes/2026-10-17-own-runtime-packet59.md)

## Draft changes

The draft stores dense weights as BF16 and experts as private INT8 with
per-16 scales. Target Q8/Q6/IQ2/IQ4 kernels cannot read those bytes directly.
This packet independently ports their useful schedules; it does not change
weights or pretend target microtimings measure the new draft kernels.

| Draft site | Packet56 | Packet59 | Before → expected, µs |
| --- | --- | --- | --- |
| QSA qgate | BF16 dense | explicit vector8 loads | 126 → 77 proxy |
| QSA attention | inherited attention | target p49/p47 split32, private scratch | 113 → 44 proxy |
| Expert gate/up | INT8 SG32 | p53b virtual8 schedule, fused activation | 82 → 72 proxy, plus removed activation |
| Expert down | INT8 SG32 | p53b virtual16 schedule | 64 → 57 proxy |
| Attention output | BF16 dense | vector8 split4, fused stream update | 77 → 47 proxy, plus removed combine |
| HC low, including final | BF16 SG32 + activation | p51-style split4 + fused activation | 22 → 11.5 proxy, each |
| HC gate/mix, including final | separate BF16 gate and mixture | virtual4 projection + mixture | 27–28 + 7 → 15 proxy, each |
| HC inject | BF16 SG32 | vector8 split4 | attention 48 → 13 proxy; FFN observed 20, uncertain transfer |
| Route | inherited generic path | selected p54 `route-exp32-rank4` | 43 → 20 proxy |
| HC/final norm | inherited norm | fixed256 tree, one launch per norm | about 8 → 5.6 assumption |
| Embedding norm | inherited norm | fixed256 tree, one launch | 28 → 14 assumption |
| Hidden norm | two launches | fixed256 tree, one launch | 8 → 4 assumption |
| Hidden projection/merge | BF16 projection + add | vector8 projection with merge-add tail | 58 + 2 → about 50 assumption |
| Embedding projection | BF16 SG32 | explicit vector8 loads | 33; no saving credited |
| QSA k/v/iq/ik; router; shared gate/up/down/router | inherited BF16 kernels | vector8, virtual4 for K=320/640; shared-up activation fused | no saving credited beyond removed activation |
| Prefix logits; argmax | p33 expanded Q6; round2 | retained fastest compatible path | 521; 21, unchanged |
| QSA prepare/pool/select; gather; checks; begin/commit; final FFN combine | selected inherited paths | retained | no faster compatible measured replacement |

Packet52's free-order GEMV grid regressed in gate/up, QKV, attention and HC.
Its winning expert-down/small-FFN choices were for target formats, and later
p53b/p54 winners supersede those controls. No packet52 variant has evidence
of beating these selected schedules on draft INT8/BF16. Its fixed arithmetic
freedom is used for the draft norms and split4 reductions; these need only
determinism and target verification, not equality to the old draft.

Fusions remove ten standalone sites (three low activations, three HC mixes,
expert and shared activations, attention combine, merge-add); split32 adds one
attention pass, and one-pass norms further reduce launches. Actual event counts
and device timings are pending. Dead intermediate buffers are retained for ABI
and fixture stability; no memory-saving claim is made.

## Expected value, not a benchmark

Using packet57's 96 retained draft cycles and explicit timing-transfer
assumptions, projected D savings are **0.379–0.395 ms per prompt class**:
analysis 0.381, code 0.395, documentation 0.382, operations 0.387,
prose 0.385, structured writing 0.379 ms. This suggests roughly **1.5% total**
only if acceptance is unchanged. The same projection can be wrong because
BF16/INT8 throughput differs from the target formats. No gap reduction is
credited. `budget.json` records the individual site assumptions and raw event
file hashes; spans include the draft hidden transfer and the gap before the
first merge kernel, matching the brief's roughly 1.77 ms scope. Actual acceptance and class-balanced speed decide.

## Gates and remaining work

The lean CPU gate compares 96 target layer fixtures and all 24 generated
mini-model tokens against packet56; two fresh candidate runs compare 27 draft
proposals and 104,032 bytes of production-K synthetic outputs. There are no
real model weights in these CPU fixtures. The target source check binds 132
retained parent files. All passed; device compilation alone is not device
qualification.

The seal is **screen-only**. The coordinator first runs the new screen tool.
Only all twelve exact prompts and class-balanced rate **greater than
46.962697 tok/s** justify the full packet56-style chain. That later chain must
recompute changed-draft KD expectations with packet59's CPU binary, retain the
same target oracle, measure acceptance, and obtain fresh-repeat evidence before
submission. This preparation does not submit or launch anything.

[Read-only review](REVIEW.md) · [preparation closeout](CPU-PREPARATION-CLOSEOUT.md)
· [do not repeat](DO-NOT-REPEAT.md)
