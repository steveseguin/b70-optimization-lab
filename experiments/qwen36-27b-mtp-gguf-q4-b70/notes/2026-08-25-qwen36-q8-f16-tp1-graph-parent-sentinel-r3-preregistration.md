# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R3 preregistration

State: **preregistered, not launched**. R3 is another fresh full sentinel.

R2 proved that the lifecycle repair works and produced the exact
compile-guarded all-zero graph-off shutdown summary. It failed only because
three extra configuration strings are not emitted by this retained backend.
The graph candidate never ran, so R2 contributes no reusable arm.

R3 changes only the control parser. It removes the unavailable human-readable
configuration strings and requires exactly one `[SYCL-GRAPH] summary` for
device 0 with cache limit zero and every graph action/rejection/cache counter
zero. This is stronger machine-readable evidence than the removed strings:
the summary is compiled only under `GGML_SYCL_GRAPH`, and its values directly
report the runtime behavior being gated.

The candidate gate is byte-for-byte unchanged: positive requested,
recording-entered, replayed, direct-replay, recorded/created/cache-hit counts;
cache limit 8; zero compatibility and device rejection. R3 also retains R2's
single-turn mode, `/dev/null` stdin, disabled UI timings, verbosity 4, exact
stdout parity, fresh roots, model/DSO/build seals, locks, compute oracle,
watchdog, cleanup, postflight, and zero matrix/site/speed authority.

The fresh root is
`/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r3` and
the acknowledgement is
`RUN qwen36-q8-f16-tp1-graph-sentinel-20260825-r3`.
