# Qwen3.8 Q8 Unified Runtime event controls: endpoint neutral

Date: 2026-08-16  
Disposition: closed; no runtime flag promoted

## Why these controls were tested

The installed oneAPI 2026.1 Level Zero adapter exposes event controls that
were not in the earlier V2 dispatch screen. The official
[Unified Runtime Level Zero reference](https://oneapi-src.github.io/unified-runtime/core/LEVEL_ZERO.html)
defines:

- `UR_L0_IN_ORDER_BARRIER_BY_SIGNAL`: choose a signal (`1`) or true barrier
  command (`0`) for an in-order barrier;
- `UR_L0_DEVICE_SCOPE_EVENTS=1`: create host-visible proxy events on demand;
- `UR_L0_DEVICE_SCOPE_EVENTS=2`: make only the final command in a batch
  host-visible.

All are process-local submission/event changes. They do not change model
weights, quantization, KV type, tensor split, or sampler arithmetic.

## Signal-based in-order barriers and default correction

The first pass treated unset as a true-barrier control and explicit `1` as a
candidate. A later source audit corrected that interpretation. Both Unified
Runtime v0.11.10 and current source use this implementation default:

```cpp
return (UrRet ? std::atoi(UrRet) : true);
```

The installed adapter is v0.12.0. Although its exact Intel package commit is
not embedded in the binary, unset-versus-`1` endpoint identity is consistent
with the same default. The following apparent brackets therefore primarily
measure run-block drift between equivalent signal-barrier processes, not a
feature gain:

| Arm | Means | Pooled |
| --- | --- | ---: |
| control | `35.980121`, `36.162427` | `36.071274 tok/s` |
| signal barrier | `36.887511`, `36.134672` | `36.511092 tok/s` |

A reversed `p64/n512/r3` B-A-A-B bracket also favored the candidate:

| Arm | Means | Pooled |
| --- | --- | ---: |
| signal barrier | `36.458223`, `36.852167` | `36.655195 tok/s` |
| control | `36.020535`, `35.940755` | `35.980645 tok/s` |

Fresh server processes also ran the same fixed 12-prompt, 512-token cache-cold
suite:

| Endpoint arm | Conventional median | TTFT median | Exact hashes | Cache zero |
| --- | ---: | ---: | ---: | ---: |
| control | `35.831076 tok/s` | `177.025 ms` | 12/12 | 12/12 |
| explicit signal barrier (`1`) | `35.852734 tok/s` | `176.709 ms` | 12/12 | 12/12 |

The endpoint delta is only **`+0.060%`**, confirming that unset and explicit
`1` behave identically. The corrected true-barrier experiment explicitly set
`UR_L0_IN_ORDER_BARRIER_BY_SIGNAL=0`; it measured `35.908476 tok/s` against
the immediately following unset/default control at `36.875038 tok/s`, a
`-2.621%` regression. Keep the faster signal behavior, but do not add a
redundant explicit variable to the reproduction.

## Device-scope events

The remaining modes measured `36.033450 tok/s` for scope 1 and
`36.166350 tok/s` for scope 2 in bounded `p64/n256/r3` screens. The next
unchanged control measured `36.909539 tok/s`, exposing another fast run block.
Neither mode warranted the expensive endpoint gate.

## Decision

Do not add any of these variables to the public Q8 recipe. Signal barriers are
already the adapter behavior when the variable is unset, and explicitly
disabling them regresses decode; device-scope modes did not clear the direct
screen. This result also reinforces the rule that apparent llama-bench
improvements must be tied to a genuinely different treatment before promotion.

Structured evidence and raw hashes are in
[`2026-08-16-q8-ur-event-controls-neutral.json`](../data/2026-08-16-q8-ur-event-controls-neutral.json).
