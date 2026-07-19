# DSpark incumbent-collective Markov W2 DPAS: negative component gate

Date: **2026-07-19**

## Outcome

The exact BF16 DPAS W2 substitution is bitwise exact through the incumbent
seven-stage W1-replicated, W2-sharded, full-bias-collective Markov transaction,
but it **fails** the frozen pre-model-load performance gate. The slowest-card,
worst-route result is **-0.02025371 ms/cycle saved** on physical card 3 for
`anchor_rank1`, versus the required **+0.15 ms/cycle**.

Per the decision contract, the patch is preserved behind a default-off flag,
production defaults remain off, and work stopped before an Item A+B combined
gate, 96 GiB model load, service launch, B-A-B suite, or LocalMaxxing
submission.

This is a component-cycle result for one active generation. It is not an
endpoint-throughput claim.

## Source and binary identity

- vLLM parent / Item A identity:
  `284ef5942dd83e532bf23de52eaecf6e6fb323db`;
- vLLM preserved Item B patch:
  `eb8a89a18ed040137e4e57bc01888feaa443a95e`;
- XPU kernels, unchanged from Item A:
  `909eaca103fad0d118b7340fc1411edc8b7c4973`;
- loaded `_xpu_C.abi3.so`, both build and package copies:
  `d62ea1cf4728250809052c68fdd74983b4f2c0dcaf924624e7a507c8d4c8392f`;
- real DSpark weight shard SHA-256:
  `a0bbb24f36d2ef6107250088e0f020f93aec0677cd24be3e9e69589547a7656f`;
- fixed real target-token oracle raw SHA-256:
  `f58a7c7ac29ef0590d5398c8531e26b77abbc6b02ddf1ebd7b76407174615c4d`;
- full summary SHA-256:
  `6156a3157c9f65cd1d9a59fe8a0901cb4d9b72372f30851bb3714e627957e137`.

The new flag is:

```text
VLLM_XPU_DSPARK_MARKOV_W2_DPAS=0
```

When enabled it fails closed unless the incumbent persistent,
W1-replicated collective path is active. It rejects full replication and the
sharded, host, IPC-event, and one-shot Markov paths. At model load it retains
one stable `local_w2.t().contiguous()` BF16 `[256,32320]` packed shard per
rank. Inside the seven-step loop it changes only the W2 operation:

```text
torch.mm(embed, local_w2.t(), out=local_bias)
  -> deepseek_markov_m1_bf16_dpas_out(
       local_bias, embed, packed_local_w2, tiles_per_item=2)
```

No source-level graph break, event transport, host barrier, collective,
winner selection, logits addition, token copy, or acceptance rule changed.
The launcher exports the flag with a default of zero and records it in the
identity dump. Rejected event/host/sharded transports, M8 DPAS/pair-tile MHC,
copy-elision, context-WKV, and fixed-M8-builder flags were not changed.

## Exactness gate

The no-model-load harness used all four real W2 shards and real W1 rows selected
by seven changing anchor/ownership routes. DSpark base logits were controlled
changing BF16 component inputs because no captured real DSpark base-logit
corpus exists; they are not represented as endpoint logits.

The fixed-address gate mirrors the incumbent breakable PIECEWISE transaction:
W1 lookup plus W2 is captured before each already-existing all-gather, and
BF16 add plus argmax/token-copy is captured after it. The seven full-bias
all-gathers remain the incumbent explicit collective boundaries. Capturing the
collectives wholesale was rejected as a harness architecture because even the
unmodified `torch.mm` control became stale after changed inputs; that diagnostic
is preserved under the smoke evidence directory and is not used here.

Every valid route passed eager-control -> captured-control A -> captured-DPAS B
-> captured-control A exactness for:

- every per-stage local BF16 W2 output;
- every gathered BF16 bias and full BF16 post-add logit;
- all seven draft token IDs;
- downstream greedy acceptance against the fixed real M8 target-token oracle
  `[19,16,455,20,16,223,21,16]`.

| Physical card / TP rank | Changed A-B-A | Local BF16 | Gathered/logits | Seven IDs | Acceptance |
|---:|---:|---|---|---|---|
| 0 | 7/7 | exact | exact | exact | exact |
| 1 | 7/7 | exact | exact | exact | exact |
| 2 | 7/7 | exact | exact | exact | exact |
| 3 | 7/7 | exact | exact | exact | exact |

The worst route's seven IDs were identical on all ranks:
`[40262,48181,56100,64019,5581,79857,87776]`. Its fixed component acceptance
oracle emitted `[19]`, `num_sampled=1`, `num_rejected=7` for control A,
candidate B, and control A. This is component parity, not endpoint acceptance
evidence.

## Timing gate

Each timing sample covers the complete seven-stage captured compute plus all
seven incumbent full-bias all-gathers. Each route used 20 alternating warmups,
nine A-B-A samples, and 100 complete cycles per sample. The conservative
control is the faster median of the two control legs; the minimum saving over
all changing routes is used independently on every card.

| Physical card | Worst route | Control median (us/cycle) | DPAS median (us/cycle) | Saved (ms/cycle) | Gate |
|---:|---|---:|---:|---:|---|
| 0 | `anchor_rank1` | 631.42552 | 651.67512 | -0.02024960 | FAIL |
| 1 | `anchor_rank1` | 631.21864 | 651.45571 | -0.02023707 | FAIL |
| 2 | `anchor_rank1` | 631.20802 | 651.44209 | -0.02023407 | FAIL |
| **3 (gate card)** | **`anchor_rank1`** | **631.20491** | **651.45862** | **-0.02025371** | **FAIL** |

The result misses the required saving by `0.17025371 ms/cycle`. The prior
single-call eager ceiling (`64.8715 -> 38.642 us`, or about `0.1836 ms` for
seven calls) does not survive the complete captured collective transaction.

## Item A+B disposition

Item B failed its mandatory standalone `>=0.15 ms/cycle` gate, so Phase 2 was
not run and the Item A flags were not enabled with Item B. Source/data-flow
review finds the components structurally compatible and non-overlapping:
Item A changes shared/routed MoE activation and quantization boundaries, while
Item B changes the later Markov W2 projection and its private persistent
buffers. That compatibility does not override the admission rule.

For context only—not a measured combined gate—the already-failed Item A floor
`0.49012080 ms/cycle` plus Item B's measured global floor
`-0.02025371 ms/cycle` is `0.46986709 ms/cycle`, also below the `0.50` bundle
threshold. Do not relabel this arithmetic screen as an A+B run.

## Evidence

- Harness:
  `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/bench-dspark-markov7-collective-w2-dpas.py`;
- full result:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-markov7-collective-w2-dpas-20260719T022300Z/summary.json`;
- diagnostic smoke and invalid whole-collective-capture attempts:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-markov7-collective-w2-dpas-smoke-20260719T000000Z`;
- real weights:
  `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/dspark-draft-pack-aa22cb0/model-00048-of-00048.safetensors`;
- fixed target-token oracle:
  `/mnt/fast-ai/deepseek-v4-corpora/mtp-reuse-m8-sequential-20260718T0440Z`.

## Recommendation

Preserve only. Do not enable Item B by default, do not run A+B or a model-load
B-A-B from this result, and do not submit it to LocalMaxxing.
