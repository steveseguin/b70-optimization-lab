# Qwen3.8 MTP5/M6 Q64xK32 fresh two-GPU A-B-B-A r3 result

Date: 2026-08-21

Classification: **`q64k32-candidate-qualified-for-endpoint-campaign` — the
chunk-native Q64xK32 FlashAttention candidate is qualified on both GPUs.**

Preregistration:
[`2026-08-21-qwen38-mtp5-m6-fa-q64k32-abba-r3-prereg.md`](2026-08-21-qwen38-mtp5-m6-fa-q64k32-abba-r3-prereg.md)
(full adoption of the
[frozen operator contract](2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-prereg.md)).
Structured comparison:
[`../data/2026-08-21-qwen38-mtp5-m6-fa-q64k32-abba-r3-comparison.json`](../data/2026-08-21-qwen38-mtp5-m6-fa-q64k32-abba-r3-comparison.json)
(SHA-256 `e8b2d2e74c831db1fdc066a6df1ba227a6466ba14db7ac9a8470a2f8147644cb`).

## What ran

Pre-launch gates passed (clean `main == origin/main` at the prereg commit,
driver `check` PASS against the sealed r2 candidate manifest, no workloads,
quiet journal). The single `run` produced all **eight fresh packets** in
exact order — GPU2 A-B-B-A then GPU3 A-B-B-A — with exit 0, including GPU3's
complete four-arm sequence, which had never passed its first selector-off
control before today's recovery. Every arm passed correctness (eager and
captured-replay digest equality, CPU-oracle agreement, caller-owned poison,
bit stability), the four mutation gates, marker discipline, and the three
mapped-library proofs. Result root
`/home/steve/qwen38-mtp5-m6-fa-q64k32-abba-20260821-r3`: 16 files, all mode
`0444`, aggregate
`171556a9a651c815651cb86828cd748a8a0d5bcfee9cd4b445bd774d09c72d05`
(basename-sorted `sha256sum` recipe).

## Decision numbers (paired A-B-B-A bootstrap, 10,000 iterations, captured
graph replay, control-minus-candidate saving in us/call)

| KV | GPU2 central [95% CI] | GPU3 central [95% CI] |
|---:|---|---|
| 128 | `7.812` [7.749, 7.885] | `7.729` [7.682, 7.761] |
| 1024 | `58.883` [58.847, 58.953] | `58.954` [58.812, 59.150] |
| 1300 | **`74.676`** [74.603, 74.815] | **`74.964`** [74.866, 75.172] |
| 2048 | `115.705` [115.585, 115.784] | `115.597` [115.503, 115.711] |

Every frozen gate passed conjunctively on both GPUs: all long-KV lower
bounds are far above zero; KV128 shows a ~7.7-7.8 us/call **saving** against
a `+2.0 us/call` regression allowance; and the KV1300 central saving is
3.4x the `21.844 us/call` hurdle on each card. The recovered GPU3 matches
GPU2 within 0.4% at every shape — the policy's effect is uniform across
devices. At the production 16 full-attention calls per MTP5 target step this
is **about `1.195-1.199 ms` saved per target step at KV1300** (and
~1.85 ms at KV2048).

## Boundaries and next step

Per the frozen contract this qualifies the exact operator candidate only for
a **separately preregistered endpoint campaign** on the vLLM MTP5 lane. It is
not endpoint performance, target exactness, or promotion, and it does not
reopen any terminal determinism preregistration: the endpoint campaign must
carry the lane's full identity/quality gates and report exactness accounting
explicitly. The terminal r2 result root remains preserved and uncompared.
