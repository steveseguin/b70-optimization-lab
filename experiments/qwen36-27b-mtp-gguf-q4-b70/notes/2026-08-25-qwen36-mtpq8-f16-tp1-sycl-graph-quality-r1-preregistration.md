# Qwen3.6 embedded-MTP Q8/F16 TP1 SYCL-graph quality R1

This is a mechanical model-identity sibling of the passed target-Q8/F16
quality battery. It changes the complete model identity to the checksum-pinned
embedded-MTP Q8_0 artifact, binds the completed embedded-MTP graph curve, and
uses a distinct campaign, alias, acknowledgement, and create-only output root.
Source, build, 33-DSO server closure, graph environment, F16 KV, TP1, MTP0,
service flags, tokenizer, quality helper, and every quality/graph gate are
unchanged. The artifact contains MTP tensors, but this target-only arm loads no
speculator (`--spec-type none`).

One fresh isolated server runs four exact canaries, eight deterministic greedy
repeats, and the 31,744-token needle under a 32,768-token service. All 13
requests must pass and report `cached_tokens=0`. The server must emit positive
SYCL graph capture and replay with zero compatibility rejection and zero
unsupported-device evidence.

A pass may satisfy the quality prerequisite for all seven embedded-MTP-artifact
Q8/F16 graph-curve cells because their model, runtime, graph, TP, MTP, KV, and
environment identities are shared. It cannot change the raw speeds, upgrade
mixed-partial prefill above depth zero, authorize publication or record
submission by itself, or replace protected graph-off values.

The default command is inert. Static validation is:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-sycl-graph-quality-r1.py --check
```

Execution requires the exact acknowledgement printed by `--check`; this packet
does not launch it.
