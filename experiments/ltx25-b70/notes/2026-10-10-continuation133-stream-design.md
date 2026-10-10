# Packet 133: move twelve text layers before capture

CPU preparation, parent 132 manifest
`67ec59a5b0c5131d0b129e4c0b9187386c29c0395ac225dc28422516684991ad`.
Native qualification and actual freed physical memory remain unmeasured.
The chosen option is a static 36/12 text split, with the display back on
xpu:3 and no display replica. It avoids recurring weight transfers and leaves
the text graphs resident. Default `LTX_TEXT_RESIDENCY=legacy` retains 132.

The [receipt analysis](2026-10-10-continuation133-memory-evidence.md) records
source paths, hashes, measured timings and the separate physical-memory
phases. The source-derived byte counts below are not measurements of released
physical memory. All sizes are GiB (2^30 bytes).

## Inventory and use

The parent text encoder is Gemma4-12B with the existing LTX projection and
qualified suffix-window policy. Layers 0–23 occupy 10.152081 on xpu:2;
embedding, projections and other primary state add 4.125905, for 14.277986.
Layers 24–47 occupy 10.152081 on xpu:3. The video encoder and decoder on
xpu:3 occupy 0.594066 and 0.776972. Parent 132's candidate moved the audio
VAE/vocoder (0.339622) and display replica (0.776972) to xpu:2.

The graph adapter keeps 480 graphs: 48 layers, five row-count buckets
(64/128/256/512/1024), and two encode workers. Each entry owns static inputs
and its output, which aliases its static hidden-state input. Graphs contain
addresses of the weights used at capture. Transient pools and capture streams
are shared per device and worker, not independently allocated per layer.
The staged-argument caches retain the last forward's argument copies until
reset. The 2.312–2.771 residual live GiB previously counted on xpu:3 includes
graph/static/workspace allocations; it is not an identified releasable pool.

There is **no semantic text KV cache** between cuts: the graph wrapper rejects
past/shared KV, and the stack requires zero KV-sharing layers. The xpu:3 text
weights do no text computation between scene cuts. They remain resident to
preserve the captured graph storage and residency contracts.

At a cut, the unchanged tokenizer, embedding, final normalization and projection
remain eager. The selected window runs through the captured 48-layer stack.
Each secondary layer stages its input xpu:2→host→xpu:3 and its output back to
xpu:2; it is not one transfer at the shard boundary. The primary stack collects
the intermediate hidden states as before. Existing encode workers own the
graphs; the decode thread does not own a ready text graph set.

Measured text-node intervals for 51 cuts in each of two saved 129 windows have
medians 0.389263 and 0.388459 seconds. The interval is `text_start` through
`stream_text_start`, including dispatch/conditioning handoff, not an isolated
kernel timer. Six 132 fresh encodes took 0.396709–0.432802 seconds.

`reuse_text` retains exactly one deep-copied conditioning structure, bound to
the current chain and prompt hash. Each reuse checks and returns a deep copy
with the same tensor metadata/hashes. It runs no text layers. Kittens-01 has
ten scenes of four chunks: at 145 frames each anchored chunk supplies six
seconds of new video, so one cut is approximately every 24 seconds of video.

## What the failed 132 attempt establishes

The failure was `conditioning-B-before` at qrepeat-c000001, rather than the
request-entry check. Its physical-free reading was 9,103,118,336 bytes,
0.522060 GiB below the 9 GiB floor; including the screening band the deficit
is 1.272060. No floor is reduced here.

The first cone capture passed by 335,659,008 bytes (0.312607 GiB). Recorded
decoder reservation growth was **3,806,330,880 bytes = 3.544921875 GiB**.
This supersedes the earlier 4.506 GiB temporal-squared estimate as an observed
growth value, but it is still not an isolated peak or a proven upper bound.
The 5 GiB capture allowance stays unchanged. Later cone readings around
12.080 GiB did not prevent the lower stage-B reading.

## Ranked options

| Rank and option | Residency change | Additional cost per cut | 145 / 169 assessment |
|---|---|---|---|
| **1. Static split36; display on3** | Move layers24–35: **5.076040 weights** from3 to2. Approximately **1.078491 owned graph-input storage** moves with them. Remove the0.776972 display replica on2 relative to132. Audio remains legacy on3. | **0 seconds of recurring weight reload**. Removes12 activation round trips per encode; actual timing delta is unmeasured. |145 is a guarded preparation candidate with the full5GiB allowance and original floors/band.169 remains unadmitted without matched peak/qualification evidence. |
| 2. (a) Host-resident secondary shard, reload before cuts | Potential10.152081 freed on3 between cuts; zero if old device storage remains for graph replay. Adds at least10.152081 pinned host storage. | No measured PCIe bandwidth exists in the audited receipts. At an **assumed**5–10GB/s, upload alone takes **1.090–2.180s**, or0.273–0.545s/chunk across four chunks. Graph reconstruction is extra and unmeasured. |Arithmetic with the shard genuinely absent gives18.630020GiB free at132's failing point, but ordinary reload invalidates captured pointers. Reload restores pressure while the cone pool remains resident. Neither145 nor169 is admissible as a simple toggle. |
| 3. (b) All text on2, display back on3 | Move10.152081 weights3→2; full text static24.430067. Remove0.776972 replica2. Both cards' graph-pool layout changes. | No recurring weight copy; fewer activation transfers. Actual cut time unmeasured. |Applying weights alone to129's no-replica minimum leaves1.553726GiB free on2, below its2GiB floor, before moving graph inputs. Consolidating pools might improve this, but no receipt establishes enough. Neither geometry is admitted. Keeping display2 is worse. |
| 4. (c) Scheduled next-scene text prefetch | **0 GiB freed** on either card by scheduling alone; may add one conditioning buffer. |Could move roughly0.389s of existing work off a cut's critical path; overlap/queue benefit unmeasured. It does not remove the work. |Does not fix145 memory and does not establish169. Exact scheduling is possible in principle with a server-bound immutable schedule and matching consumer checks; not implemented. |
| 5. (d) Drop text graph pools between cuts | **0 GiB guaranteed**. Dropping smaller-window entries retains1024 graphs and their shared pools. Dropping all graphs also releases owned statics but loses qualified entries. |Full recapture/requalification cost unmeasured.132's entire startup window stage took337.149s; that is not a per-cut recapture measurement. |Current timed encodes forbid captures. Removing all graphs violates the sealed residency/window contract. Neither145 nor169 is admitted under this design. |

The host-copy estimate is a scenario, not a measured link speed. Uploading into
the original GPU allocation preserves pointers but frees no weight storage.
Replacing the allocation cannot make an old XPUGraph reference the new weights.
A future graph-aware staging or destroy/requalify design needs a new lifetime
contract, graph proofs, source-bound state transitions and peak-memory budget.

An immutable scenes file can remove packet119's unknown-prompt objection, but
the current protocol allows resets, interruption, resume and prompt changes.
A future scheduled prefetch must bind file hash, schedule position, chain,
prompt/token/window identities and the actual successor; invalidate mismatches;
use an already-qualified encode worker; and pass the same output hashes.
Running text directly on the decode thread would require another graph set or
a different ownership contract. Prefetch is not a residency remedy by itself.

A small split27 move with display still on2 is possible only by crediting moved
graph inputs: approximately0.095GiB screening margin on2 and0.250GiB on3.
Weights alone fail one screen for each split26–28. Those margins are too narrow
to prefer over split36 with native display. The all-text2 option is not declared
physically impossible: its missing single-card pool/peak measurements are the
reason it is not admitted.

## Selected memory budget and exactness contract

For the matching saved129 native-display/legacy setup, minimum sampled physical
free was9.270363 /9.828613 /11.705807 /10.806747GiB on cards0/1/2/3.
For split36, charging the **full5GiB** cone allowance at every saved phase gives:

| Projection | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| Physical free, weights only |9.270363|9.828613|6.629766|10.882788|
| Margin above unchanged8/8/2/9 floors |1.270363|1.828613|4.629766|1.882788|
| Margin after an additional0.75 screen |0.520363|1.078613|3.879766|1.132788|
| Including estimated moved graph inputs: margin after screen |0.520363|1.078613|**2.801275**|**2.211279**|

The0/1 screening columns are comparative planning margins, not new runtime
floor requirements. Floors, observations and the cone's actual0.75 band stay
where the parent checks them. Shared transient pools must not be charged once
per moved layer. Neither graph-input sizes nor sampled minima establish an
instantaneous physical peak. Actual pre/post-probe and cut checks remain.

First cone capture still requires14.75GiB physically free. Subsequent cone
admission requires9.75GiB, and conditioning/request floors remain unchanged.
No lowered reserve, compressed state, lazy fallback, extra retry, midstream
recapture or changed arithmetic is admitted. The candidate is restricted to
145/frame/dg1/cone/bo1/pa1/fingerprint/full, serial eager native display3,
legacy audio/auxiliaries and the explicit `text-shift` cone-memory mode.

The existing shard constructor supports an interior split and proves the
partition preserves every tensor identity, dtype and shape. Placement changes
before loading/capture, so each graph captures its actual resident weights.
Layer/window math, precision, prompt contents, seeds and sampler stay fixed.
Same B70 class and earlier display/audio cross-card equality are supporting
evidence, **not a proof that this text placement is exact**.

The new [conditioning oracle](../data/resume-20261008/continuation133-text-oracle.json)
binds12 prompt hashes and261 consistent saved fresh encodes, covering the two
qualification prompts and all ten kitten scenes. Every candidate fresh encode
must match its parent tensor metadata and bytes before sampling; unknown
prompts refuse. All40 text-window probe rows must match parent full/window
hash arrays and prompt/window identities. The window's existing owner-approved
rounding policy is preserved; this is exactness against that accepted parent,
not a new claim of equality to the1024-row path.

The frozen145 full-output table is mandatory for split36. All nine existing
qualification outputs, three chains, native/optimized conditioning checks,
cone/display frame bytes, fault handling and postchecks remain. The plan,
source closure, status, receipts, decode records, verdict and client bind the
text-residency mode. CPU fakes prove these refusals and protocol rules; they
cannot establish native memory fit or native cross-card arithmetic equality.

## Predicted timing and limits

Use **5.25–5.35 seconds per six seconds of new video (0.875–0.892s/s)** as the
inherited conditional cone forecast, plus the unmeasured text-placement and
native-card3 eager-display scheduling/contention deltas. The129 baseline used
sampler-a display scheduling, while132's forecast assumed replica2 display;
neither is a matched measurement of this selected setup. No host reload penalty
applies. Do not claim a faster measured cut or
period from fewer activation transfers. For each future authorized comparison,
report cuts and reuse chunks separately, all-scene average/p90 and sustained
period over complete four-chunk scenes, along with every card's minima.

169 remains refused in the new option. Its prior display2 refusal is not a
measurement of this native-display/split36 layout, and145 cone growth cannot
prove169 peak safety or sustained cadence. Nothing in this packet changes
the owner's9GiB floor or admits an extrapolated performance result.

Preparation performs no GPU, model/server launch, check-only, systemd/unit,
live-port, device-node, signal or host-setting operation, and writes nothing
under existing run directories or `/home/steve/ltx-stream`. CPU work uses
nice19, OMP/MKL2 and pinned bin/python-B. The coordinator retains live control.
Final seal, exact test counts and cleanup are recorded in the build receipt.

## Preparation review record

The first complete recovery run exercised1046 tests and exposed five failures
and four errors in inherited parent/status/helper fixtures. Its complete client
run passed6012 checks across41 suites. Separate review found two actual wiring
defects: the status route omitted the new feature declaration, and the runtime's
run-name check still used the old cone-mode suffix. Both were corrected and
covered by six new tests that execute the actual status handler or check the
launcher/runtime identity without launching anything. The sealed transition
metadata now lists text-shift, and the contract correctly states that this mode
performs no allocator release.

The original logs, failing focused regressions and exact corrective patch remain
under `data/resume-20261008/continuation133-tests/`. The initial prepared packet
was moved to the new `prepared-continuation-stream-133-development-status`
archive before the final packet was rebuilt. No pre-existing run was changed.
Only the final full suites and final source-bound runtime evidence count toward
the build receipt; the development seal is not a launch recommendation.

## Final CPU evidence

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-133`.
Manifest: `a1f0fb23dbba64ea2530b58fb4787f736a602746a1be72a040688bf0eaf74bd6`.
Inner plan: `b230f1dbd3f799b7f5227ef8ea7a72057a901aa0054be67f3babe664aa8700d9`.
The final full recovery suite passed 1052/1052 in 1109.781 seconds. All 6012/6012
checks across 41 client suites passed against the final seal. Owned scratch is
removed. Three final CPU runtime cases each exercised nine qualification and
two stream chunks;
all 22 cross-case output-hash comparisons and 10 mocked preflight checks passed.
Recursive verification covers 2299 bound files, with zero Python caches and
matching authored components. All 30 inner-plan pin assertions pass across 15
packets. The [build receipt](../data/resume-20261008/continuation133-build.json)
records final client counts, source/log hashes, repository checks and cleanup.
The [prepared launch](../recovery/20261010-continuation133-stream/LAUNCH.md)
is text for the coordinator; it was not executed here.

Repository and packet documentation links and manifest paths pass. The literal
pin checker still reports 231 existing drifts to two Flash-Next tools (87 pins
match; no target is missing), identical to the development baseline. Those
unrelated historical pins were not rewritten; packet 133's own pins all pass.
