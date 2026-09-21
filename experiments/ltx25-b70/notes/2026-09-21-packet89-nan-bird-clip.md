# Packet 89 endure: one NaN clip (bird 201201); the "shift" was my mapping error (2026-09-21)

## Event

Server 89 (pid 4367, boot dde38282, C6 disabled, PM pinned) ran warm 3/3 and
113 endure prompts clean. At f89-endure-115 the capture node refused:
`nonfinite generated output`, all four tensors NaN, and the VAE graph gate
latched. Campaign data: f89-warm receipts committed (d282d8124); per-prompt
receipts and evidence in the server run dir and output/validation.

## What actually happened (corrected analysis)

Prompt N's saved bundle is clip N-1's latents plus that clip's decode (the
decode node passes its JOB's latents through; the runner verifies against
`fixture[(emitted_index - index_base) % 10]` from the DECODE receipt). With
that mapping every receipt lines up:

- Clips through 201200: bitwise-exact.
- **Clip 201201 (bird, prompt 112's clip, seeds from the bird fixture): the
  SAMPLER emitted all-NaN latents.** The decode faithfully produced NaN
  images and an all-NaN waveform (96960/96960 samples; the guarded save
  recorded `save-failed:ArgumentError` from avcodec and a waveform dump at
  `output/f89-endure-114_preview_audio_debug.pt`, then continued); the
  capture node raised and latched the gate.
- Clips 201202-201205 (pendulum, rain, paper, candle): **bitwise-exact vs
  their references.** The corruption was exactly one clip.

An earlier draft of this note claimed a one-slot emission shift (post-NaN
clips "matching the previous fixture"). That was my own off-by-one: I mapped
prompt->fixture directly instead of through the decode receipt's
emitted_index. No shift exists; conditioning fingerprints, emission indices
and saved content are all consistent.

## What this means

- The wrong-clip bug is the SAME class as packets 80/81/82b/88: ONE clip
  NaN (or finite-wrong), everything around it bitwise-exact, and it is the
  **bird fixture again** - the clip that failed on every previous server.
- Bird is prompt-index 2 mod 10; its failures happened under full two-thread
  pipelined load on every occurrence. The conditioning/noise/seed inputs
  are exonerated by the surrounding exact clips and the receipt fps.
- Suspect stays the two-thread sampler machinery (pool/capture keying per
  device+thread shipped in 83; 88 still produced one finite-wrong bird).

## Replay

`replay-clip.py` fixed for the pipelined world (submits target + two
fillers, reads the second filler's validation dir, summary-level sha256 vs
the summary-only r01 references, asserts the emitted_index mapping). The
failing clip is **bird at index 112** (fixture bird, its constant seed),
NOT prompt 115's own fixture. Server 89 is latched, so the replay needs a
fresh server on this (clean) boot: launch 89b, replay bird/112, then - if
it reproduces - rerun with heavy instrumentation; if not, it needs the
two-thread steady state and the next endure continues the hunt.
