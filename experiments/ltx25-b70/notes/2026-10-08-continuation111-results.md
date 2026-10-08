# Continuation 111 results: first exact three-chunk scene continuation

Run `encoder-server-continuation-native-111-two-way20-28-w2-b1-p1-dxpu2-s640x384-f49`,
packet manifest `65adf13f…`, plan `7944f870…`, server identity `294fee41…`.
Campaign started 2026-10-08 00:28:07 UTC; eighth request verified 00:40 UTC.
Final record: `continuation-final.json` in the run directory
(`exact_replay_pairs: 3`, `unique_video_frames_per_chain: 145`, `verified: true`,
all claims false: not adopted, no speed improvement, seams not reviewed,
audio alignment unresolved).

## What passed

- All eight requests completed and were independently verified; no fault, no
  halt, no kernel entry in the window.
- Two complete chains (pass0, pass1) of three 49-frame chunks at 640×384.
  Chunk 0 is ordinary text-to-video; chunks 1 and 2 are conditioned on the
  preceding chunk's last decoded F32 frame through the native image-conditioning
  node before both samplers.
- Every chunk's four tensors (video latent, audio latent, images, waveform)
  matched between the two passes: three exact replay pairs. Anchors bound by
  hash (2,949,120 bytes each), predecessors linked, all finite.
- 145 unique video frames per chain (49 + 48 + 48).

## Timing (reference only, native eager path)

Request wall time from submit to success, per the proof receipts:

| Request | Wall |
| --- | ---: |
| pass0 chunk0 / chunk1 / chunk2 | 20.8 s / 14.5 s / 16.6 s |
| pass1 chunk0 / chunk1 / chunk2 | 9.2 s / 21.3 s / 24.4 s |
| prepare-native (setup) | 40.7 s |
| window probe (first request, includes warm-up) | 326.4 s |

Complete-to-complete gaps inside a chain were 24–79 s because each request
also wrote a full 146 MB capture and its proof. A two-second chunk therefore
took 15–24 s of generation: about 2–3 generated frames per second. This is the
deliberately unoptimized native reference. It is far below the 17 fps of the
independent-clip 49-frame lane and nowhere near real time. The point was
exactness and determinism, which it established.

## Not established

Seam/motion quality at the two boundaries (needs a human look at lossless
samples), audio timeline alignment (raw audio left unchanged), any speed claim.

## Next lever (preregistered in the after-111 note)

Per-block graph replay on the same serial continuation chain
(`notes/2026-10-07-after111-graph-candidate.md`), then the same at 256×256 where
the independent-clip lane already runs above real time.

## Stop

The 111 application was stopped once with SIGINT at 00:54 UTC after its finite
authority was consumed; all four cards passed postflight at 00:54:58 UTC with
zero fault lines this boot. Receipt: `data/resume-20261007/continuation111-stop.json`.
