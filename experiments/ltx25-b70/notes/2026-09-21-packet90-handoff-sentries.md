# Packet 90: sampler handoff sentries (wrong-clip localizer), 2026-09-21

## Why

The wrong-clip class (f80 NaN audio, f81 all-NaN, f82b finite-wrong, f88
finite-wrong, f89 NaN) always takes exactly ONE clip, everything around it
bitwise-exact, always under full two-thread pipelined load. Packet 89's
victim: clip 201201 (bird), sampled as all-NaN latents while its neighbors
were bitwise their references.

Replays on quiesced servers (f89-replay-bird on 89b) produced bird's latents
**bitwise-exact** vs the r01 reference (video_latent sha ec1d42fa...). The
bug does not reproduce in isolation: it needs the two-thread steady state.
So the endure arm itself becomes the trap, with sentries at the three points
where the clip's bytes can change:

1. **Worker side** (`sample_clip`, after the clip's streams drain): finite
   scan + sha256 + data_ptr of both latents, recorded as
   `('sample-output', clip_index)`.
2. **Collect side** (sampler node `_apply`, after `run_behind` returns the
   emitted clip): the same scans must match the worker record. A mismatch
   here = corruption while the job sat in the handoff dict (pool alias,
   in-place overwrite).
3. **Decode submit** (decode node, before `run_behind('decode', ...)`): the
   latents ComfyUI hands to the decode stage must equal the sampler's
   worker record. A mismatch here = corruption in the inter-node handoff;
   a match moves any downstream wrongness into the decode stage itself.

Any sentry failure raises, which latches the pipeline fail-closed (existing
`_failed` path) with the clip index and both hashes in the exception and the
receipt. Costs ~4 latent scans + host copies per clip; timing shifts are
accepted for this debug packet (if the bug goes quiet under sentries, that
is itself the signal that the race is timing-sensitive).

## Build

Same builder, same packet13 parent, same file inventory as 89 (the sampler
and decode nodes are graph-capture additions, so only their digests change);
output renamed to `prepared-encoder-sentry-90`, manifest
fd76eaaa4e88ee851b24091c9d42d33ae619ef9c19c4acb15ca40bd825b88112, launcher
gate passes `--check-only`. Numerics untouched: sentries only read.

## Side finding from the replays

On two fresh servers (89b, 89c), the SECOND clip through the sample stage
(thread B's first job) died in `sample_euler_ancestral_RF`'s step-noise
draw: `capturing_ INTERNAL ASSERT FAILED ... Attempt to increase offset for
a XPU generator not in capture mode`. The campaign path (3-prompt warm arm
first) never trips it; the bare replay path did, twice. Not the campaign
failure mode (that one is silent NaN, no exception), but another
capture/RNG fragility in the two-thread machinery, recorded here for the
eventual fix.

## Campaign

run-campaign-90.sh = the 89 shape verbatim: PM check, health wait, 60 s
rest, f90-warm (3 prompts, base 202989), 60 s settle, f90-endure (120
prompts, base 203089). Outcomes:

- 120/120 exact: bug silent this run; timing or the sentry overhead shifted
  the race. Rerun or thin the sentries.
- Latch at sentry 1: the graph itself NaN'd -> instrument inside the chain.
- Latch at sentry 2: in-handoff corruption -> pool/buffer forensics.
- Latch at sentry 3: inter-node handoff -> ComfyUI output-cache forensics.
- 120/120 with a capture-node refusal (like 89): impossible by construction
  now - the capture reads the decode stage's inputs, which sentry 3 checks.
