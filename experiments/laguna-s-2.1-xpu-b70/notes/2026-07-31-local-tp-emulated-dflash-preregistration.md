# Local TP4-emulated Laguna DFlash body

Date: 2026-07-31 America/Toronto

Status: **preregistered before implementation or device execution**.

## Promoted baseline and required saving

The protected BF16-KV record is `125.4619731637751 tok/s` under the
conventional 99-interval metric. It is 13/13 token-and-text exact against the
canonical q1 target, cache-zero on all prompts, and uses target width 12,
DFlash depth 11, target topology `146/145`, and draft topology `14/13`:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-shared-elementwise-m12-formal-20260801T053000Z
```

That run emitted 6,354 tokens over 1,609 speculative cycles in 52.014017
post-TTFT seconds: `32.326922 ms/cycle`. Reaching 130 at unchanged acceptance
requires a true complete-cycle reduction of `1.128465 ms`. The component gate
is deliberately higher at **at least `1.4 ms/cycle` net**, measured at the
maximum-rank completion time.

No current-source draft-only timer exists. An older direct profile measured
roughly 8.55--9.01 ms/cycle in the drafter, and later draft graph treatments
removed about 4.62 ms from the complete cycle. The resulting roughly 4.07 ms
remaining-draft estimate crosses source revisions and is not a measurement.
It is only a scope bound motivating a fresh component test.

## New mechanism

The current six-layer DFlash body is TP4-sharded. Each speculative cycle has
13 eager BF16 reductions separating 14 captured compute segments:

- one shared vocabulary-embedding reduction;
- six attention-output reductions; and
- six MLP-down reductions.

Each reduction payload is only `[12,3072]` BF16 (73,728 bytes), so latency and
the graph boundary can dominate payload bandwidth. Capturing the copies before
these reductions was exact but neutral; local argmax retained a collective
round trip and regressed. Neither experiment removed the 12 decoder-body
reductions.

This treatment constructs the six DFlash decoder layers as full-head local
layers on every TP rank, but preserves the incumbent four-shard FP8 arithmetic
inside each projection:

1. load the full BF16 draft projection on every rank;
2. split it into the same four logical TP shards used by the incumbent;
3. quantize each shard independently with its original per-output scale rule;
4. evaluate all four shards locally;
5. reconstruct Q/K/V column outputs by component then rank order; and
6. combine O/down row partials locally in literal rank-0, rank-1, rank-2,
   rank-3 BF16 addition order.

The shared target/draft embedding remains sharded in phase 1. Therefore this
candidate removes 12 decoder-body collective boundaries while retaining one
embedding reduction. The expected draft topology is `2/1`, not `1/0`.
Replicating the shared embedding is explicitly outside this treatment because
the earlier embedding-only stack caused OOM/device loss and produced no score.

The auxiliary `fc` is already replicated and is unchanged. The target model,
target embedding/head objects, target collective topology and arithmetic,
BF16 KV type, width 12, depth 11, official DFlash checkpoint, sampling,
rejection, prompts, cache policy, and score window remain unchanged. The
selector is default-off.

Draft candidates must be deterministic across ranks. The design aims to match
the incumbent drafter bitwise, but target-model exactness is the quality
authority: speculative proposals remain verified by the unchanged canonical
target. No acceptance or throughput claim may be made from a component alone.

## Static memory ledger

The checkpoint contains 2,229,955,584 bytes of BF16 tensors. Current per-rank
FP8 projection weights and scales for the six decoder bodies use about
252.35 MiB; retaining all four logical shards locally uses about 1009.38 MiB,
an additional **757.04 MiB / 0.739 GiB per rank**. Full draft K/V geometry
increases the six-layer 8,192-token BF16 draft cache by approximately 151 MiB
per rank. Temporary BF16 loading/staging and graph allocations must be measured
and released before serving.

The final record reported 17.27 GiB model load, 3.58 GiB peak activations,
about 0.50 GiB non-Torch memory, 0.17 GiB graphs, and a 5.9 GiB KV reservation
on a 30.3 GiB device. The existing 114,051-token cache is far above the fixed
8,192-token single-request suite requirement. If a later live smoke is
authorized, `gpu_memory_utilization=0.82` is preregistered to reserve graph and
staging headroom. This changes cache capacity, not KV precision or benchmark
quality. Any OOM or device-lost error closes the treatment immediately.

## Gates and stop rules

1. Selector-off tests must prove byte-for-byte construction behavior and the
   promoted target path are unchanged.
2. CPU/static tests must prove the full shapes, TP shard order, Q/K/V
   reconstruction, O/down input slicing, literal BF16 rank-order addition,
   pointer non-aliasing, and exact memory accounting. Changed inputs and
   rollover-shaped iterations are required.
3. A one-layer one-B70 component must compare incumbent TP-shard arithmetic
   with local emulation using the same real draft weights. Raw outputs must be
   equal at QKV, attention output projection, gate/up, and down projection.
   It must also measure the complete six-layer proposal critical path or a
   mechanically faithful extrapolation using maximum-rank completion.
4. Continue only if the measured **net saving is at least 1.4 ms/cycle** after
   all extra shard compute, local reductions, attention/KV work, and graph
   replay overhead. A theoretical bandwidth estimate is not a pass.
5. Only after gates 1--4 may one bounded TP4 non-scored smoke run at the
   preregistered memory reserve. It must show two changing 400-token requests,
   q1-prefix exactness, cache zero, non-flat acceptance, cycle rollover,
   target `146/145`, draft `2/1`, per-rank proposal identity, and clean idle
   teardown.
6. One cold formal 13-prompt leg is authorized only after the smoke. Its first
   valid result stands. Promotion requires 13/13 token-and-text exactness,
   cache zero, topology on all ranks, clean teardown, and a conventional rate
   above `125.4619731637751 tok/s`. LocalMaxxing submission requires a verified
   matching record.

Do not capture collectives, weaken fixed-address/topology guards, use peer IPC
or a new custom collective, alter target arithmetic, lower precision, warm or
omit prompts, move work outside the scored window, select among repeated
starts, use `kill -9`, repeat after OOM/device loss, or perform any reboot,
reset, driver reload, unbind/rebind, or shared-memory cleanup as part of this
experiment. Hardware recovery requires a separate user decision.

## Historical separation

Repository-wide history confirms that full local TP emulation of the six-layer
DFlash body is new. Prior work covered replicated embedding only, local draft
argmax, segmented/captured copies, attention subgraphs, inline attention, a
separate FP8 draft LM head, and unsafe whole-drafter graph capture. None loaded
all four decoder projection shards locally or removed the 12 per-layer
reductions. A configuration-only `draft_tensor_parallel_size=1` is not a
shortcut: Laguna DFlash inherits the target TP4 parallel configuration.

## Offline implementation and component result: rejected

The default-off implementation is vLLM commit
`448351379b4ced80891725dc16a4b7f14cdb5663`. It constructs full 72-Q/8-KV
DFlash attention and full dense MLP geometry on each rank, retains four
independently quantized logical FP8 shards per projection, reconstructs fused
Q/K/V by component then rank, and performs O/down additions in literal BF16
rank order. The target constructors and selector-off path remain unchanged.

Offline gates passed:

- `74 passed` for DFlash model/workspace, selector, full-shape construction,
  shard-order, runtime reconstruction, and BF16 rank-order tests;
- `5 passed` for the 13-reduction incumbent and one-reduction local-TP4
  collective-state contracts;
- Ruff, Python compilation, and whitespace checks passed.

The real-weight one-B70 projection gate used the official checkpoint and the
record FP8 W8A16 kernel:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/components/
  laguna-dflash-local-tp4-projections-20260801T073600Z.json
```

All five projection families were raw-equal to an independent four-shard
reference. The maximum incumbent-rank projection body measured
`0.209433 ms/layer`; local TP4 measured `0.910882 ms/layer`. The extra local
projection cost is therefore `0.701449 ms/layer`, or **`4.208694 ms` over six
layers**, before counting additional full-head attention cost.

One bounded TP4 gate then timed the exact 12 `[12,3072]` BF16 reductions, with
each reduction synchronized and verified on all ranks:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/components/
  laguna-local-tp4-collective-gate-20260801T074100Z/summary.json
```

The maximum-rank median was only `1.239689 ms` for all 12 reductions
(`103.307 us/reduction`). To clear the preregistered `1.4 ms` net gate before
even paying the unmeasured extra attention cost, the removed collectives would
have needed to cost at least `4.208694 + 1.4 = 5.608694 ms`.

The candidate therefore misses the component gate by at least
`4.369005 ms/cycle`; it is **rejected before smoke or endpoint execution**.
No model service, prompt, score, OOM, device error, reset, or reboot occurred.
All four ranks verified and tore down cleanly. The promoted record remains
`125.4619731637751 tok/s` conventional.

Preserved source bundle:

```text
patches/laguna-s-2.1-xpu-b70/
  vllm-laguna-dflash-local-tp4-rejected-448351379-20260801.bundle
```

SHA-256:
`18317f6a824bd8f3dc788225462cc292f8e572292061c83a0945e8da854cea98`.

This closes full local replication of the six-layer draft body. The result
does not close mechanisms that reduce collective latency without multiplying
the draft projection work.
