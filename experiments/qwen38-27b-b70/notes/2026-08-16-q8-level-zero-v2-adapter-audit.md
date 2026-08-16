# Qwen3.8 Q8 Level Zero v2 adapter audit

Date: 2026-08-16

Host: 2x ASRock Intel Arc Pro B70, 32 GiB per card; 16 GiB host RAM

Scope: target-only Q8_0, F16 KV, equal TP2, no MTP/DFlash/speculation

## Outcome

The Level Zero v2 Unified Runtime adapter is materially faster than forcing
the legacy adapter, but v2 is already the default on the validated oneAPI
2026.1.1 runtime. The Qwen3.8 repro now exports
`SYCL_UR_USE_LEVEL_ZERO_V2=1` to make that runtime identity explicit. This is
not a new headline speed gain.

Both brackets used the accepted Qwen3.8 direct-Q8 binary and model with
`p64/n256/r3`, `b1024/ub256`, equal TP2, F16 KV and a fresh process per arm.
The binary reported `VERIFY_MISMATCH=0` and identical fusion counters in every
run.

## Forced v2 versus forced legacy

Position-balanced order: legacy, v2, v2, legacy.

| Adapter | Decode arms (tok/s) | Mean (tok/s) |
| --- | --- | ---: |
| Level Zero v2 | `36.039391`, `36.053099` | **`36.046245`** |
| forced legacy | `34.861560`, `34.877399` | **`34.869480`** |

The v2 advantage is `+3.374772%` relative to forced legacy.

## Explicit v2 versus unset default

Position-balanced order: unset, explicit v2, explicit v2, unset.

| Runtime selection | Decode arms (tok/s) | Mean (tok/s) |
| --- | --- | ---: |
| explicit v2 | `36.092021`, `36.067951` | **`36.079986`** |
| selector unset | `36.010644`, `36.070006` | **`36.040325`** |

The `+0.110046%` difference is run noise. This confirms that the unset
2026.1.1 runtime already selected the v2 path. The explicit export prevents a
future environment or runtime from silently falling back to the slower
legacy adapter.

## Decision

Keep `SYCL_UR_USE_LEVEL_ZERO_V2=1` in the reproduction package. Do not add
`3.375%` to the accepted result: the accepted result already ran on the v2
default. Retain the legacy comparison only as evidence for the runtime pin.

Machine-readable values are in
[`2026-08-16-q8-level-zero-v2-adapter-audit.json`](../data/2026-08-16-q8-level-zero-v2-adapter-audit.json).
