# MiniMax-H3 gate sessions, 2026-10-03 (kernel 7.0.0-31, zero GPU fault lines on the boot)

Runner: `scripts/gate-session-20261003.sh`. Raw runs: `/mnt/fast-ai/bench-results/minimax-h3/duet-20261003T*`.

| Session | What ran | Result |
|---|---|---|
| `run1/` | gate A, base model 50 NFE | clip-00 4/4 MATCH vs `repeat-20260920T023257Z-a`; then the decode server died on clip 1 (shared-file cleanup race) |
| `run2/` | gate A turbo, gate B twice | A passed. B "passed" for the wrong reason: the workers ignored fp16, so the picture hash equalled fp32's |
| `run3/` | same, on the corrected code | A passed (4/4 MATCH vs `duet-20260920T074116Z/clip-00`). B failed: fp16 two-proc decode is 9.0 s/clip but the two runs' picture hashes differ |
| `fp16-single-repeat/` | decode-only, single card, fp16, twice | the two receipts are bytewise-equal; 15.3 s |

`receipts/` holds the per-clip receipts of the four runs that matter. The three `mp4-*.json` files are
`scripts/compare-h3-mp4.py` outputs; note that two clips with bit-identical picture tensors still give
different mp4 files (the x264 encode is not repeatable), so those numbers have a noise floor of their own.
