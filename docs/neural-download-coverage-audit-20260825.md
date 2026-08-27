# neural.download coverage audit — opened 2026-08-25, updated 2026-08-27

This is a current audit of the 16 canonical manifests in
`packages/*/package.json`. It counts only measurements attached to the exact
model, artifact, quantization, runtime, card count, KV type, and workload. A
configured context limit, a projection, a different quant, or a raw engine
batch is never substituted for an unmeasured HTTP deployment.

## What exists

| package-level evidence | packages | coverage |
| --- | ---: | ---: |
| strict or package-qualified headline single-user measurement | 12 / 16 | 75% |
| directly measured decode at approximately 32K or 32K | 13 / 16 | 81% |
| HTTP/service TTFT profile | 6 / 16 | 38% |
| output-audited HTTP concurrency profile | 6 / 16 | 38% |
| sequential-output-invariant HTTP concurrency profile | 0 / 16 | 0% |
| clean-host installation and replay | 0 / 16 | 0% |

The four absent package headlines are intentional, not forgotten cells:
Nemotron 3.5 lost its public number because its raw strict artifacts were not
retained; Ornith 9B has now replayed but matched only 8/12 complete arrays;
Ornith 35B matched 0/12 complete natural-response
arrays across fresh stock servers; Qwen3.8 FP8 failed the same fresh-server
output gate at 8/12. LFM2.5 was formerly in this group, but a preregistered
two-server replay on 2026-08-27 qualified **132.137457 tok/s** with complete
arrays exact 12/12 and all workload/cache/canary gates passing.

The home picker was checked cell by cell on 2026-08-27. Two omissions had
publishable evidence and are now filled: the LFM2.5 strict headline above and
MiniMax M2.7's discrete 32,264-prompt-token production observation at
**63.9086 tok/s** after TTFT. The MiniMax cell is daggered because it used a
64-token output and carries the package's documented historical payload-pin
limitation. Laguna's stored 32,640-token **39.5886 tok/s** diagnostic is not
shown as a number: target-only equality failed every row from 4K through
32,640, so the picker says **withheld after quality failure** instead.

The remaining blank picker cells have no exact, quality-appropriate result for
their displayed tuple. In particular, raw-engine concurrency does not fill an
HTTP cell; a configured 32K capacity with a short active prompt does not fill a
32K-input cell; Q4 target or target-only measurements do not fill Q8+MTP2; and
one topology, quantization, or speculative depth never fills another. Ornith
9B's replay is complete and withheld at 8/12 cross-server equality; Nemotron is
queued for fresh strict replay on this two-card host. The
four-card Laguna, Muse, MiniMax, and DeepSeek service gaps require the four-card
host and remain blank rather than inferred.

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

Qwen3.8 Q8 TP1 now has a separately qualified F16-KV HTTP curve. The exact
64-slot/32K and 32-slot/16K profiles fail device allocation on one 32 GiB B70;
16 slots at 8K total context is the largest measured fit. Two fresh-server
attempts passed the output-isolation and stability gates at 1/2/4/8/16 users.
Aggregate decode peaks at 66.329901 tok/s at eight users and falls to
43.603476 tok/s at 16 on the preallocated p16 baseline. The qualified
eight-active-slot queued profile removes that collapse: its median aggregate
is 68.127528 tok/s at 16 and 68.555544 tok/s at 64 simultaneous requests, a
56.24% gain at 16. Its worst pointwise two-run range is 0.96%. This is
aggregate batch-wall throughput; queued TTFT and per-request latency remain
unmeasured. The capacity failures are not displayed as zero throughput.

Qwen3.8 Q8 TP2 now closes both exact service depth and output-audited
concurrency for its own two-card tuple. At 32K exact prompt depth it measures
33.848820 tok/s decode, 915.09 tok/s server-reported prompt evaluation, and
35.832 s TTFT. The directly measured c1→c64 aggregate curve reaches
163.644206 tok/s at c64. Its non-monotonic c8/c16/c32 shape reproduced on both
fresh servers and is retained rather than smoothed; the worst pointwise range
was 1.455%. Every curve is target-only/MTP0, F16 KV, and separately labeled
from the historical reasoning-enabled headline.

Qwen3.8 official FP8 TP2 now closes its exact one-slot service depth and
output-audited concurrency gaps. The
32K point measures 20.389854 tok/s decode with 21.873 s TTFT; all six 2K→32K
requests were exact-count, cache-zero, and returned 128 token IDs. Its prompt
throughput profile is explicitly the derived `prompt tokens / HTTP TTFT`
effective rate, including scheduling and first-token work—not a server-only
kernel prefill claim. The separate four-active-slot HTTP profile measures
21.585295 / 41.347433 / 81.086716 tok/s at c1/c2/c4. c8-c64 queue and plateau
near 81.5 tok/s; c64 median/p95 TTFT reaches 47.235/93.332 s. Every response
returned 128 raw token IDs with cache zero and passed output isolation.

## Generation and topology comparison policy

- Every public speed must state its generation mode. `Target-only / MTP0`
  means no helper drafted tokens. A named `MTP`, `DFlash`, or `DSpark` result
  states its own depth or policy; those mechanisms are not interchangeable.
- MTP1/MTP2 cells are required only for an exact model/runtime identity that
  has compatible draft weights and a controllable depth. Models without that
  route stay `not applicable` or `not measured`; the site does not fabricate a
  universal MTP ladder.
- A depth ladder changes only depth. Quantization, target/draft artifacts,
  runtime, topology, KV type, graph mode, prompt suite, and quality gate remain
  fixed. Existing Qwen and Gemma family pages expose these matrices and keep
  unmatched historical highs outside them.
- TP1, TP2, TP3, and TP4 are different deployment tuples. A multi-card speed
  never fills a one-card blank, and a missing topology is unknown unless a
  retained boot/allocation result proves it unsupported.

## Exact missing work

| priority | exact tuple or group | missing evidence | why it is still missing |
| ---: | --- | --- | --- |
| 1 | Qwen3.8 27B Q4_K_M TP1 | batch-shape-invariant greedy output for multi-user serving | Realistic HTTP speed/TTFT, exact 2K→32K service depth, and a preregistered output-audited stable HTTP capacity curve are now closed. The corrected 64-slot curve returns complete token IDs and has no cross-base collision, but strict sequential token identity varies for multi-user serving. |
| 2 | Ornith 1.5 35B Q4_K_M TP1 | realistic HTTP TTFT/depth and qualified concurrency | Its context and raw 1→32 engine curves are complete; the service-shaped workload has not yet been run. |
| 3 | Qwen3.8 Q8 TP1, LFM2.5, Nemotron 3.5, Ornith 9B | realistic HTTP TTFT/depth; qualified concurrency for the three small/stock packages; strict headline closure for Nemotron | Qwen Q8 now has output-audited HTTP concurrency but not realistic-prompt TTFT/depth. LFM's strict headline is closed; Ornith 9B replayed and failed cross-server equality at 8/12; Nemotron's replay and stock-package service profiling remain. |
| 4 | Laguna S, Muse-Glimmer, MiniMax M2.7 | decode/prefill/TTFT context curves and qualified concurrency | These are four-card or historical specialist stacks with much higher setup cost; only their promoted workloads were preserved. |
| 5 | all 14 packages | clean-host Intel/oneAPI replay; beginner recovery outside Qwen Q4 TP1 | Every current result was reconstructed or replayed on an established lab host. Qwen Q4 TP1 now has a failure-oriented beginner recovery checklist plus a primary-source clean-host runbook and inventory receipt script. This host has overlapping oneAPI 2025.3/2026.0/2026.1 packages, so it correctly remains uncertified; only a fresh supported OS can close the badge. |

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
3. **Qwen TP2 FP8 active-slot capacity.** Exact context behavior and
   output-qualified concurrency are now measured. Decode falls only from 21.84
   tok/s at 2K to 20.39 at 32K, while four active users reach 81.09 aggregate
   tok/s. c8-c64 plateau near 81.5 because the package admits only four active
   sequences. The next matched screen is a separately identified eight- and
   sixteen-slot service profile, followed by scheduler or collective work if
   active throughput remains weak.
4. **Laguna/Muse/MiniMax context profiles.** These are expensive four-card
   lanes. Fill the missing service curves before changing kernels so a later
   improvement has a matched baseline.
5. **Small stock models.** LFM2.5, Nemotron, and Ornith 9B already have useful
   one-card baselines and 32K raw curves. Their next value is user-shaped HTTP
   and concurrency coverage; speculative kernel work waits for a measured
   bottleneck.

## What this two-card host can execute next

The locally staged, exact artifacts support more Qwen work without another
download: Qwen3.8 Q4_K_M/Q8_0/FP8/INT4 plus its MTP drafts, and Qwen3.6
Q8_0/AutoRound INT4/DFlash plus its draft artifacts. The next matched service
tuple is official FP8 TP2 active-slot capacity, followed by the remaining
Qwen3.6 depth/topology cells where a compatible runtime exists.

MiniMax M2.7 artifacts are checksum-verified in USB cold storage because its
promoted deployment needs four B70s, so this host cannot honestly fill that
four-card service matrix. The first-wave
model share is mounted. LFM2.5 was copied to local NVMe and its strict pair is
complete. Ornith 9B was staged to local NVMe and completed the same two-attempt
gate, which withheld its headline at 8/12 output equality; Nemotron follows.
Network-storage timing is excluded from benchmark attempts.
Four-card Laguna, Muse, MiniMax, and DeepSeek gaps stay assigned to a four-card
machine rather than being approximated here.

## Completion rule

A blank becomes a number only when the exact package tuple has a retained raw
artifact, workload definition, output/quality gate appropriate to the claim,
and a linked reproduction path. Failed and diagnostic runs stay visible in
notes and limitations; they do not silently become home-page recommendations.
