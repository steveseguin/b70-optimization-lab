# Packet 138: scheduled text prefetch and pacing measurements

Parent is sealed packet 137, manifest
`18c80d25c2ba4992d8c6dff24779737a056a325389a84486d24da674ef7e463e`.
This is CPU preparation. Native output, overlap, memory peaks and speed remain
unqualified. No model request, launch, check-only, port inspection, unit
operation or device access is part of this work.

## Scheduling and exactness

The client publishes the position in the fixed forty-chunk kitten schedule
and its file hash. This removes the unknown-prompt objection in
[119](../experiments/ltx25-b70/notes/2026-10-10-continuation119-stream-design.md)
without granting predictions authority over actual requests. The current
prompt must agree with the pinned slot. At the end of a four-chunk scene,
the only candidate is the next pinned scene, including the wrap from scene ten
to scene one. Missing hints take the fresh path. Different prompts, positions,
chains or resets invalidate the speculative result. Seeds and reset semantics
remain unchanged; a text prediction never changes an anchor or sampler input.

The decoder tail for source n−1 observes active source n at schedule slot three,
after n's sampler-A event and after the decoder's display, audio, hashing and
preview handoff. It prepares n+1's slot-zero text. This offset matters: waiting
for source n's own decoder tail would be too late for n+1's fresh text. Preview
writing remains asynchronous on its existing worker. The graph/repeat
qualification chains separately prepare their fixed chunk-two cut from
chunk zero; both must record a verified hit before admission.

The decoder orchestrates the work, while an existing qualified `ltx-encode`
worker performs the actual encoding. Calling text directly on the decoder is
invalid: `ltx_text_window.encode` requires graphs keyed to the executing thread,
and `pipeline_node.native_encode` supplies the encode worker's stream ordering.
A third graph set is not introduced. The unchanged native wrapper resets its
forward caches, runs the same suffix window and projection, synchronizes its
streams, consumes its embedding observations and restores its thread state.
Graph-state comparisons retain each shadow, entry and graph object, static
tensor storage pointer and metadata, and per-thread signature. Source files,
helper functions, constants and the installed consumer are bound as well.
Both the produced conditioning and the consumer's conditioning must match the
parent oracle, including tensor metadata and every byte hash. The oracle covers
the two qualification prompts and all ten scene prompts; unknown prompts still
refuse under split36.

The parent checks real pipeline quiescence and uncollected jobs at request
boundaries. A prefetch must be collected before that check; reporting workers
as idle while they run would be invalid. Likewise, the original pipeline's
mismatched-tag inline fallback is unsuitable for a window encode on the prompt
thread. A speculative miss must discard its slot and use the original fresh
worker path. Registered native node methods remain source-bound; no live
monkeypatch of their ownership is allowed. The pipeline worker now decrements
its truthful running count before publishing its completion event (the parent
published those in the opposite order). This closes the completion race for
all stages; it changes no computation and never hides a running worker.

## Conditioning buffer and memory

The [read-only census](../experiments/ltx25-b70/data/resume-20261008/continuation138-prefetch-memory.json)
binds 41 input files, including all 12 oracle prompt entries, 31 saved GC10
receipts, the frozen133b memory analysis and sealed137 source. The largest
conditioning payload is **1,376,256 bytes, or 1.3125 MiB**, a float32 tensor of
shape `[1,56,6144]`. Only one extra predicted conditioning is retained; the ten
scene candidates are not a conditioning cache. Existing reuse/cache handoff
deep copies can briefly coexist with that value. Two or three complete values
contain 2.625 or 3.9375 MiB of logical tensor data; these totals are not allocator
peak measurements and are not all necessarily incremental to the parent.

That retained buffer is on **CPU**, derived from the sealed code: the native
encoder returns through `intermediate_device()`, the launcher does not select
`--gpu-only`, and the LTX projection returns float32 conditioning to that
original output device. The oracle records metadata and bytes but omits device,
so this placement is source evidence, not a receipt device observation. Text
computation still uses xpu:2 for layers 0–35, embedding and projection, and
xpu:3 for layers 36–47. Sampling remains on xpu:0/xpu:1 under the
admitted two-way20-28 placement. The prefetch's card 2/3 memory synchronizations
therefore do not directly wait for sampler work on cards 0/1. The native encode
wrapper retains its own per-thread stream synchronizations on every card.
Host overhead and inherited snapshot synchronization may reduce overlap.
A retained CPU buffer saves no card memory.

Saved GC10 chunks 0–30 have independent minimum margins above the unchanged
8/8/2/9 GiB floors plus the 0.75 GiB planning screen of **0.520542, 1.078800,
2.157818 and 4.846485 GiB** on cards 0–3. The corresponding frozen 133b margins
are 0.520538, 1.078781, 2.157822 and 4.846481 GiB. These are sampled observations
from the parent, neither simultaneous minima nor candidate overlap bounds.
The new overlapping encode's temporary allocations remain unmeasured. All
fresh memory checks and existing cone allowances remain required.

Reusing a qualified encode worker needs no additional graph set. Its captured
static inputs and output are per thread, and the output aliases the static
hidden-state input. Copying all graph state or adding decoder-owned graphs
would exceed the one-conditioning-buffer design and has no budget here.

## Expected benefit

The saved fresh-text interval is **0.378417 seconds per scene cut**. If fully
hidden behind the preceding chunk, the upper timing budget is about **0.378 s
per cut, or 0.0946 s per chunk averaged over four chunks**. This is a prediction,
not a measured gain or a promise about the pooled median. Startup, a miss, a
reset, worker contention or a late decode can leave some or all of the cost on
the chain. The work is moved, not removed. Report cuts, reused chunks, all-scene
means and tails separately, using matched unthrottled windows.

## Pacing measurements

The [pacing analysis](../results/ltx25-continuation-stream-pacing-2026-10-10.md)
and [v2 data](../data/ltx25-continuation-stream-2026-10-10-pacing-v2.json) preserve
raw periods and explicitly separate the continuous prefix before the first
client hold in each invocation. Destination sequences below ten are excluded;
all cuts, maintenance and slow intervals within the selected prefix remain.
Restart gaps are never bridged. Later hold-free intervals are diagnostics,
not a reconstruction of sustained unthrottled production. Rounded legacy hold
durations are never subtracted to fabricate server timings.

For 135 GC-10, all 747 periods have a 5.553 s median. The first uninterrupted
52 periods have a 5.2415 s median, 5.3642 s mean and 5.764 s p90. Removing only
the 47 directly held intervals leaves 700 periods at 5.5255 s median; pacing
alone does not explain the later drift. The matching GC-60 prefix also has
52 periods and a 5.2415 s median. These windows do not establish a GC speed win.

The client option `--pacing-log precise` records every hold's monotonic start,
end and integer nanosecond duration, including an orderly interruption. The
138 wrapper selects it by default; `LTX_CLIENT_PACING_LOG=legacy` retains the
137 log form. These are client observations. No server receipt field claims to
subtract time that the server cannot observe.

## Preparation evidence

The packet contract, launch instructions, final seal and exact CPU counts are
recorded alongside the build receipt after validation. GPU qualification stays
with the coordinator. All preparation uses nice 19, OMP/MKL two threads,
`/home/steve/.venvs/ltx25-baseline/bin/python -B`, and owned scratch only.

Preparation history is preserved in the validation directory. An initial
assembly refused before creating a packet because source-binding review was
still changing authored inputs. Assembly resumed after the explicit source
freeze. The first full recovery run exposed an inherited launch-suffix test
that selected the new scheduled production environment while expecting the
prefetch-off suffix. The fixture now explicitly selects `LTX_TEXT_PREFETCH=off`;
no sealed runtime bytes changed. Its failed log, focused correction and complete
rerun are retained separately.


## Final seal and CPU validation

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-138`.
Manifest: `85781225aad084faf676268cbe693df5649aa77cad76373306243a688fb23fc5`.
Inner plan: `38ba6ca1e54d34acd0e27a438c6978436cbd5ecbb268946587c9e13f7f3cab2a`.

| Check | Result |
| --- | --- |
| Complete corrected recovery suite | 1,138 / 1,138 |
| Scheduled producer/consumer method tests, included in recovery | 26 / 26 |
| Full historical and new client suites | 8,897 / 8,897 across 51 suites |
| All-pins test | 40 assertions across 20 packets; inner plans pinned |
| Separate sealed-import suite | 9 / 9; all 71 helper copies (38 component, 33 runtime), plus three preseal modes |
| Pacing measurements | 14 / 14 |
| Inherited client preflight | 10 / 10 |
| Full inherited runtime, prefetch off | Three cases, each nine qualification and two stream chunks; 22 reference comparisons and 11 parent/bulk comparisons |
| Recursive verification | 2,378 bound files; 2,380 physical files; no bytecode caches |

The 26 scheduled tests execute the actual Runtime producer and consumer
methods with CPU fakes. The three complete runtime cases separately cover
prefetch-off regression; they do not prove native scheduled output or speed.
All owned scratch was removed after children exited. The first failed recovery
run and the corrected full rerun are both retained. Repository link and manifest
path checks pass. The global literal-pin check retains its pre-existing
Flash-Next result: 318 pins, 87 matching, 231 drifted, none absent. Packet-specific
pins and recursive closure pass; no unrelated pins were changed.

[Build receipt](../experiments/ltx25-b70/data/resume-20261008/continuation138-build.json),
[contract](../experiments/ltx25-b70/recovery/20261010-continuation138-stream/CONTRACT.md),
[launch commands](../experiments/ltx25-b70/recovery/20261010-continuation138-stream/LAUNCH.md),
and [validation logs](../experiments/ltx25-b70/data/resume-20261008/continuation138-tests/).
