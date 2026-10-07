# Explicit KV budget admission

Use **`--kv-cache-memory-bytes 2147483648`**, meaning 2 GiB per GPU, for one
separately preregistered application reload. Preserve the healthy first arm's
results and keep the 24 GiB task admission floor unchanged. No host setting,
cache precision, context limit, task, or retry policy changes are proposed.

The exact installed R276 parser registers the full option in
[`arg_utils.py`](source/vllm/engine/arg_utils.py#L1215).
[`CacheConfig`](source/vllm/config/cache.py#L180) defines it per GPU and says it
overrides the utilization-based cache budget. The
[`worker`](source/vllm/v1/worker/gpu_worker.py#L475) still runs dummy-input
profiling, but returns the explicit budget instead of sizing KV from remaining
device memory. Its printed `--kv-cache-memory` suggestion is abbreviated;
use the registered full spelling above.

At TP2, 16 full-attention layers, two local KV heads, head dimension 256,
K plus V, and two-byte FP16 elements require **32,768 bytes per token per GPU**.
One 33,024-token sequence therefore needs **1.0078125 GiB of attention KV per
GPU**. Recurrent state, hybrid grouping and alignment add overhead. Scaling
the first arm's observed 287,232-token capacity at about 9.51 GiB suggests
roughly 60,400 tokens at 2 GiB; this is an estimate, not an admission result.
The runtime must report at least 33,024-token capacity and pass the unchanged
boundary/transport gates. Do not enable context auto-fit.

This reduces the requested device allocation by about 15 GiB across two cards.
If that returned host backing memory one-for-one, the reported 23.5 GiB host
availability would rise to about 38.5 GiB, or about 30.5 GiB after allowing
6 GiB for source copies and 2 GiB for a CPU task. Driver memory behavior is
not guaranteed to scale that way. Check actual host availability after startup
and before each task; an estimate cannot override the frozen 24 GiB floor.

[`capacity-review.json`](capacity-review.json) records calculations and limits.
[`provenance.json`](provenance.json) hashes four exact installed source files,
the retained license and the [first-arm cache log excerpt](first-arm-cache-log.txt).
Sources were copied read-only from the exact R276 container; it was exited
cleanly when preservation completed. Source hashes and Python syntax passed.
No container was started, no model request was sent, and no GPU probe was run
for this review. New-arm capacity and correctness remain to be measured.
