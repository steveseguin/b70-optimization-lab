# Qwen3.8 27B Q8 TP2 upstream GDN cache-writeback fusion

Date: 2026-08-16

Status: closed during source audit; already subsumed by the accepted stack.

## Source and rationale

Fresh remote audit on 2026-08-16 found upstream llama.cpp at
`4df29be4f4c3673f428170fda944a5b19f743bb8`. Matthew Dodd's
`intel-sycl-optimization` branch remains at the accepted base
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`; it has no newer SYCL commit.

Upstream commit
[`3d93885352a0049c8388a0da0698ec1a69e60d90`](https://github.com/ggml-org/llama.cpp/commit/3d93885352a0049c8388a0da0698ec1a69e60d90)
fuses the strided recurrent-state cache copy into the gated-delta-net kernel.
Its commit record reports a repeatable `+1.2%` tg128 gain on an Arc Pro B70
running Qwen3.6 27B Q4_K. The accepted Qwen3.8 Q8 TP2 tree has neither
`ggml_sycl_gated_delta_net_fused_cache` nor
`ggml_sycl_try_gdn_cache_fusion`, so this mechanism is not already present.

The newer generic upstream unary-plus-multiply fusion was not selected for
this arm: the accepted stack already has Qwen-specific, direct-Q8 GDN tail
fusions that subsume its important decode shapes. The state-writeback change
is orthogonal and has a stronger measured B70 result.

## Contract

- port only the GDN state-writeback mechanism from upstream `3d9388535` into
  the accepted Q8 source;
- retain all accepted Q8, TP2 collective, GDN arithmetic, and direct-Q8
  fusion paths;
- put graph recognition and fused writeback behind a default-off environment
  door and log live/declined counts;
- treatment must remove the standalone state-cache copy for the recognized
  graph without changing the state layout, rollback slots, arithmetic, or
  output stores;
- add a treatment-only poison/reachability control and require normal fixed
  completion to match control byte-for-byte;
- run a bounded same-binary position-balanced screen before any full suite;
- promote only after a repeatable gain and the complete quality contract.

Build no more than two jobs under the established 8 GiB host-memory cap. Stop
on any device-lost, reset, hang, timeout, or output mismatch.

## Audit outcome

The initial symbol check used upstream's new names and missed the accepted
stack's older, stricter implementation. No candidate build was started.

The accepted source already provides:

- `GGML_SYCL_FUSED_GDN_STATE_IO=1`, enabled by the Qwen3.8 repro;
- `ggml_sycl_find_gdn_state_io`, which recognizes the exact one-sequence,
  one-retained-slot Qwen graph;
- `ggml_sycl_gated_delta_net_beta_sigmoid_state_io`, which reads and writes
  the persistent state directly in place;
- removal of both the input `GET_ROWS` and output `CPY`, while upstream
  `3d9388535` removes only the output state-copy tail;
- a treatment poison and live counters already used by the lab's quality
  contract.

This direct-state mechanism previously delivered a matched `+3.132%` on the
Qwen3.6 Q8 TP2 progression and is carried into the accepted Qwen3.8 Q8 repro.
Upstream `3d9388535` is therefore not a new additive optimization for this
stack. Do not port or benchmark it unchanged. This correction was committed
immediately so other hosts do not duplicate the audit mistake.
