# One proposed two-card rebalance: 20/28 versus 23/25

Status: **offline proposal, not implemented or measured**. This note records a
bounded next-lever option after the newest-upstream base-99 control qualifies.
It authorizes no launch, placement change, expanded grid, or host setting change.
The coordinator selects the next lever from the qualified control's evidence.

## Why this remains a useful question

The accepted packet-97 batch-one path uses 23 transformer blocks on card 0 and
25 on card 1, two sampler workers, shared graph pools, and the second decoder
on card 2. Its timed arm reports 1.3082 seconds per emitted 25-frame clip and
compute-engine seconds per clip of **1.2095 / 0.9634 / 0.8808 / 0.8440** on
cards 0–3. Card 0 is now the busiest. Moving blocks 20–22 from card 0 to card 1
keeps two transformer segments and the same inter-card boundary count.

Propose exactly one alternative: **20/28**, compared with the unchanged
**23/25 control**. Keep batch one, two sampler workers, shared pools, decoding
on card 2, native BF16 models, original sampling, 256×256 output, 25 frames at
24 fps, and the accepted short-window encoder unchanged. Do not combine this
arm with conditioning-cache, worker-count, batching, precision or kernel changes.

The bounded audit found no 20/28 or 21/27 accepted-batch-one result after the
decoder moved to card 2 in packet-97/98 summaries and the lane notes inspected.
This is not an exhaustive claim about all unindexed artifacts.

## Projection, not a measurement or an 8% guarantee

As a rough planning proxy, card 1's compute counter divided by its 25 blocks is
`0.9634 / 25 = 0.038536` seconds per block. Moving three such units gives:

| Quantity | Projected value |
| --- | ---: |
| Card 0 compute seconds per clip | 1.093892 |
| Card 1 compute seconds per clip | 1.079008 |
| Reduction of busiest-card counter | 0.115608 s |
| Clip time if that entire reduction transfers to wall time | 1.192594 s |
| Corresponding clip-time reduction | 8.84% |

Compute-engine counters can include waits and do not isolate movable block
work. Glue, transfers, queueing, allocation and scheduling need not remain
constant. The older block-time estimate of 0.0327 seconds would instead suggest
only about 7.5% wall-time reduction under the same optimistic assumption.
Consequently **8% or greater is plausible enough to screen, not promised**.
Even the optimistic estimate does not meet the lane's under-one-second goal.
No benefit from context reuse has been measured here, so this is not a measured
comparison against that candidate either.

## Bounded memory estimate

The matching packet-97 B1/W2/shared-pool/card-2-decoder freeze receipt recorded:

| Card | Free GiB after whole-chain check |
| --- | ---: |
| 0 | 7.534 |
| 1 | 12.319 |
| 2 | 9.741 |
| 3 | 14.564 |

The existing `ltx_layer_shard.py` planner charges **0.97 GiB per block**:
approximately 0.720 GiB of BF16 weights plus 0.25 GiB for graph statics and pool
share with two workers. Charging three added blocks to card 1 gives
`12.319 - 3 × 0.97 = 9.409 GiB`; an additional 0.25 GiB safety pad leaves
**9.159 GiB**, comfortably above the unchanged 2 GiB floor. Conservatively do
not credit card 0 for released blocks. The saved whole-chain check budget was
359,661,688 bytes per transformer card; its transient admission remains required.

This is a feasibility estimate, not a new live admission receipt. Base-99's
upstream changes may alter allocation and capture costs. Recompute from its
qualified control, retain pre-capture and live worker checks, and enforce the
existing whole-chain-check and post-check freeze floor without overrides.
The old pool calibration is evidence, not a transferable candidate calibration.

## Minimal implementation dependencies, only if selected

Preserve all sealed packets and their original source/control-port evidence.
Implement a successor alternative with a distinct name such as
`two-way20-28`; do not redefine the existing `two-way` name.

1. Add the exact named segments `(('xpu:0', 0, 20), ('xpu:1', 20, 48))` to the
   successor `ltx_layer_shard.py` placement inventory. Existing
   `host_embedding_resident_node.py` dispatches named alternatives through
   `apply_layer_segments`, and `graph_capture_node.py` checks exact named segment
   membership and owner accounting. Verify the two-segment ownership path and
   unchanged numerical routing; do not merely assume it equals the old install
   path because both use two cards.
2. Review and update `ltx_graph_capture.py`'s shard-source SHA pin, the packet
   manifest placement inventory, and `encoder_runtime_common.py`'s exact
   placement allowlist. Keep all numerical-source and runtime checks intact.
3. Give the successor launcher, runner and memory planner explicit support for
   this one name. Current packet-98 run-name and layout tables reject it. Assign
   distinct output names and clip indices within the existing ceiling; do not
   reuse control indices or expand the historical matrix formula casually.
4. Give the new layout its own memory basis and receipts. Do not silently reuse
   a `two-way` calibration under a different name or claim unknown-layout
   admission from the old hard-coded tables.
5. CPU controls must check exact coverage of all 48 blocks, one owner per block,
   two-card boundary/ownership behavior, strict unknown-name refusal, unchanged
   numerical operations, source-hash binding and memory-floor refusal. Then
   independently review the candidate before any GPU work.

No transformer arithmetic, model weights, accepted references or graph-pool
semantics should be changed as part of this placement-only question. Any
necessary upstream port changes belong in the separately qualified base first.

## Comparison identity and exact quality gate

There are two distinct qualification steps; preserve receipts for both:

1. **Qualify the source/control port first.** Freeze the base-99 source/runtime
   identity and show that its unchanged 23/25 batch-one control passes the
   accepted `stability-01-w93c-*` reference checks. Historical packet 97/98
   output and timing receipts remain intact. A failed port does not qualify a
   placement experiment or justify replacing the accepted references.
2. **Compare two identified arms on that same qualified base.** Record full
   source, manifest, launcher, environment, model/revision, graph, worker, pool,
   decoder, output-size and fixture identities for control and candidate.
   The intended numerical-work difference is only block placement. Preserve
   the reviewed source delta and all derived hash changes. Do not attribute a
   packet-97-to-base-99 speed difference to this rebalance.

Before timed work, require complete graph captures on both stages and both
workers, whole-chain replay/eager and replay/repeat bit equality, native/replica
decode equality, freeze and ownership checks, and the post-freeze self-check.
Then require **all ten accepted w93c fixtures to match every saved tensor
exactly**, with context-sentry and emission-sequence checks passing. Run the
bounded timed arm only after those gates pass, and require exact reference
parity for every emitted timed clip as well. Preserve mismatches and halt new
requests on any fault; no automatic retry/restart or reference regeneration.
No throughput result is a win if any exactness or health gate fails.

Use the same measurement definition and fixture order in both arms. Report
elapsed clip time, busy counters, scheduling, memory, stalls and exactness,
including an inconclusive outcome when variance or identity differences prevent
attribution. Retain the 50 GiB disk reserve plus the separately admitted full
output/cache budget. A selected candidate would need its own controlled
application load; this note does not start a reload chain.

## Prior results that this does not reopen

- [Packet 84](graph-capture-84-results.md) changed 21/27 to 23/25 and measured
  about 1.9% improvement. It predates the accepted short-window encoder, lean
  conditioning, shared pools and decoder relocation. It is real historical
  evidence, but not a matching negative test of the present question.
- [The original split design](split-rebalance-design.md) supplies historical
  weight/block-cost reasoning. Its old host-setting and recovery suggestions
  are not current instructions.
- [Packet 94f](2026-10-04-packet-94f-results.md) and the subsequent spread-layout
  work found additional transformer-card boundaries slower. Do not reopen the
  broad three/four-card grid; this proposal retains two segments.
- [Packet 97](2026-10-06-packet-97-results.md) already tested extra decoder and
  batch-two worker variants without useful improvement. Batch-two/four rounded
  outputs and their private references remain outside this unchanged-quality
  candidate.

## Exact evidence used

All three receipts are under
`data/place-97/two-way-w2-b1-p1-dxpu2/`, with accepted source packet manifest
`6e232f72a9835727323c383bc9baaa167844b58dc6400a5de43a3b9eb4e44b9f`.

| Receipt | SHA-256 |
| --- | --- |
| `summary.json` | `1cff36d560958f05b0dd902abf87ef29104cbe308dd23cc7e7331c4f34524628` |
| `sampler-capture-freeze-f97-twowayw2b1p1dxpu2-freeze.json` | `c54180c9e466452c58d574ebd26c6eb8e84c693c214625b06d51e0b85c1644a9` |
| `pool-calibration.json` | `083133144030c57736fdc0c4b9ae14bcba9122807b3b3e68544528f88b0941fd` |

Source contracts were read from sealed packet 98 at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98/`
and its tracked builder/planner. The inspected shard source SHA-256 is
`9caaec0aeb68e9f391fab5ae9b6a63e464aa62a99e1ffc449775b3687d2149b2`.
This audit made no GPU, endpoint, Docker, systemd or host-setting calls.
