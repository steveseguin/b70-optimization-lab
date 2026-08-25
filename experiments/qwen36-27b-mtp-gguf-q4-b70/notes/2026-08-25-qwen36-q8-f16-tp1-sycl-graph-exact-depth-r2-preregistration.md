# Qwen3.6 target-Q8/F16 TP1 SYCL-graph exact-depth R2 preregistration

R1 is preserved as a failed, create-only result. It completed depth 0 and
returned valid benchmark JSON, but its strict graph-evidence gate found no
info-level SYCL graph summary because `llama-bench` was not verbose.

R2 inherits the checksum-pinned R1 manifest and runner. Its sole execution
identity delta inserts `-v` immediately before `-o json`. This exposes the
already-required `GGML_LOG_INFO` graph counters and destructor summary; it does
not change any benchmark selector or optimization knob.

The seven exact contexts remain 0, 2K, 4K, 8K, 16K, 24K, and 32K. Model,
source, build, binary, backend, 32-library closure, environment, graph gates,
timeouts, parser, and authority are inherited unchanged. The output root and
exact acknowledgement are distinct and end in R2. Artifacts remain create-only.

Passing still creates raw graph cells with quality pending. It grants no site,
record, submission, or quality authority and cannot replace protected graph-off
values. The default invocation is inert; `--check` is CPU-only.

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r2.py --check
```

GPU execution requires the exact acknowledgement recorded in the overlay and
is intentionally outside this packet-drafting step.
