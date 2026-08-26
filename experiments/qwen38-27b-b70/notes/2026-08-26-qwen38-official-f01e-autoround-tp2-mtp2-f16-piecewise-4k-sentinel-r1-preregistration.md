# Official f01e AutoRound TP2 PIECEWISE MTP2/F16 exact-4K sentinel R1

Status: **preregistered and executable; not launched**.

This is one bounded current-f01e TP2/PIECEWISE/native-MTP2/F16 exact-4K sentinel. It is not a depth ladder, an automatic descendant, or a publication packet. No other topology, graph mode, MTP depth, KV mode, context depth, or family cell is inherited.

The exact target oracle is the same-image, same-topology TP2/MTP0 PIECEWISE exact-4K receipt (`947a2459...`), which returned token hash `3febb16e...`. The same-topology TP2/MTP2 eager 4K receipt (`426062cb...`) returned the same 128 IDs and independently proved 94 drafted / 80 accepted tokens, full quality, both-worker topology, rank-cache isolation, model verification, and cleanup. Its eager speed does not transfer to this graph profile.

Every non-4K exact cell is deliberately absent. Existing TP2 target and eager evidence at other depths is out of scope; the quality suite's 8K needle is semantic quality evidence only and cannot create an exact-8K performance cell or expansion authority.

The runner launches one fresh TP2 server on devices `0,1` with native embedded MTP2, F16 KV, PIECEWISE size-one graph capture, port `19527`, and dedicated output/cache/container identities. Startup must prove the exact image/source/model, AutoRound `quantization=inc`, native `mtp` depth two, `enforce_eager=False`, mixed-prefill/decode PIECEWISE capture, and both world/local ranks. `ONEAPI_DEVICE_SELECTOR` is absent.

Counters are bracketed immediately around the single exact-4K request. Drafted and accepted deltas must be finite, positive, and conserved. The exact request must pass all depth/cache gates and match the TP2/MTP0 parent token-for-token; the pinned TP2/MTP2 eager evidence must first match the same target.

The candidate then runs the full quality and baseline battery: 7 exact cases, 8 identical repeats with one hash, the long-context needle, 24 true baseline comparisons, and cache zero on all 16 requests. Rank cache must contain exactly `rank_0_0` and `rank_1_0`; all 19 model files must verify; cleanup must leave no container, port, model-server process, or render owner.

There is no speed floor, site authority, protected-value replacement, LocalMaxxing action, automatic publication, or automatic expansion. A pass remains exact-4K internal evidence pending human adjudication.

Static check (inert):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp2-f16-piecewise-4k-sentinel-r1.sh --check
```

GPU execution (not performed by this preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp2-f16-piecewise-4k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp2-mtp2-f16-piecewise-4k-sentinel-20260826-r1'
```


The original TP1/MTP2 PIECEWISE runner omitted its cache gate. Its retained result and posthoc cache audit are diagnostic context only and provide no parent, oracle, cache, correctness, performance, or publication authority here.

Coverage-contract proposal: `qwen38-tp2-vllm-xpu-autoround-f01e-mtp2-piecewise-depth`, with fixed TP2/MTP2/PIECEWISE/F16/native-MTP selectors and active-context axis `[0, 2048, 4096, 8192, 16384, 24576, 32768]`. Exact 4K is the sole preregistered candidate; the other six selectors remain explicitly missing. This preparation does not edit family/site data.
