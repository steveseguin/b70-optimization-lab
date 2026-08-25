# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R2 preregistration

State: **preregistered, not launched**. R2 is a fresh complete sentinel, not a
resume of R1 and not a context curve.

R1 completed model verification, the GPU0 compute gate, model loading, and all
64 control tokens, then remained in the old CLI's next interactive read until
the watchdog cleaned it. Its default error-only logger also hid the required
INFO graph counters, and its stdout included dynamic timing text. R1 is closed
as failed-incomplete and contributes no reusable arm.

R2 keeps the exact R1 model, immutable launcher, graph-enabled build receipts,
34 effective DSO hashes, prompt, seed, token count, F16 K/V mode, graph
treatments, locks, verification, compute oracle, unsafe-variable exclusions,
timeout, process-group cleanup, and postflight. Its only deltas are:

1. fresh campaign/root/acknowledgement ending in `r2`;
2. `--single-turn` and child stdin `/dev/null`, so the predefined turn must
   finish without another interactive read;
3. `--no-show-timings`, so raw stdout is eligible for exact-byte parity;
4. `--log-verbosity 4`, because this retained CLI maps backend GGML INFO logs
   to the trace threshold and otherwise emits no graph evidence.

The exact acknowledgement is
`RUN qwen36-q8-f16-tp1-graph-sentinel-20260825-r2`. The create-only root is
`/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r2`.

Every preflight and both arms rerun. A pass remains
`passed-parent-sentinel-only`: it still authorizes no speed, site cell,
LocalMaxxing action, or seven-depth expansion by itself. Any timeout, missing
or rejected graph action, nonzero control graph counter, raw stdout mismatch,
cleanup failure, identity drift, or postflight failure closes R2 with zero
matrix authority.

The compact R2 delta manifest is merged with and cryptographically binds the
full R1 base manifest at runtime. Both manifests, both runners, both R1 result
artifacts, and the R2 tests are sealed as packet blobs on clean pushed `main`.
