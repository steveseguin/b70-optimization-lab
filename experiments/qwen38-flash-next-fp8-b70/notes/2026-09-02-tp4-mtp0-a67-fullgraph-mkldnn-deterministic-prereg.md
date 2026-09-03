# Qwen3.8 Flash-Next FP8 A67 full-decode-graph deterministic-oneDNN preregistration

Date: 2026-09-02
Status: diagnostic; frozen before launch; no promotion claim possible

## Question

A66 (eager, bundled oneCCL, tuned M1 W13-N32 map) returned byte-identical
first-step logits (8/8, spread 0.0) and identical 128-token repeats (3/3,
zero logprob difference at all 128 positions) at depths 8, 64 and 256 once
every XPU worker set `torch.backends.mkldnn.deterministic=True`; the
2048-token depth was still running when this was frozen and its result is
recorded in the A66 result note. The promotable identity is the A56/A59
full-decode-graph line with the public oneCCL preload and twoshots. Does that
line become logit-exact with the same flag, or do graph replay or the public
collective add a second source that the eager jitter masked?

## Design

`tools/rewrite-q38-a59-to-a67-graph-mkldnn-det.py` derives A67 from frozen
A59 (the A56 server with the logprob-probe lineage): the head override moves
from `cbc3cb58...` to `805cde59...`, and the derived script gains
`export VLLM_XPU_MKLDNN_DETERMINISTIC=1` next to the tuned-folder export, an
`mkldnn_deterministic=1` identity receipt, and static assertions for both.
Everything else is A59/A56: `VLLM_XPU_ENABLE_XPU_GRAPH=1` full decode graph,
public oneCCL `4ceafd1` with `CCL_SYCL_ALLREDUCE_LL=twoshots`, tuned M1
W13-N32 map, external checkpoint, PLE-only UVA placement, 2304 max model
length, host guards. Attempt 67 / port 19739; names carry `fullgraphdet`.
Packet: launcher `1c41a023...`, client `0480fae0...` (hash pin only),
supervisor `eadbcc5e...`, host wrapper `e87a4c3a...`. Probe:
`probe-q38-a59-logprob-determinism.py --depths 8,64,256,2048`.

## Reading

- Exact at every depth (server log shows four
  `mkldnn.deterministic=True` lines): the graph line is logit-exact; A68
  runs the frozen A56-style client battery (recovery canary, 7 exact
  semantic cases, 16-repeat, exact 2K needle, short rows, exact-2K rows) on
  this identity for a promotable, deterministic number.
- Exact in eager (A66) but not here: graph replay or the public oneCCL path
  is a second source; A68 removes the public preload first (bundled oneCCL
  with the graph), then the graph.

No speed is claimed. Protected results remain unchanged.
