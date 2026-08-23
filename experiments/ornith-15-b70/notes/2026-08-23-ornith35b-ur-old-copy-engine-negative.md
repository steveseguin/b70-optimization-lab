# Ornith 1.5 35B-A3B: legacy copy-engine flag regresses the accepted V2 recipe

Date: 2026-08-23 EDT

Status: **CLOSED ENGINE NEGATIVE — do not add the flag**

The accepted Ornith recipe already sets the Unified Runtime V2-specific
`UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1`. Older Qwen and Gemma experiments also
used `UR_L0_USE_COPY_ENGINE=0`, so this screen tested whether the legacy/common
adapter control disables any additional harmful copy-engine path.

Both arms kept the accepted V2 setting. Adding the legacy flag preserved the
canonical 128-token transcript byte-for-byte (SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`)
and retained all 1,270 Q/K fusion hits.

The mirrored seven-repetition `llama-bench tg128` order was A/B/B/A:

| Arm | Run means, tok/s | Arm mean |
| --- | --- | ---: |
| accepted control | 132.410556, 134.656296 | **133.533426** |
| plus `UR_L0_USE_COPY_ENGINE=0` | 131.773324, 133.844406 | **132.808865** |

The candidate regressed **0.543%**. No fresh-server test was justified. Keep
the explicit V2 copy-offload setting and leave `UR_L0_USE_COPY_ENGINE` unset.
This also avoids carrying a redundant legacy-looking switch in the beginner
recipe. Structured results, raw engine JSON, and exact transcripts are
adjacent under `../data/`.
