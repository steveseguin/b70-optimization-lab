# TP2 historical autotune-winner bundle

This directory preserves the 78 TorchInductor/Triton `.best_config` decisions
from the certified Qwen3.8 TP2 cache. It is an optimization-data overlay, not a
compiled cache and not a source patch.

The source cache was:

```text
/var/tmp/qwen38-nightly-strict-cache/tp2-mtp0-f16-graph-isolated-repeat-b
```

Only `.best_config` files were copied. No generated Python, `.kernel_perf`,
Triton binary/cache object, compiled model, outer vLLM cache, or AOT artifact is
present here. `source/` retains the two-character Inductor subdirectories. The
78 source files total 20,619 bytes and are enumerated by `manifest.sha256`; the
manifest-file SHA-256 is
`65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757`.

This mapping is valid only for the fail-closed identities in `metadata.json`.
The current-runtime compile must produce the expected code/compiler/config/env
and per-rank graph hashes, must compile a fresh AOT model, and must leave all 78
seed records byte-identical. A newer nightly requires a new mapping and full
identity audit; this bundle must never be applied merely because the model name
matches.

Use
[`run-20260823-qwen38-tp2-autotune-winner-overlay.sh`](../../scripts/run-20260823-qwen38-tp2-autotune-winner-overlay.sh).
The fresh diagnostic arm is allowed first. The strict/quality replay is gated
on the diagnostic meeting the frozen historical floor.
