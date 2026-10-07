# After 104: finish the client decision, then work on sampler service

Independent CPU-only review; no application requests, source changes, builds, or lifecycle actions. Reviewed with the performance agent.

The next concrete step should be **one quiet, reversed-order comparison of the same ten fixtures: storage-change-only first, always second**, followed by closing this client experiment. This is worthwhile because 104's observed 6.20% improvement is large enough to matter but its fixed control-first order leaves warmup/drift unresolved. Do not build a ladder of additional client microtrials. Preserve the reduced-write policy as a maintenance improvement even if the timing result becomes inconclusive; qualify its speed claim separately.

This requires a newly authorized immutable schedule. The retained 104 application is idle and healthy, but its 71-request plan is consumed and its fast phase explicitly requires `control_verified`. Do not append requests or silently relax that barrier. A successor must explicitly admit fast after the existing exact candidate gate and verify the final comparison after both blocks, retaining all source, fault, storage, event-fsync, and output checks. Prefer incorporating this single pair into the next necessary successor; a dedicated reload/requalification has a real cost for a small effect. Any controlled application reload belongs to the main agent's lifecycle decision, with no restart chain.

## What 104 actually established

Evidence root: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-client-compare-104-two-way-w2-b1-p1-dxpu2-s640x384/`. Primary receipts are `same-size-native-references.json`, `same-size-candidate-check.json`, `same-size-timed.json`, `same-size-timed-fast.json`, and `resolution-campaign-result.json`. Sealed source packet: sibling `prepared-client-compare-104/`, manifest SHA256 `49892a00ece1cf4a7d84ce5d03e6a9c2290ffc3af9b2822ba4866e72cfa2e93a`.

Twenty native requests and thirty scored optimized outputs passed the four-tensor exact comparisons. Both timing blocks used ten original fixtures, four unscored fills, 640×384×25 frames, W2/B1, window 64, native BF16, unchanged 8+3 denoising steps, and unchanged 23/25 block placement. These are generated-frame throughput measurements of a repeated workload, not playback rate, cold-start performance, or a new general benchmark record.

| Observation | Always/control | Storage-change-only/fast |
| --- | ---: | ---: |
| Generated FPS, nine completion intervals |12.03981|12.78627|
| Mean completion interval |2.07644s|1.95522s|
| Storage checkpoint calls, all 14 requests |1284|1392|
| Storage-ledger saves |1284|668|
| Unchanged saves skipped |0|724|
| Emitted sampler service, ten scored clips |3.72905s|3.75958s|
| Emitted decoder service, ten scored clips |2.83138s|2.88524s|
| Prompt-thread sampler wait, scored request rows 04–13 |0.01127s|0.79156s|

Worker service comes from sampler rows 02–11 and decoder rows 04–13: their emitted clip indices, rather than submission row numbers, select the ten scored outputs. The mean gap from one server completion to the next server start falls from 1.20444 s to 0.28756 s for scored successor rows 05–13. Much of this newly available time becomes a sampler wait; only about 0.12122 s survives as an average end-to-end interval reduction. This is consistent with improved pipeline feeding, not faster sampler or decoder computation. The fast arm actually made more checkpoint calls while saving fewer ledgers.

## Where the larger opportunity now lies

Sampler service is the strongest measured next bottleneck: fast mean service divided by two workers is 1.87979 s versus 1.95522 s observed delivery. That rough capacity comparison is suggestive, not a utilization measurement or a guaranteed achievable bound. Decoder service divided by two slots is about 1.44262 s, and prompt-thread decoder waits remain about 0.014 s. Blindly adding a third sampler worker is not justified by these receipts.

Current `emitted_phases` do **not** measure the two GPU partition durations. They describe denoising stage A and B. Fast scored means are 2.52277 s for `concat_a->sample_a` and 1.16527 s for `concat_b->sample_b` (control 2.48478 s and 1.16947 s). Those stages have different geometry and 8 versus 3 steps; their ratio cannot select a better 23/25 block split. `route_busy_ms` is disabled in 104 by `LTX_BUSY_WINDOWS=0`. The existing per-replay busy-window implementation in sealed `source/scripts/ltx_graph_capture.py` can supply route/card occupancy evidence in a separately identified diagnostic. Card event intervals spanning whole stages include idle time and must not be relabeled utilization.

After the single reverse comparison, prioritize a bounded measurement of sampler route occupancy and transfer/fence time at 640 before selecting one partition or transfer change. A measured imbalance could make placement more valuable than W3; the old small-shape 20/28 screen is neither proof nor justification for a broad sweep. Keep that diagnostic separate from quiet performance claims and retain exact output checks.

The earlier [follow-up lever note](2026-10-07-follow-up-levers.md) identifies duplicate decoder/preview/raw-capture host copies. They remain plausible, but 104 does not isolate their cost: the roughly 0.10–0.11 s client-observed node 414 interval includes observation effects, and enqueue timings begin after private copies. Do not remove ownership-protecting copies without measured benefit and an explicit lifetime design. Similarly, staged sampler transfers deliberately use pinned host buffers to avoid a historically worse peer-copy path; a direct P2P rewrite is not automatically an improvement.

Higher resolution is a useful capability extension after this decision, with its own exact native oracle and fresh memory admission. It should not be presented as a speed improvement over 640. The goal is a reliably faster useful generator; the stopping rule here is one more client comparison, then a different, evidence-supported lever—not indefinite confirmation of a six-percent result.
