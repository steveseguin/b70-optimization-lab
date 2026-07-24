# Laguna separate shared gate+up native M=8 MM Stage-0 pass

Date: 2026-07-23 America/Toronto / 2026-07-24 UTC

## Outcome

The first and only authorized tensor-bearing Stage-0 campaign for the
separate shared gate+up native-M8 treatment passed its frozen one-card
exactness protocol. The production analyzer returned exactly `stage0-valid`.

This is narrow component-preparation evidence. It proves two separate,
role-bound native BF16 M=8 matrix multiplications, in gate-then-up order,
through the actual checkpoint-selected `LagunaMLP.forward` path on physical
card 0. It is not a merged gate/up operation, timing result, four-card
component result, model generation, endpoint result, record claim, or
LocalMaxxing submission authorization.

The pass authorizes construction, CPU validation, source freezing, and
independent audit of pair-specific four-card component tooling only.
Component execution, timing, other-card work, counters, model generation,
network use, payload construction, reboot, and submission remain
unauthorized until a separate packet-only commit freezes the new toolchain.

## Frozen lineage

- runtime-guard reaffirmation:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-up-runtime-guard-fix-and-reaffirmation.md`
- reaffirmation SHA-256:
  `20ec56aeec8f8f0a1843cfa430ca118e7be9c6f97977e6b8b80d2beba45e194f`
- Stage-0 tooling commit:
  `79577851f76f078d3150a8300bad670670b4d48c`
- authorization-only child commit:
  `8bb2af9ef2657aa17687bf323f310a2efaf6c902`
- authorization packet:
  `data/laguna-s-2.1-shared-gate-up-m8-stage0-authorization.json`
- authorization raw-file SHA-256:
  `550ca03817f81d74233e3a89a874e9ef36e0f81a64fdd345f78265b9a90ff00e`
- authorization canonical-JSON digest without the tracked newline:
  `670cd0c7212708c8a7974a9f37e60dc09b67ca475af05eee039d029551f2bacd`
- vLLM commit:
  `503f7784cf9d1704109b1e4650427fb4f417d604`
- XPU-kernel commit:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`

The authorization commit changed exactly the packet and has the tooling
commit as its parent. Main, vLLM, and kernel worktrees were clean for
execution and production analysis. The boot remained
`0b7f98a5-e50a-46a5-81ea-15938b55317a`.

## Fixture and authorized command

The canonical fixture is on internal NVMe:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/shared-gate-up-m8-stage0-fixture-v1-79577851f.json
```

- file SHA-256:
  `c47d3f7e0fef29dd483fb1397ca4d36a93a923c7d6a9af18859023d98de7618c`
- manifest SHA-256:
  `87e40cc2367ebc44df5620f27861a0b2d87d2c5a3a8bbd28e28a51784e7b5300`
- ordered-epoch-hashes SHA-256:
  `e907c35d4726a8178abfa40c98bfe369ad4704c9a4540ff43a9e6458c377c851`

The exact authorized command was:

```bash
/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_up_mm_stage0.sh \
  --authorization /home/steve/llm-optimizations/data/laguna-s-2.1-shared-gate-up-m8-stage0-authorization.json \
  --fixture /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/shared-gate-up-m8-stage0-fixture-v1-79577851f.json \
  --output-root /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-up-m8-stage0-card0-79577851f-v1
```

It exited zero. The result began at `2026-07-24T04:41:46.514405Z` and
completed at `2026-07-24T04:42:16.864499Z`.

## Sealed evidence

Campaign root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-up-m8-stage0-card0-79577851f-v1
```

- `stage0-result.json`:
  `726bfa5b19dd6e8722aedda0679603d9cc43214acb1952b07c15dc9562b558b0`
- `pre-tensor-identity-checkpoint.json`:
  `335ccb1f1663a96ac95ab499986fef53319f77869d9eb5a65b53e3d44aad8b4c`
- `tensor-work-started-checkpoint.json`:
  `d1db2b1724bcdc7b8db6f3aad49372ea44da3412ee6ac66103e8895ee482ca62`
- `runtime-card0-binding-checkpoint.json`:
  `8589a4bf0747075b7c51c7127bdf8225ec6ffed3df865f23fc4919cbee819d22`
- `constructor-scope-proof.json`:
  `27a1398ef501a9e2f5dc643f2732aae62f51c175ef3f5e7b47ebe3eaa78706e4`
- `dispatch-proof.json`:
  `0f76865d0c38a06ae521671c47acf93dd52c6062b79a238907beaa6ec7537f0a`

The terminal result is `stage0_exactness_pass`, with all 128 epochs durable.
All 1,152 declared comparisons passed both raw little-endian BF16/`uint16`
equality and `torch.equal`. Every one of the 16 output labels had 128 unique
raw and canonical hashes. Inputs and all three projection weights remained
immutable across host copy, transfer, and execution.

The exact boundaries were:

- gate BMM control versus native-MM candidate and candidate repeat;
- up BMM control versus native-MM candidate and candidate repeat;
- gate SiLU;
- BF16 SiLU-gate times up;
- shared down projection;
- shared-plus-routed add; and
- three-peer sequential fixed-rank reduction.

The actual-forward dispatch proof recorded exactly two native MMs, one for
gate and one for up, in that order. Across the full proof it recorded 2 MM,
22 incumbent BMM, and 0 fallback calls. The 22 incumbent cases cover
unmarked M8, marked M1-M7, prefill, dense, draft, routed, and shared-down
paths. All 30 named layout, marker, pair-scope, peer, selector, and
record-stack corruptions raised the frozen `RuntimeError` before any MM, BMM,
or fallback primitive.

The constructor proof binds only:

- `model.layers.1.mlp.shared_expert.gate_proj`; and
- `model.layers.1.mlp.shared_expert.up_proj`.

Shared down, dense, draft, and routed representatives remain unmarked. The
runtime bound one visible XPU to physical card 0, DRM `/dev/dri/card3`, BDF
`0000:23:00.0`, and the frozen B70 UUID.

## Production validation

The independent production command was:

```bash
PYTHONDONTWRITEBYTECODE=1 \
  /home/steve/.venvs/deepseek-v4-xpu/bin/python \
  experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_shared_gate_up_mm_stage0.py \
  --fixture /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/shared-gate-up-m8-stage0-fixture-v1-79577851f.json \
  --authorization /home/steve/llm-optimizations/data/laguna-s-2.1-shared-gate-up-m8-stage0-authorization.json \
  --result /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-up-m8-stage0-card0-79577851f-v1/stage0-result.json
```

It returned exactly `stage0-valid`. Before authorization, independent audits
also caught and closed two evidence weaknesses: dispatch records now bind
both input and output width, including shared down `256 -> 3072`, and an
identical raw tensor with a forged `torch_equal=false` can no longer be
classified as a proven raw mismatch. The final CPU-only tool suite passed
85/85.

## Next boundary

Construct new pair-specific four-card component tools from the corrected
shared-gate component structure. The frozen treatment remains two separate
gate-then-up MMs—no N=512 merge, logical-B16 packing, fusion, reordering,
overlap, or shared-down treatment.

Each card must independently pass 128 pre-timing and 32 post-timing changing
exactness epochs, at least 28 of 31 A-B-B-A blocks, and at least `0.20 ms`
median saving per complete 47-layer gate+up cycle. The component toolchain
must be CPU-tested, independently audited, committed, and followed by its
own authorization-only child commit before any component execution.
