# Gemma 4 26B A4B Q8: UBATCH=832 Full Confirm Negative

Date: 2026-06-27

## Result

`UBATCH_SIZE=832` was re-tested as a full confirmation because a prior short
screen had a row0 near `105 tok/s`.

Run:

- `data/gemma4-q8-gpu2-ub832-nmin3-pmin010-fullconfirm-20260627T115058Z/`
- GPU: single B70 (`GPU_INDEX=2`)
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- MTP: `n_max=7`, `n_min=3`, `p_min=0.10`
- quality lane: Q8 target, f16 KV
- canary: `384/384` rows passed

Fresh-response headline:

- row0 after-TTFT throughput: `102.40217510432741 tok/s`
- row0 wall throughput: `89.37488964718207 tok/s`
- support-only repeated-prompt mean after TTFT: `103.54321095189627 tok/s`
- support-only median after TTFT: `104.14578804611969 tok/s`

## Decision

Rejected. The current valid LocalMaxxing record remains
`104.30919255569083 tok/s` from
`data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`.

The earlier `UBATCH_SIZE=832` short-screen result was run-to-run noise. Do not
promote repeated-prompt mean or support rows as the fresh-response headline.

## Follow-up

Stop spending GPU time on tiny `UBATCH_SIZE` neighborhood sweeps unless paired
with a source-level mechanism. The remaining gap to the >150 tok/s target is not
launch sizing; current node profiles point at target verifier work, especially
Q8 routed MoE matmuls and LM-head/output verification.
