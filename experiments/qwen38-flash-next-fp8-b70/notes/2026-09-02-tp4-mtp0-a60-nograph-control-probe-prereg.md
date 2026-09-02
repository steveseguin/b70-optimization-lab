# Qwen3.8 Flash-Next FP8 A60 no-graph control probe preregistration

Date: 2026-09-02
Status: diagnostic; frozen before launch; no promotion claim possible

## Question

A59 showed the first decode step's logprobs differing by about 0.03 nats
between identical 256-token requests on the full-graph server. Does the
same server without the full decode graph reproduce that jitter?

## Design

`tools/rewrite-q38-a59-to-a60-eager-control.py` derives A60 from frozen A59
by deleting only the launcher rules that turn the eager base into the graph
server: the graph environment exports, the `compilation_config` injection,
its config assertions, and the `--enforce-eager` replacement. The derived
launcher therefore keeps the base's `--enforce-eager`, `XPU_GRAPH=0`, and
graph-disabled exports; identity receipts read `eager=1 graph=none` and
`diagnostics=nograph-public-oneccl-torch-trace`; campaign, run, cache,
compile, and evidence names use `nograph`. Everything else is A59: tuned M1
W13-N32 map (folder export and receipts), public oneCCL with `twoshots`,
external checkpoint, PLE-only UVA placement, 2304 max model length, 64-token
chunked prefill, Torch trace, host guards. Attempt 60 / port 19732. Packet:
launcher `4b3e95b7...`, client `5970b93d...` (hash pin only), supervisor
`c6eae5e4...`, host wrapper `7434e6f7...`. GuC 70.72.1.

Client: `tools/probe-q38-a59-logprob-determinism.py` unchanged, with the
A60 port, PID file, and stop file; summary at
`<run_dir>/a60-logprob-determinism.json`.

## Reading

- First-step top-5 identical across eight repeats at both depths and no
  jitter in the 128-token runs: the graph path is the source; the eager
  line with the map is a determinism-clean baseline and its speed becomes
  the promotable target while the graph is repaired.
- Same jitter as A59: the graph is exonerated; the collective path
  (`twoshots`/public oneCCL) or the QSA/prefill kernels are next, toggled
  one at a time.
- A hang like A59's: the hang class is not graph-specific either.

No speed is claimed. Protected results remain unchanged.
