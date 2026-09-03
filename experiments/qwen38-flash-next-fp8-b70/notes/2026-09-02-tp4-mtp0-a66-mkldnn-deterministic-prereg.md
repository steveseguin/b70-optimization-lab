# Qwen3.8 Flash-Next FP8 A66 deterministic-oneDNN control preregistration

Date: 2026-09-02
Status: diagnostic; frozen before launch; no promotion claim possible

## Question

A65 localized the first non-repeatable operation of an 8-token prefill to a
K=10240 BF16 oneDNN GEMM in the layer-0 hyperconnection mix on rank 0, with
every rank's later difference explained by that partial entering the TP
all-reduce. The BF16 deterministic census (A3/A4a) showed
`torch.backends.mkldnn.deterministic=True` makes the K=10240 down-projections
and all 13 other dense families exact within and across fresh processes at a
0.986 multiplicity-weighted cost ratio. Does setting that flag in every XPU
worker make the served TP4 line logit-exact at depths 8, 64, 256 and 2048?

## Design

Overlay commit (recorded in the packet as `expected_vllm_head`) adds
`VLLM_XPU_MKLDNN_DETERMINISTIC` (default off) to `vllm/envs.py` and, when
set, assigns `torch.backends.mkldnn.deterministic = True` in
`XPUWorker.init_device` right after the device is selected, logging the
resulting value per rank so the server log is the receipt.

`tools/rewrite-q38-a65-to-a66-mkldnn-det.py` derives A66 from frozen A65 by
moving the head override to that commit and replacing the six trace exports
with the A62 `unset` lines plus `export VLLM_XPU_MKLDNN_DETERMINISTIC=1`.
Everything else is A65/A62: eager, bundled oneCCL, tuned M1 W13-N32 map,
external checkpoint, PLE-only UVA placement, 2304 max model length, 64-token
chunked prefill, host guards. Attempt 66 / port 19738; names carry
`mkldnndet`. Probe: `probe-q38-a59-logprob-determinism.py --depths
8,64,256,2048` (eight `max_tokens=1` repeats and three 128-token repeats per
depth).

## Reading

- Identical first-step logits (8/8) and identical 128-token repeats (3/3)
  at every depth: the oneDNN GEMM path is the source and the flag is the
  repair; A67 then re-runs the A56-style quality, repeat and needle battery
  plus throughput rows on this identity, and the decode-graph identity with
  the flag follows.
- Exact at short depths but not at 2048: a second source enters with long
  prefill (QSA or GDN chunk state); the trace is re-armed at the failing
  depth.
- Same jitter everywhere: the flag does not reach the primitive used by the
  serving GEMMs (log line checked) or a second source exists; the trace is
  re-armed with the flag on.

The server log must contain four `torch.backends.mkldnn.deterministic=True`
lines, one per rank. No speed is claimed. Protected results remain unchanged.
