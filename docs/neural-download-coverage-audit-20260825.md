# neural.download coverage audit — 2026-08-25

This is a point-in-time audit of the 14 canonical manifests in
`packages/*/package.json`. It counts only measurements attached to the exact
model, artifact, quantization, runtime, card count, KV type, and workload. A
configured context limit, a projection, a different quant, or a raw engine
batch is never substituted for an unmeasured HTTP deployment.

## What exists

| package-level evidence | packages | coverage |
| --- | ---: | ---: |
| headline single-user measurement | 14 / 14 | 100% |
| directly measured decode at approximately 32K or 32K | 8 / 14 | 57% |
| HTTP/service TTFT profile | 2 / 14 | 14% |
| output-audited HTTP concurrency profile | 2 / 14 | 14% |
| sequential-output-invariant HTTP concurrency profile | 0 / 14 | 0% |
| clean-host installation and replay | 0 / 14 | 0% |

The home picker had an additional publication defect: it showed only one of
the eight existing 32K measurements. This audit wires the directly measured
Gemma 4, LFM2.5, Nemotron 3.5, Ornith 35B/9B, and Qwen3.8 Q4 values into the
picker. Qwen3.8 Q8 and the 256K capability package retain their curves on the
Qwen family/package pages rather than creating redundant home-page routes.

Raw aggregate measurements now remain visible but explicitly distinct from a
user-serving claim:

- Ornith 1.5 35B: 216.513077 tok/s at 32 raw concurrent engine sequences;
- Qwen3.8 27B Q4_K_M: 95.411842 tok/s at 64 raw concurrent engine sequences.

Neither raw tool emits auditable completions or includes HTTP and scheduler
overhead. They are ceilings and optimization evidence, not substitutes for a
service profile. Qwen Q4 TP1 now separately has an 83.796743 tok/s measured
64-user native HTTP point with complete raw token IDs, cache off, two
fresh-server attempts, and an explicit batch-shape output warning.

After the initial census, Qwen3.8 Q4 TP1 completed a qualified cold
realistic-prompt HTTP run and an exact 2K→32K HTTP decode/TTFT sweep. The
realistic suite passed 12/12 registered outputs at 27.785930 tok/s median and
262.869 ms median TTFT. The exact 32K point passed cache/truncation/token gates
at 24.488129 tok/s and 50.267 s TTFT. Its repeated-token depth fixture is
explicitly grade C and is not presented as long natural prose.

Qwen3.8 Q4 TP2 now also closes exact service depth and output-audited
concurrency on its exact two-card tuple. Its 32K HTTP point is 44.437281 tok/s
with 35.059 s TTFT. Its two-attempt 1→64-user aggregate curve peaks at
165.387286 tok/s; all responses were complete and isolated, cache reuse was
zero, and the worst pointwise relative range was 1.717%. Greedy text remains
batch-shape-dependent and is not described as sequentially invariant.

## Exact missing work

| priority | exact tuple or group | missing evidence | why it is still missing |
| ---: | --- | --- | --- |
| 1 | Qwen3.8 27B Q4_K_M TP1 | batch-shape-invariant greedy output for multi-user serving | Realistic HTTP speed/TTFT, exact 2K→32K service depth, and a preregistered output-audited stable HTTP capacity curve are now closed. The corrected 64-slot curve returns complete token IDs and has no cross-base collision, but strict sequential token identity varies for multi-user serving. |
| 2 | Ornith 1.5 35B Q4_K_M TP1 | realistic HTTP TTFT/depth and qualified concurrency | Its context and raw 1→32 engine curves are complete; the service-shaped workload has not yet been run. |
| 3 | LFM2.5, Nemotron 3.5, Ornith 9B | realistic HTTP TTFT/depth and qualified concurrency | These were first brought in as stock one-card packet baselines and depth-screened with `llama-bench`; package work outpaced service profiling. |
| 4 | Laguna S, Muse-Glimmer, MiniMax M2.7 | decode/prefill/TTFT context curves and qualified concurrency | These are four-card or historical specialist stacks with much higher setup cost; only their promoted workloads were preserved. |
| 5 | Qwen3.8 Q8/FP8 TP2 | 32K service/depth profiles and qualified concurrency | Exact two-card single-user baselines exist, but the Q4_K_M result cannot populate a different quant/runtime tuple. Q4_K_M TP2 is now closed for these service profiles. |
| 6 | all 14 packages | clean-host Intel/oneAPI replay; beginner recovery outside Qwen Q4 TP1 | Every current result was reconstructed or replayed on an established lab host. Qwen Q4 TP1 now has a failure-oriented beginner recovery checklist plus a primary-source clean-host runbook and inventory receipt script. This host has overlapping oneAPI 2025.3/2026.0/2026.1 packages, so it correctly remains uncertified; only a fresh supported OS can close the badge. |

## Optimization queue

Measurements, not model popularity alone, set this order:

1. **Qwen3.8 Q4 TP1 concurrency.** Output-audited HTTP reaches 83.796743 tok/s
   at 64 users versus the 95.411842 tok/s raw-engine ceiling. The current
   low-latency build has the Q4_K oneDNN WDC path disabled. Broad
   forced-reorder attempts exceeded memory or did not engage; the next valid
   optimization is the bounded source-level Q4_K-only WDC door, followed by
   the same token-audited endpoint and batch-shape comparison.
2. **Ornith 35B service batching.** Single-user decode is already strong at
   131.460231 tok/s, but 32-way raw aggregate is only 216.513077 tok/s. This is
   the clearest practical batching/scheduler and batched-MoE kernel opportunity.
3. **Qwen TP2 Q8/FP8 context and service behavior.** Measure first. Q4_K_M now
   has exact service-depth and output-audited concurrency curves; its other
   quant/runtime tuples still do not reveal whether their weak point is
   long-context attention, collectives, scheduling, or weight traffic.
4. **Laguna/Muse/MiniMax context profiles.** These are expensive four-card
   lanes. Fill the missing service curves before changing kernels so a later
   improvement has a matched baseline.
5. **Small stock models.** LFM2.5, Nemotron, and Ornith 9B already have useful
   one-card baselines and 32K raw curves. Their next value is user-shaped HTTP
   and concurrency coverage; speculative kernel work waits for a measured
   bottleneck.

## Completion rule

A blank becomes a number only when the exact package tuple has a retained raw
artifact, workload definition, output/quality gate appropriate to the claim,
and a linked reproduction path. Failed and diagnostic runs stay visible in
notes and limitations; they do not silently become home-page recommendations.
