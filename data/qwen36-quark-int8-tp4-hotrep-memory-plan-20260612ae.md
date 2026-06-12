# Qwen3.6 Hot-Replication Memory Plan

Per local-shard expert bytes: `795648`
Baseline all-expert MoE weight footprint per rank: `7770.0 MiB`
Runtime KV report: `20.67 GiB`, `2052915` tokens, `62.65x` at `32768` context.
XPU memory snapshot max used: `32651.4 MiB`; min free: `4.6 MiB`.

## Hotset Storage

| hotset | selected layers MiB/rank | all layers MiB/rank |
|---:|---:|---:|
| 16 | 60.7 | 485.6 |
| 32 | 121.4 | 971.2 |
| 64 | 242.8 | 1942.5 |

## Capacity Tradeoff

| hotset | reserve MiB | add MiB/rank | KV tokens to free | remaining 32K concurrency | fits current free? |
|---:|---:|---:|---:|---:|---|
| 16 | 0 | 485.6 | 47102 | 61.21 | False |
| 16 | 512 | 485.6 | 96761 | 59.70 | False |
| 16 | 1024 | 485.6 | 146420 | 58.18 | False |
| 32 | 0 | 971.2 | 94203 | 59.78 | False |
| 32 | 512 | 971.2 | 143862 | 58.26 | False |
| 32 | 1024 | 971.2 | 193521 | 56.74 | False |
| 64 | 0 | 1942.5 | 188405 | 56.90 | False |
| 64 | 512 | 1942.5 | 238064 | 55.38 | False |
| 64 | 1024 | 1942.5 | 287724 | 53.87 | False |

## Decision

- Current accepted TP4/32K/c48 lane is effectively full by telemetry, so an all-layer hot cache cannot be bolted on without reducing KV/graph memory or using a separate latency lane.
- All-layer hot64 storage is small relative to the reported KV budget, but too large for current free VRAM. It is feasible only by carving roughly a few hundred thousand KV tokens from the capacity lane or by running a lower-context static c1 lane.
- The next safe implementation step is a route-replay-only one-layer hot64 prototype, then an explicit low-context sidecar memory screen if the replay kernel shows real latency upside.
