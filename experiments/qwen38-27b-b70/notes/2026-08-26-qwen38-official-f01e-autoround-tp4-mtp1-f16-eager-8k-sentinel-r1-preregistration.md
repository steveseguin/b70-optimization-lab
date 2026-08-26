# Official f01e AutoRound TP4 eager MTP1/F16 8K sentinel R1

Status: **preregistered and executable; not launched**.

This is the first current-f01e TP4/MTP1 control. It changes only the native
speculative binding from the successful TP4/MTP0 parent: method
`qwen3_next_mtp`, one speculative token. Topology remains all four B70s,
`ZE_AFFINITY_MASK=0,1,2,3`, TP4, memory utilization 0.60, eager graph-off,
F16/auto KV, one sequence, and a 32,896-token capacity. No
`ONEAPI_DEVICE_SELECTOR` is set.

The parent is the just-run same-image, same-topology TP4/MTP0 oracle. Its
terminal receipt is pinned at SHA-256 `779c6441...`; its exact-8K raw result is
pinned at `49ea5caa...` and contains the 128-token hash `34e792cc...`; its
quality result is pinned at `20192404...`. MTP1 must exactly match all 128 TP4
parent tokens. TP1 happened to match that hash too, but is context only and is
not the target or quality baseline.

Prometheus counters are snapshotted immediately before and after only the exact
8K request. Startup and the later quality traffic cannot satisfy the mechanism
gate. Drafted and accepted deltas must both be positive, accepted must not exceed
drafted, and the exact request must pass every prompt-depth, completion, token-ID,
cache-zero, and timing gate.

Startup must resolve the exact native configuration as
`SpeculativeConfig(method='mtp', model=<target>, num_spec_tokens=1)`. The 29
embedded `mtp.*` tensors, target config/index, runtime image/source/package, all
four rank/local-rank pairs, eager mode, graph-off mode, and F16 cache identity
are fail-closed. An exact unsupported-method log may be classified unsupported;
a binding failure or generic worker/startup failure remains failed.

Objective quality requires `pass_all` plus explicit `cached_tokens == 0` on all
16 usage records: seven exact cases, eight repeat runs, and the long-context
case. Missing cache telemetry fails. `baseline_match_all` compares to the frozen
same-topology TP4/MTP0 quality result. A baseline-only mismatch is retained as a
lower-grade passed sentinel caveat, but target-token mismatch, inactive
acceptance, objective-quality failure, or exact-depth failure is quarantined.

The cache is a fresh ext4 root using the proven per-rank namespaces. Graph-off
should produce no compilation files; if it does, all artifacts must stay within
`rank_0_0` through `rank_3_0`, all four ranks must be represented, and no shared
file is allowed. Startup and requests are bounded; EXIT/INT/TERM cleanup and an
all-render-node postflight are mandatory.

There is no speed floor or historical replacement authority. Every outcome is
additive and retained, and no descendant launches automatically.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-r1.sh --check
```

GPU execution (not performed during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-20260826-r1'
```
