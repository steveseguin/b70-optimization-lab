# TP4 historical autotune-winner bundle

This directory preserves the 152 TorchInductor/Triton `.best_config`
decisions from the certified Qwen3.8 TP4 cache. It is an optimization-data
overlay, not a compiled cache and not a source patch.

The source cache was:

```text
/var/tmp/qwen38-nightly-strict-cache/tp4-mtp0-f16-graph-natural-eos-a
```

Only `.best_config` files were copied. No generated Python, `.kernel_perf`,
Triton binary/cache object, compiled model, outer vLLM cache, or AOT artifact
is present here. `source/` retains the two-character Inductor subdirectories.
The 152 source files total 40,158 bytes and are enumerated by
`manifest.sha256`; the manifest-file SHA-256 is
`a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2`.

This mapping is valid only for the fail-closed identities in `metadata.json`.
The current-runtime compile must produce the expected
code/compiler/config/environment and four per-rank graph hashes, must compile
a fresh AOT model, and must leave all 152 seed records byte-identical. A newer
nightly requires a new mapping and full identity audit; this bundle must never
be applied merely because the model name matches.

Use
[`run-20260823-qwen38-tp4-autotune-winner-overlay.sh`](../../scripts/run-20260823-qwen38-tp4-autotune-winner-overlay.sh).
The fresh diagnostic arm is allowed first. Strict replay A is conditional on
its speed gate, and exact-cache replay B is conditional on replay A's quality
and lower historical floor.

The bounded program is now closed and passed: fresh diagnostic measured
`71.722545 tok/s`, and exact-cache strict A/B measured
`71.352872 / 71.454271 tok/s` with full replay-A quality and an immutable
2,117-file current-runtime cache. The accepted claim is the exact
`a3561ef8`-plus-overlay profile and observed strict range, not a claim that the
upper value replicated. See the
[result note](../../notes/2026-08-23-qwen38-tp4-autotune-winner-overlay-result.md).

This mapping remains target-runtime-specific. When the rolling nightly moves,
remap the decisions and rerun all gates on the newer source; do not retain the
older base merely to keep this result.
