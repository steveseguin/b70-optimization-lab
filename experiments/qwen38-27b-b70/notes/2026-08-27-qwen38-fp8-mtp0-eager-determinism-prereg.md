# Qwen3.8 FP8 MTP0 eager determinism preregistration

## Trigger and hypothesis

Two independently compiled PIECEWISE/XPU-Graph MTP0 attempts matched only
8/12 complete outputs. Two new servers beginning from byte-identical copies of
one compiled-kernel cache still matched only 10/12. Compiled-cache identity is
not sufficient. The runtime warns that XPU Graph is experimental and supports
only single-GPU execution, while this package uses TP2.

The bounded hypothesis is that disabling graph capture and enforcing eager
execution restores fresh-server target determinism. This is a different,
slower operating profile and must not inherit the graph result's speed.

## Frozen profile

- same official FP8 model revision, block-W8A16 image, two B70s, TP2, FP16 KV,
  direct P2P collective policy, one active sequence, 1,024-token capacity, and
  1,024 max batched tokens as the strict graph MTP0 profile;
- target-only/MTP0, `VLLM_XPU_ENABLE_XPU_GRAPH=0`, `VLLM_XPU_GRAPH=0`, and
  `--enforce-eager`; no compilation configuration;
- two fresh containers and new empty non-prompt cache directories;
- unchanged complete 12-prompt, six-class, 512-cap, cache-zero benchmark and
  post-suite objective canaries.

The launch recipe is
[`run-w8a16-eager-server.sh`](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-eager-server.sh).

## Decision

The primary correctness gate is 12/12 complete token-array equality between
the two fresh eager servers. Both must also pass all workload and objective
canary gates. Compare eager outputs to both graph attempts and disclose any
runtime-order differences; eager is not automatically an oracle merely because
it is deterministic.

If eager remains below 12/12, graph capture is not required for the observed
nondeterminism and the official-FP8 TP2 headline remains pending. If eager is
12/12, it becomes the determinism-qualified target control; promoting an MTP
profile still requires exact equality to that eager target or a separately
approved quality tolerance, never speed alone.
