# Qwen3.6 embedded-MTP Q8/F16 TP1 SYCL-graph exact-depth R1 preregistration

This sealed, inert packet fills one missing seven-cell slice: the pinned
embedded-MTP Q8_0 GGUF running target-only (`MTP0`) with F16 KV on one B70 and
SYCL graph cache 8. Exact active-context depths are `0, 2048, 4096, 8192,
16384, 24576, 32768`.

The packet reuses the passed target-Q8/F16 R4 phase-aware runner. The only
runtime delta is the model identity and path: artifact
`qwen36-27b-unsloth-mtp-q8-0-5cb35eb`, revision
`5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, size `29047084160`, SHA-256
`9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`.
The accepted graph-off manifest and result for that exact artifact are
checksum-bound. They transfer model/workload identity only, never speed or
publication authority.

Source `fa0f3b25...`, the graph-enabled build and backend, 32-library closure,
three-patch chain, complete optimization environment, verbose argv, cache size
8, and all phase-aware conservation gates remain unchanged. `MTP0` means the
embedded tensors are present but speculation is not engaged.

Each context must independently produce exactly two ordered graph summaries.
Prefill may be classified mixed partial when cache 8 fills, under the frozen
conservation equations. Decode must replay every requested graph with zero
cache-full, compatibility-rejection, or unsupported-device events.

Default invocation is inert and `--check` performs static checks only. A launch
is create-only and requires the exact acknowledgement. Even a pass creates only
seven raw-engine cells with quality pending; it cannot publish, submit a
record, replace graph-off values, or alter any featured speed.

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-sycl-graph-exact-depth-r1.py --check
```
