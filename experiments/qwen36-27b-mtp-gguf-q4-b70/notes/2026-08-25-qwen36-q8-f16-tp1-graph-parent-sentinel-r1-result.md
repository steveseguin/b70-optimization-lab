# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R1 result

State: **failed-incomplete because of the CLI lifecycle harness**. This is not
a graph failure, a correctness result, or matrix evidence.

R1 used the create-only root
`/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r1`.
The direct-then-ordinary model verifier passed on the frozen model digest in
36.47 seconds, and the real GPU0 compute gate passed in 2.42 seconds. The
graph-off control then generated all 64 requested tokens at the expected
roughly 15.6 tok/s, printed another interactive `> ` prompt, and remained
alive until the 900-second watchdog terminated and cleaned its process group.

The terminal receipt is `failed` at `control-graph0-cache0`, with
`cleanup_passed=true`. The control has no receipt, the graph candidate never
started, and no arm is reusable. R1 therefore authorizes zero graph cells,
zero parity claims, zero speeds, and no website or submission change.

Two additional harness defects were exposed without another GPU run:

- raw stdout contained the dynamic line
  `[ Prompt: 33.3 t/s | Generation: 15.6 t/s ]`, so whole-stream parity would
  not be deterministic across graph-off and graph-on arms;
- stderr was empty because this `llama-cli` defaults to error-only logging,
  while the required graph counters are emitted at GGML INFO verbosity.

The independently reviewed R2 repair is deliberately limited to lifecycle and
observability: use a fresh root and acknowledgement, add `--single-turn`,
connect stdin to `/dev/null`, add `--no-show-timings`, and use log verbosity 4
so the retained GGML INFO graph evidence reaches stderr. The model, binary,
34-DSO closure, graph variables, prompt, token count, seed, KV mode, four locks,
model verification, compute oracle, process-group watchdog, cleanup gates, and
zero publication/speed authority remain unchanged. R2 must rerun everything;
it may not inherit a result from R1.

Immutable predecessor hashes are captured in the adjacent structured result.
The raw R1 root remains preserved.
