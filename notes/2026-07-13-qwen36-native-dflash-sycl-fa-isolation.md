# Qwen3.6 native DFlash: draft-KV correctness isolation

Date: 2026-07-13 UTC

## Success and why it matters

This is the first valid local Qwen3.6 27B lane to break the 68 tok/s milestone
on one B70: `73.91 tok/s` with native Q8 DFlash and `74.01 tok/s` with the
existing Q4_K_M draft on favorable code. The result does not satisfy the strict
100 tok/s TP1 objective and must not be represented as mixed-workload speed;
its importance is that it reverses a false technical conclusion.

We had treated native DFlash as nearly unusable because only 0.35-1.49% of its
drafted tokens were accepted. The actual problem was the Q8_0 native-draft KV
cache, not the DFlash algorithm, draft weights, or Q4 weight quantization. The
first A/B changed both flash attention and draft KV type, so its initial
flash-mask conclusion was confounded. The missing control—FA on, F16 draft
KV, identical Q8 draft weights—restored 100/106 acceptance (94.3%) and
73.47 tok/s. Flash attention itself is therefore exonerated by current
evidence; the catastrophic failure follows Q8_0 draft KV.

The resolution is to keep native DFlash draft K/V in F16 while retaining flash
attention for both the draft and target. The temporary DFlash-specific FA
bypass was removed. A focused backend regression covering D=128, GQA4,
Q8-K/F16-V, full and wrapped iSWA cache layouts, and DFlash-style sparse masks
passed 12/12 against CPU. Q8-K NMSE was `3.72e-6` to `6.52e-6`, maximum
absolute error below `9e-4`, with zero argmax mismatches over 960 tested rows.
Current evidence therefore favors model-level DFlash sensitivity to Q8 K-cache
quantization rather than a generic SYCL FA kernel defect. F16 draft K remains a
model-specific correctness requirement.

This matters to the main objective because DFlash's long accepted blocks are
still the clearest way to amortize a 27B target pass enough to approach 100
tok/s on TP1 or 200 tok/s across multiple B70s. It also prevents future agents
from discarding DFlash, blaming Q4, or attempting to solve the wrong 1 ms host
boundary. With correct drafting, measured timing identifies the width-6 target
verifier at about 58.7 ms as the dominant engineering target.

## Why this was tested

The earlier native DFlash Q4_K_M run accepted only 6 of 1695 drafted tokens.
Upstream Q4 results are materially better, so this was treated as a backend or
executor correctness failure rather than ordinary quantization loss.

## Identity

- Target: `Qwen3.6-27B-Q4_0.gguf`, SHA-keyed RAM cache path
  `/dev/shm/qwen27-b70-model-cache/20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a/`
- Native draft: `williamliao/qwen3.6-27B-DFlash-GGUF`, revision
  `406f95903d0a7a6926ae5fd29be3b0fcf9613014`
- Draft file: `Qwen3.6-27B-DFlash-Q8_0.gguf`
- Draft SHA256: `c37b84724fa58cc5c6b545d8b96f8617a8c3bd7f018bf608feef4d3460e0575e`
- Runtime: local llama.cpp SYCL JIT build
  `build-sycl-b70-qwen36-mtp-jit`
- GPU: Intel Arc Pro B70, TP1, one active generation
- Graph capture disabled
- Greedy request, Python `merge_sort` code prompt

## Correctness discriminator

With SYCL flash attention and Q8_0 draft KV, native DFlash at `n_max=4` was
broken:

- 7 accepted / 470 drafted (1.489%)
- mean emitted length 1.06
- 16.69 tok/s for 128 completion tokens

With flash attention disabled and draft KV in F16, the same native Q8 model and
prompt produced:

- 100 accepted / 106 drafted (94.34%)
- mean emitted length 4.70
- 73.38 tok/s for 128 completion tokens

That comparison was initially insufficient because it changed two variables.
The decisive control used FA on with F16 draft KV and produced 100/106 accepted
(94.3%), mean length 4.70, and 73.47 tok/s. Q8_0 draft KV—not FA—is the isolated
failure condition. Q8 draft *weights* do not repair or cause the cache problem.

The existing Q4_K_M draft also recovered with F16 draft KV: 104/115
drafted tokens accepted (90.4%), mean length 5.52, and 74.01 tok/s. Therefore
Q8 weights are not required for favorable code correctness; the original Q4
failure was also caused by its Q8_0 draft KV configuration.

## Four-card block-depth screen

The remaining three B70s screened longer blocks concurrently. Flash attention
was off, draft KV was F16, and custom fusions/graphs were off.

| `n_max` | accepted / drafted | mean emitted length | decode tok/s |
|---:|---:|---:|---:|
| 4 | 100 / 106 | 4.70 | 73.38 |
| 5 | 137 / 150 | 5.57 | 75.20 |
| 8 | 139 / 144 | 8.72 | 48.19 |
| 15 | 146 / 165 | 14.27 | 64.47 |

The prompt was favorable code and is not a promotion benchmark. `n_max=5` was
the best shallow screen; larger verification blocks cost too much in the
current generic verifier despite excellent acceptance.

## Strict realistic suite

`n_max=5`, native Q8 DFlash, FA off, F16 target/draft KV, graphs and custom
fusions off:

- result:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/native-dflash5-q8-faoff-20260713T021705Z.json`
- strict gate: passed, 12/12 prompts uncached
- median tokens 1-100 after TTFT: **40.203 tok/s**
- p10: 31.181 tok/s
- mean: 39.666 tok/s
- mixed-prompt per-request native acceptance ranged roughly 26.6% to 49.5%
  in the retained server log
- retained server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/native-dflash5-q8-faoff-20260713T021705Z/server.stdout.log`

This is a valid negative production result but a major correctness milestone:
native DFlash is now usable on SYCL with FA and F16 draft KV, and the favorable-code lane
exceeds 68 tok/s. The mixed suite is still below the MTP production floor.

A corrected current-configuration rerun used FA on, target KV8, draft F16 KV,
and the native DFlash5 profile. It passed all cold/cached-zero gates at
`37.967 tok/s` median (`32.001` p10, `38.204` mean):

`data/qwen36-27b-mtp-gguf-q4-b70-baselines/native-dflash5-q8-f16kv-faon-20260713T024247Z.json`

This supersedes the FA-off run as the configuration identity, but does not
change the production conclusion: mixed acceptance is still too low, while
the favorable-code lane remains useful and must be routed.

## Measured complete-cycle decomposition

Opt-in timing (`LLAMA_DFLASH_CYCLE_TIMING=1` plus
`LLAMA_MTP_CYCLE_TIMING=1`) on a representative prose request at `n_max=5`
showed steady-state cycles of approximately:

- target width-6 verification: 58.6-58.8 ms
- DFlash feature gather + encoder + KV injection: about 1.0 ms
- DFlash width-6 block decode + host sampling: about 10.0 ms
- acceptance + commit: about 0.3-1.2 ms depending on accepted length
- total: about 70-71 ms per cycle
- request mean emitted length: 2.70; decode: 38.40 tok/s

The missing time is now measured rather than inferred: the generic width-6
target verifier dominates. Host-mediated DFlash feature injection is architecturally
undesirable for multi-GPU work, but it is only about 1 ms on this TP1 run. The
next decisive TP1 kernel is the offline-packed Xe2 small-M verifier.

## Decision

1. Keep native draft KV in F16 and isolate the Q8_0 draft-cache failure with
   tensor/cache parity tests before attempting to recover KV8 memory savings.
2. Profile the complete `n_max=5/8/15` cycle. High acceptance is being erased by
   the generic small-M verifier and host-mediated DFlash feature/KV injection.
3. Build the offline-packed Xe2 DPAS verifier and GPU-resident DFlash boundary.
4. Preserve native DFlash as a routed high-ceiling lane while mixed-suite
   acceptance remains workload-dependent.
