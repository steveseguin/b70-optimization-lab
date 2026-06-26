# 2026-06-26T21:05Z Gate/Up Fast Path Seeding Route Cache - Loss

## Patch

Default-off source experiment in
`/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/ggml-sycl.cpp`:

- add `LLAMA_SYCL_MUL_MAT_ID_GATE_UP_FAST_SEED_ROUTE_CACHE=1`;
- apply the direct multi-token `MUL_MAT_ID` fast path only to node names
  containing `ffn_moe_gate_up`;
- before launching that fast path, build the normal host route-cache metadata
  from the same `ids`, so the following `ffn_moe_down` can still use
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`;
- keep the down projection on the current validated route-cache path.

Harness capture added the env key to:

- `scripts/run-gemma4-26b-first-baseline.sh`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh`.

## Result

Run:
`data/gemma4-q8-gpu2-gateupfast-seedroute-screen-20260626T210513Z/summary.json`

Config: current promoted Gemma 4 26B A4B Q8 record recipe plus:

```bash
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
LLAMA_SYCL_MUL_MAT_ID_GATE_UP_FAST_SEED_ROUTE_CACHE=1
```

Validity:

- canary: `96/96` repeats, `384` rows, pass;
- benchmark cached tokens: `[0, 0, 0, 0]`;
- row0 is fresh-response eligible.

Performance:

- fresh row0 after TTFT: `76.68309224299286 tok/s`;
- support mean after TTFT: `76.5484238319723 tok/s`;
- current valid record: `103.51547512013657 tok/s`.

## Decision

Reject. Do not promote. Do not submit to LocalMaxxing.

The design is correct under the screen gate, but it is a large speed loss. The
host route-seeding copy / wait and graph disruption dominate any savings from
using the direct gate/up fast path. This closes the route-cache-seeded gate/up
fast-path lane as implemented.

Future work should only revisit this if route metadata can be seeded without a
host wait and without disabling the current graph-friendly record path.
