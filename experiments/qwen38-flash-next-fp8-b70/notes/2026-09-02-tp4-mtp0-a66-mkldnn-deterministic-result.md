# Qwen3.8 Flash-Next FP8 A66 deterministic-oneDNN control result

Date: 2026-09-02 20:45--21:20 EDT
Status: diagnostic positive; first logit-exact TP4 server; no promotion
claim yet (no quality battery, no speed rows); protected results unchanged

## Outcome

A66 (the A65/A62 server identity: eager, bundled oneCCL, tuned M1 W13-N32
map, external checkpoint, PLE-only UVA placement, 2304 max model length,
64-token chunked prefill, host guards) ran overlay head `805cde59...` with
`VLLM_XPU_MKLDNN_DETERMINISTIC=1` exported inside the derived launcher. The
server log carries four `torch.backends.mkldnn.deterministic=True` lines
(one per rank) and the identity receipt carries `mkldnn_deterministic=1`.
Load took 13 minutes (weights 21:00, healthy 21:03). The logprob probe ran
all 44 requests without a hang; the kernel log holds no GPU fault.

| depth | first-step logits identical (8x) | top-1 logprob spread | 128-token repeats (3x) | max top-1 logprob diff over 128 positions |
| --- | --- | --- | --- | --- |
| 8 | yes | 0.0 | one hash | 0.0 |
| 64 | yes | 0.0 | one hash | 0.0 |
| 256 | yes | 0.0 | one hash | 0.0 |
| 2048 | yes | 0.0 | one hash | 0.0 |

Every earlier arm on this identity (A59-A65) failed the same probe at every
depth with first-step spreads of 0.005-0.36 nats and three distinct
128-token hashes. Receipt:
`.../qwen38-flash-next-fp8-tp4-ep4-mkldnndet-mtp0-2304-ple-only-r1-attempt66/a66-logprob-determinism.json`.

## Reading

The A65 localization holds: the run-to-run jitter of the served TP4 line
came from oneDNN BF16 dense GEMMs (first seen in the K=10240
hyperconnection mix), and asking oneDNN for deterministic primitives in
every worker removes it end to end at prefill lengths from 8 to 2048 tokens
and through 128 decode steps. No other change was made: kernels, oneCCL,
placement, scheduler, map, and graph mode are those of A62/A65.

This is component-plus-endpoint evidence of exactness, not a quality or
speed result. The BF16 census measured the flag's multiplicity-weighted cost
at a 0.986 ratio (a small gain in aggregate, two sentinel shapes about 2%
slower); the served cost is measured next.

## Next

- A67 (frozen): the A59/A56 full-decode-graph identity with the public
  oneCCL preload and the same flag, same probe. Prereg:
  `2026-09-02-tp4-mtp0-a67-fullgraph-mkldnn-deterministic-prereg.md`.
- A68: the frozen A56-style client battery (recovery canary, 7 exact
  semantic cases, 16-repeat, exact 2K needle, short rows, exact-2K rows) on
  whichever of A66/A67 is exact, for a promotable deterministic number.
