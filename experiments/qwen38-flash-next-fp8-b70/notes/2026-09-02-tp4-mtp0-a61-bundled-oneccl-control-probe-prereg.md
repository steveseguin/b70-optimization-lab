# Qwen3.8 Flash-Next FP8 A61 bundled-oneCCL control probe preregistration

Date: 2026-09-02
Status: diagnostic; frozen before launch; no promotion claim possible

## Question

A60 (eager, otherwise identical to the graph server) reproduced the
first-step jitter: eight identical 256-token `max_tokens=1` requests gave
the same top token with logprobs spread over 0.2175 nats, and the top-2
logit gaps stepped in multiples of 0.125 (BF16 ulps at logit magnitude). The
graph is therefore not the source. The deterministic 2026-08-28 eager line
ran on the venv's bundled oneCCL; every arm since A47 preloads the public
`oneccl-4ceafd1-b70-public` build with `twoshots`. Does removing that
preload restore determinism?

## Design

`tools/rewrite-q38-a60-to-a61-bundled-ccl.py` derives A61 from frozen A60
by deleting only the public-oneCCL selection from the launcher: the
`LD_PRELOAD`, `CCL_KERNEL_PATH`, `CCL_SYCL_ALLREDUCE_LL_THRESHOLD`, and
`CCL_SYCL_ALLREDUCE_LL=twoshots` exports, their identity receipts, and the
two library/kernel hash checks. The base's own oneCCL environment
(`CCL_ATL_TRANSPORT=ofi`, direct send/recv, `CCL_TOPO_P2P_ACCESS=1`, simple
thresholds) and everything else in A60 remain: eager, tuned M1 W13-N32 map,
external checkpoint, PLE-only UVA placement, 2304 max model length,
64-token chunked prefill, Torch trace, host guards. Attempt 61 / port
19733; names carry `bundledccl`. Packet: launcher `a1e5c07b...`, client
`4f442ec8...` (hash pin only), supervisor `09d424c4...`, host wrapper
`fda928d5...`. GuC 70.72.1.

Client: `tools/probe-q38-a59-logprob-determinism.py` with
`--depths 8,64,256,2048` (8 and 64 tokens fit inside one 64-token prefill
chunk; 256 and 2048 span several), eight first-step repeats and three
128-token repeats per depth; summary at `<run_dir>/a61-logprob-determinism.json`.

## Reading

- First-step top-5 identical at every depth and no 128-token divergence:
  the public oneCCL preload is the source; the promotable line returns to
  the bundled library, and the twoshots decode gain is re-evaluated against
  determinism separately.
- Jitter at 256/2048 but not at 8/64: the instability is in cross-chunk
  prefill state (QSA/GDN handoff between chunks) or in reductions of
  multi-chunk prompts.
- Jitter already at 8 tokens: a single-chunk forward pass is unstable on
  the bundled library too; the kernels (QSA, MoE, PLE UVA) are next.

No speed is claimed. Protected results remain unchanged.
