# MiniMax-H3: chosen two-B70 video result

The owner approved this target and result on October 10, 2026 and requested
featured placement. [Decision](../../repro/minimax-h3-pruned-bf16-tp2-b70-20261004/owner-decision.json)
· [guide and evidence](../../repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md).

The served denoiser is the AdaLN-fitted variant (all other weights bit-exact
with the official checkpoint; the AdaLN tables are a fitted approximation
measured below the BF16 noise floor). The 2x result is an exact scheduling
speedup against that denoiser's own reference (32 MATCH / 0 DIFFERS, 8 repeat
passes). The encoder is INT8 ConvRot. No official-model parity is claimed.

| Result | Scope and evidence |
| --- | --- |
| **396.625 s/clip (396.6 rounded)** | 3173 s / 8 clips; one batch, 124 frames, 960×544, 24 fps playback, 32 kHz stereo; [session](../../experiments/minimax-h3-b70/data/2026-10-04-soak8/session.log) and [eight receipts](../../experiments/minimax-h3-b70/data/2026-10-04-soak8/) |
| 800.8 s/clip | **ledger-recorded baseline, raw receipts not retained**; [baseline ledger](../../experiments/minimax-h3-b70/notes/2026-09-20-realtime-goal.md) |
| 2.019× historical ratio | 800.8 / 396.625; not a newly matched measurement or an isolated persistent-decoder gain |
| 32 MATCH / 0 DIFFERS, 8 repeat passes | Session report against September's reference, whose receipts are absent; eight clip comparisons, not eight fresh complete batches |

Settings: split25, base schedule 50 NFE, seed 42 per prompt, no LoRA, FP32
video decode, persistent two-process decode and overlapped audio. The exact
prompt set, hashes and historical source anchor are in the guide. Official
checkpoint revision and full file hashes are reconstruction metadata, not
retrospectively verified historical pins. Prefill, full process-tree VRAM,
first-clip latency, fresh-run dispersion and scaling are not measured here.

The owner acceptance is complete. Public recipe closure remains incomplete:
the retained AdaLN script checks the fit but does not recreate its coefficients,
and the clean-build/runtime and independent full-suite repeat evidence are
missing. The site lists the chosen measured result; the publication manifest
stays draft and strict featured metric null. No weights are redistributed.
