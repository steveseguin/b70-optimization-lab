# Why packet58 starts with global LRU

A CPU replay of packet55's retained independent calibration routes supports
trying global LRU. It does **not** establish the one-card engine's hit rate
or speed. Packet55's quoted 92.5% is a fixed per-layer cache result; packet58
must measure its own between-position admission policy in device windows.

The [replay](cache_policy_replay.py) validates packet55's converter, raw trace,
request and manifest hashes using the original analyzer before reading the
403,168 route records. It never opens model weights or GPUs. Twelve prompts
train the reset cases; the other twelve are evaluated. None are the benchmark
prompts. All observed speculative/rejected target visits remain charged.

| 18 GB diagnostic policy | Prefill byte hit | Decode byte hit | Missed experts per decode layer visit | Missed MB per decode layer visit |
| --- | ---: | ---: | ---: | ---: |
| Packet55 fixed layer quotas, train-only start reset per prompt | 82.63% | 92.46% | 0.7503 | 1.4926 |
| Global LRU, train-only start reset per prompt | 82.50% | 93.64% | 0.6354 | 1.2595 |
| Global LRU, empty at first held-out prompt, persistent thereafter | 84.88% | 93.67% | 0.6323 | 1.2533 |

These are exact replay observations, not interpolated cache curves or model
performance measurements. The fixed-quota row reproduces packet55's prior
18 GB LRU result. Global LRU has fewer decode misses in this replay and
similar prefill demand. Packet58 therefore keeps a global byte arena with
256-byte alignment, first-fit placement and least-recently-used eviction.
The immutable weight cache starts empty and persists across requests in the
same process. No prompt content or response becomes cached state.

The replay also exposes fragmentation: the persistent global cache ends with
8,948 resident experts, 17,713,561,600 occupied bytes and 439 free extents.
Mixed expert sizes can force more than one eviction before a contiguous
extent fits. The simulator preserves that behavior rather than treating all
free bytes as interchangeable. The 18 GB global budget is data storage;
pointer tables are separately charged in [MEMORY.md](MEMORY.md). Packet55's
18 GB budget includes its own alignment and metadata, so the capacities are
close but not identical.

The main limit is scheduling. This replay admits after each observed layer
route in packet55's timestamp order across two cards. The one-card zero-copy
path admits after each complete position. Its plain decoding also avoids the
speculative visits present in packet55. These differences prevent transferring
93.64% or 93.67% to the engine, even though every source route is real. This
is evidence for which policy to test, not proof of native cache performance.
The device cache log and cold-fill costs remain required evidence.

[Full compact result and source hashes](cache-policy-replay.json). Reproduce
into a new output, from the repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet58-onecard
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cache_policy_replay.py" \
  --output "$P/cache-policy-replay-repeat.json"
```

Four small CPU tests check simultaneous route touching, LRU eviction,
fragmented first-fit behavior, too-small capacity and bounded metadata. No
large pin is used. Credit Niko1221 / Strata for the hot-expert cache idea;
this policy implementation and replay are independently written lab code.
