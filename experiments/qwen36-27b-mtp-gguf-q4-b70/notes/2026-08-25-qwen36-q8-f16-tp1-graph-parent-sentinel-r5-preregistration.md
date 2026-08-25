# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R5 preregistration

State: **preregistered, not launched**. R5 is a fresh full rerun.

R4 passed every mechanism and parity gate, then failed because an unrelated
remote commit landed during postflight. R5 changes no graph, model, runtime,
output, or parity rule. It changes only remote freshness scope:

- launch still requires clean pushed local `main` equal to live origin;
- after launch, local HEAD and all 26 packet blobs are frozen and rechecked;
- a later remote-only commit no longer invalidates the immutable local run;
- full model stat, binary/build/protected, DSO, cleanup, and idle postflight
  remain mandatory.

R4 contributes no reusable arm. Fresh root:
`/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r5`.
Acknowledgement:
`RUN qwen36-q8-f16-tp1-graph-sentinel-20260825-r5`.
