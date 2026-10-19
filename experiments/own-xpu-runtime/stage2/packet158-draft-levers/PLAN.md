# Packet158: make the draft faster without changing a byte

**Design-only handoff.** The two-card record remains58.798 tok/s, packet136
bundle8. No build, model payload read, GPU work, service or queue edit happened
here. The two ready-to-start **CPU build briefs** are
[routed experts](briefs/routed_experts.md) and
[input norm/embedding mix](briefs/input_norm_embedding_mix.md).
They are not device-ready packets and this directory has no READY marker.

## Evidence and ranking decision

Packet154 measured1.227 ms/interval of rank0 wait overlapping rank1 draft,
with draft_issue median1.571 ms/cycle. Packet147's+2% threshold is approximately
0.423078 ms/hit net saving. Packet156's current suffix window has only enough
room for0.29–0.32%, packet120's25/23 split lost3.9%, and packet79's rank0 draft
lost. Those mechanisms remain closed. Only the draft's internal work changes.

At the initial poll, packet157's first smoke failed its first-request analyzer
with **`host duration disagrees`**. It supplies no valid ranking. A repaired
`device-p157b-smoke-A` appeared during preparation. Final polling state and
hashes are retained in [packet157-status.json](evidence/packet157-status.json).
Do not use incomplete output or a smoke's raw time as a completed v5 result.

Until a valid packet157 split summary lands, the best completed device evidence
is packet122's two full-draft micro processes, each forty measured replays at
128 and4096 occupied tokens. We recomputed **group means from whole-step event
sums**, rather than adding class medians or copying the note's mixed-context
figures. Both short-context processes choose the same top two gaps. The fallback
is128 occupied tokens because this is the short cold-decode lever;4096 is a
separate context sensitivity case, not a substitute live measurement.

The ranked **gap** is measured group time minus its useful-byte/537 GB/s
reference. Packet157's analyzer itself sorts **raw device time**; that order
cannot answer which group has the largest gap. Neither order proves attainable
saving. Source/kernel line ranges, bytes, FLOP formulas and host caveats are in
[SOURCE-MAP.md](SOURCE-MAP.md); exact process values are in
[ROOFLINE.md](ROOFLINE.md) and [roofline.json](roofline.json).

| Rank, fallback128 | Group | Device ms | Reference ms | Signed gap ms | Proposed action and saving bound |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | Routed experts |0.307689|0.144742|+0.162947| Build paired-scalar input reuse. Changed gate/up about0.081 ms is the hard historical whole-operator ceiling; engineering scenario0–0.024 ms, not measured. Close if compiler already shares inputs. |
| 2 | Input norm/embedding mix |0.184503|0.074067|+0.110435| Build four-RHS hidden projection. Changed operator about0.060 ms is a tighter historical ceiling; engineering scenario0–0.024 ms. Logical-byte scale0.073225 ms does not override that ceiling. |
| 3 | Attention |0.088526|0.000792|+0.087734| Contingency: unchanged fixed32 value-tree scheduling, described below. Register/spill evidence required; no numerical expected saving is justified. |
| 4 | Attention projections |0.232592|0.191736|+0.040856| No new mechanism qualified here. Dense weight reads dominate the reference; do not revive packet59 all-on or packet101 geometry. |
| 5 | Final norm/HC |0.054807|0.024688|+0.030119| No HC remapping/fusion replay; packet122 closed. A distinct mechanism needs new compiler/substage evidence. |
| 6 | Argmax/publication |0.026355|0.000299|+0.026057| Historical timing excludes publication copies. No claimed saving; keep stable ties, sticky errors and completion ordering. |
| 7 | Shared expert |0.041962|0.018368|+0.023594| No target shared-tuple interleave revival; no format or activation-order change. |
| 8 | Head GEMV,80128 rows |0.445348|0.477793|−0.032446| No supported bandwidth gap. Fixed prefix and head arithmetic remain. Largest raw time is not automatically the largest exact opportunity. |
| Separate overlapping clock | Host issue |1.571 median/cycle|not applicable|unresolved| Existing reads, drains, submission and device overlap; never claim all1.571 ms removable or add to the device sum. |

All saving bounds above refer to the historical diagnostic identity. They are
neither certified bounds on packet136 live execution nor new benchmark claims.
Even erasing both positive reference gaps at128 tokens would total only
0.273382 ms/draft, below0.423078 ms/hit, before critical-path transfer costs.
That comparison is an optimistic planning screen, not a matched elapsed-time
proof. The two concrete mechanisms address smaller subsets: at most about
0.141 ms if their entire historical operators disappeared, which they cannot.
Do not turn these briefs into a claim that+2% is established.

At4096 occupied tokens the measured ranking changes: attention gap0.601355 ms,
routed0.165700 ms, input0.127683 ms. This identifies why packet157's natural
position distribution matters. No interpolation turns those two measured
points into a context-performance curve.

## What to launch for every packet157 outcome

First require a **complete, valid real** C/T/C/T/C summary, all13 exact/view,
identical proposals, complete event census and reviewed instrumentation overhead.
Rerun:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet158-draft-levers/analyze.py \
  --split-summary experiments/own-xpu-runtime/stage2/packet157-draft-decomp/v5/evidence/<completed-run>/bracket-summary.json </dev/null
```

This averages the byte model at each measured occupied position using the same
equal-prompt/view means as packet157. It does **not** interpolate times. Inspect
`overhead` in that summary: host and device times overlap, and a perturbation
that changes group ordering makes the timing verdict uncertain, not new spare
time. Regenerate the ranking prose/brief priority in a focused commit if needed.

| Valid gap-ranking outcome | Exact launch decision |
| --- | --- |
| Routed then input, or input then routed | Launch the corresponding two briefs above in that order, as independent packet159 trees. CPU preparation may precede device admission. Do not combine their speed estimates. |
| Only one of routed/input is in the top two | Launch that matching brief in its ranked position. Do not launch the displaced brief merely because it is already written. For the other group follow the row below; replace the displaced brief before its CPU build. |
| Attention is in top two | Use the **input brief's full preparation/smoke/v5/storage/READY contract**, but materialize a new `briefs/attention.md` for `stage2/packet159-attention/` with the exact mechanism and byte shapes below, replacing only its mechanism/proof section. This is a defined contingency, not an already built or qualified third arm. |
| Head is high by raw time but has nonpositive gap | Launch neither a new head nor prefix arm. Select the actual top positive gaps; the raw analyzer label does not reopen106/114 or wide heads. |
| Attention projections, final norm, shared expert or argmax is a top gap | Neither current mechanism targets it. Start a bounded CPU source/codegen audit under the **routed brief's preparation contract**, rewrite its mechanism/real-shape proof for that exact group, and require a distinct measured substage/byte mechanism before a build. No blind submission batching, whole-graph replay, existing fusion or geometry sweep is a ready design. The mapping is explicit: current briefs must not be relabeled as optimizing these groups. |
| Host issue dominates while device gaps are small | Neither device brief cures unassigned host time. Use the routed brief's real-argv CPU probe contract to locate embedding read/decode, drains or preparation cost; retain the unchanged confirmed-token transaction. No suffix-slack or graph-replay revival. |
| Missing/failed/empty/incomplete packet157, or overhead invalidates ranking | Use the completed128-token fallback and launch routed then input. Keep current live timings pending. The4096-only attention result does not displace them without matching live evidence. |
| All gaps nonpositive or tied within uncertainty | Retain signed values; no claimed opportunity. For ties among routed/input use routed first (larger measured substage), for any unprepared tied group obtain substage/codegen evidence before choosing. Do not substitute a closed design. |

This rule covers arbitrary permutations without pretending two group-specific
briefs optimize all eight groups. A future summary may warrant replacing one;
the requested two are chosen from the completed evidence available at handoff.

### Attention contingency, exact mechanism and proof specification

The selected path is implementation12: packet136 `adapter.cpp:320` →
`p49_qsa_submit.cpp:29–31` → `p49_qsa_kernel.hpp:43–73`. Only change the
`tiles<true>` value-tree **evaluation schedule**, lines59–61. It currently
materializes32 `vec<float,2>` leaves per lane and then reduces the fixed tree.
For j=0..31 form the exact same leaf (same selected ID, BF16 V load,
`local[32+j]*bf(v)`, or +0 padding), and use compile-time binary-carry slots:
when a right subtree finishes, add saved **LEFT + RIGHT**, at the same tree
node. Keep the identical fixed32 tree, even for a short tail; do not change to
sequential accumulation. Retain every258-float partial record, max/denominator,
output, error, active/position state, tile size32, WG128/SG32 and three events.
Scores, softmax, exp, combine, selected order and BF16 KV stay unchanged. This
is not packet107's failed local-K/V sharing, p30 value code or online softmax.

The hypothesis reduces live leaf storage64 FP32 values/lane to approximately
10–12; actual compiler register/spill reduction must be demonstrated before a
device proposal. If the compiler already schedules the tree that way, close.
No speed estimate follows from a register count alone. In the future brief,
require GNU+Intel old/new exact FP32 partial[258] bytes and complete final BF16
output/status/canaries at real24Q/2KV/256D, capacity4096, selected n=0,1,31,32,
33,127,128,2047,2048,2051, legal occupied-position boundaries and noncontiguous
selected IDs. Include finite extremes, ±0, denormals, Inf/NaN payloads, invalid
IDs and inactive/error cases, two fresh processes/compiler. Same whole-model
smoke and both-lane C/X/C/X/C as the input brief. No changed tree or scratch
contents are excused as a tolerance.

## Launch contract shared by the two prepared briefs

Both briefs specify a private packet136 copy; unchanged target/draft/prefix;
GNU+Intel real-shape byte proofs; CPU device-defined parser/load/prepare probe
using the real rank argv; first-request analyzer with **no wall-clock deadline**;
complete smoke; one-load v5; both-lane proposals; freeze-safe active-time limits;
CPU stop below27 GB; **device25 GB floor plus about250 MB/view planned writes**;
no live queue edits; and **READY written last** after final pins/gates.

Only a newly prepared packet can receive READY. No GPU, service or compile is
part of packet158. The source/receipt accounting runs under nice19, CPUs8–15,
24–31, python3 -B and2 GB address-space cap with no runtime imports.
Run `analyze.py` (no arguments for fallback), then `audit.py`, both with closed
stdin. `audit.py` verifies eight groups, arithmetic, source hashes and local
links and records the final packet157 poll. It does not claim compiler/device
byte proofs, which belong to the later builds.
