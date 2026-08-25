# Qwen3.6 target-Q8/q8-KV TP1 SYCL-graph exact-depth R2 preregistration

This sealed R2 supersedes, but does not modify, the old unsealed q8-KV graph
R1 packet. It inherits the passed F16 R4 graph-curve lifecycle and exact runtime
identity. The sole runtime delta is `-ctk q8_0 -ctv q8_0`; the matching selector
label is `kv=q8_0`.

The graph-enabled source, binary, backend, model, 32-DSO closure, environment,
cache size 8, verbose logging, seven contexts, and ordered prefill/decode
conservation gates remain byte-for-byte inherited. The accepted q8-KV graph-off
manifest and result are separately checksum-bound for identity comparison only.

The default invocation is inert and `--check` is CPU-only. Execution is
create-only under the distinct R2 root and requires the exact acknowledgement.
A successful run yields at most seven raw graph cells with quality pending; it
does not authorize site publication, a quality claim, a record submission, an
estimate, or replacement of protected graph-off values.

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-q8kv-tp1-sycl-graph-exact-depth-r2.py --check
```
