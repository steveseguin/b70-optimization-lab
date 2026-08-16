# Qwen3.8 Q8 Unified Runtime event controls: endpoint neutral

Date: 2026-08-16  
Disposition: closed; no runtime flag promoted

## Why these controls were tested

The installed oneAPI 2026.1 Level Zero adapter exposes event controls that
were not in the earlier V2 dispatch screen. The official
[Unified Runtime Level Zero reference](https://oneapi-src.github.io/unified-runtime/core/LEVEL_ZERO.html)
defines:

- `UR_L0_IN_ORDER_BARRIER_BY_SIGNAL=1`: implement in-order barriers with a
  signal rather than a true barrier command;
- `UR_L0_DEVICE_SCOPE_EVENTS=1`: create host-visible proxy events on demand;
- `UR_L0_DEVICE_SCOPE_EVENTS=2`: make only the final command in a batch
  host-visible.

All are process-local submission/event changes. They do not change model
weights, quantization, KV type, tensor split, or sampler arithmetic.

## Signal-based in-order barriers

A short `p64/n256/r3` screen initially looked positive:

| Arm | Means | Pooled |
| --- | --- | ---: |
| control | `35.980121`, `36.162427` | `36.071274 tok/s` |
| signal barrier | `36.887511`, `36.134672` | `36.511092 tok/s` |

A reversed `p64/n512/r3` B-A-A-B bracket also favored the candidate:

| Arm | Means | Pooled |
| --- | --- | ---: |
| signal barrier | `36.458223`, `36.852167` | `36.655195 tok/s` |
| control | `36.020535`, `35.940755` | `35.980645 tok/s` |

The candidate therefore advanced to the real validity gate. Fresh server
processes ran the same fixed 12-prompt, 512-token cache-cold suite:

| Endpoint arm | Conventional median | TTFT median | Exact hashes | Cache zero |
| --- | ---: | ---: | ---: | ---: |
| control | `35.831076 tok/s` | `177.025 ms` | 12/12 | 12/12 |
| signal barrier | `35.852734 tok/s` | `176.709 ms` | 12/12 | 12/12 |

The endpoint delta is only **`+0.060%`**, well inside ordinary run noise. The
large llama-bench observation does not transfer to realistic serving, so the
flag is not added to the reproduction.

## Device-scope events

The remaining modes measured `36.033450 tok/s` for scope 1 and
`36.166350 tok/s` for scope 2 in bounded `p64/n256/r3` screens. The next
unchanged control measured `36.909539 tok/s`, exposing another fast run block.
Neither mode warranted the expensive endpoint gate.

## Decision

Do not add any of these variables to the public Q8 recipe. The signal form is
quality-safe but endpoint-neutral; device-scope modes did not clear the direct
screen. This result also reinforces the rule that llama-bench improvements
must transfer to the fixed endpoint suite before promotion.

Structured evidence and raw hashes are in
[`2026-08-16-q8-ur-event-controls-neutral.json`](../data/2026-08-16-q8-ur-event-controls-neutral.json).
