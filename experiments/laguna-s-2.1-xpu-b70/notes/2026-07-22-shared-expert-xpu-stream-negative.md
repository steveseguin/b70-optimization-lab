# Laguna exact M=8 shared-expert XPU stream negative

Date: 2026-07-22 America/Toronto

Classification: exact component result, decisive performance negative, stopped
before endpoint by the preregistered gate.

## Candidate and frozen identity

The candidate moved only Laguna target-verifier M=8 shared-expert work to one
process-wide XPU auxiliary stream. Shared gate, up, SiLU/multiply, down,
shared+routed addition, and the fixed-rank reduction retained incumbent
arithmetic.

- candidate vLLM commit:
  `3d1222281b3bcb44b60dee9899fbd3b498f84e5a`;
- unchanged XPU-kernel commit:
  `9525343e74b1a434b6af7d05583e1385a891c919`;
- preregistration:
  `notes/2026-07-22-shared-expert-xpu-stream-preregistration.md`;
- gate:
  `tools/gate_laguna_shared_expert_stream.py`; and
- focused static/unit validation before hardware: Ruff, `py_compile`,
  `git diff --check`, and `31 passed`.

Independent review tightened activation before source freeze: PP1 and
enforce-eager were explicit, all three projections had to be unquantized BF16
with exact shapes, the scheduler marker required one cached DFlash request with
seven drafts and exactly eight target rows, and incumbent/MK overlap conflicts
raised instead of silently changing treatment.

## Four-card gate

Each physical B70 was exposed alone with
`ONEAPI_DEVICE_SELECTOR=level_zero:*` and `ZE_AFFINITY_MASK=<card>`. Every card
ran 128 changing-input and changing-weight epochs, exact comparisons at gate,
up, SiLU/multiply, and down, the same checks for an independent main-stream
interference MLP, sustained timing submissions, and a post-timing race check.

| Card | Serial pair ms | Overlapped pair ms | Saved ms | Gain |
|---:|---:|---:|---:|---:|
| 0 | 0.371928825 | 0.411977550 | -0.040048725 | -10.7678% |
| 1 | 0.372046800 | 0.410971375 | -0.038924575 | -10.4623% |
| 2 | 0.400076675 | 0.440212025 | -0.040135350 | -10.0319% |
| 3 | 0.363405075 | 0.401006425 | -0.037601350 | -10.3470% |

The four-card means were 0.376864344 ms serialized and 0.416041844 ms
overlapped: -0.039177500 ms saved, or -10.4022%. Auxiliary fork/join execution
also cost about 0.031-0.032 ms more than the isolated main-stream shared MLP on
every card.

Correctness passed completely:

- 128/128 unique shared inputs, weights, and down outputs per card;
- 128/128 unique interference inputs and weights per card;
- all raw SHA-256 pairs equal;
- 1,032 `torch.equal` component checks per card, 4,128 total; and
- post-timing exactness passed on all four cards.

## Decision

The frozen gate required strictly positive median overlap on every card. All
four cards were negative by roughly 10%, so no endpoint service, realistic
suite, A/B leg, payload, or LocalMaxxing submission was permitted.

This rejects auxiliary-stream placement for the complete shared MLP on the
current oneDNN/XPU path. It does not reject arithmetic-preserving fusion inside
the shared MLP, but any such fusion is a separate experiment with its own
changing-input bitwise gate.

The failed implementation remains preserved in Git at `3d1222281`. It was
explicitly reverted by `f239a10144ea313746d48c2b4c920c1783133068`; the
post-revert source tree is byte-identical to pre-experiment vLLM
`d503073ec3573c6208cc2a06339815ec040ee984`.

## Raw evidence

Artifact directory:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/shared-expert-stream-gate-3d1222281-20260723T035830Z/
```

Raw JSON SHA-256:

```text
rank0.json d575a3cfeffb9b8ea4ee69157f5a26b67fe932c7606cfb82ff216ec69bfda927
rank1.json 3818c0dc842f0aa2a40e4128ccdd469a10d676ad3493640ba9dbbf65f3a48b5a
rank2.json 7429011201543d2b00d2245eae04f806acc48ab914aa0e0223a31d8f752aa204
rank3.json de8aa9a95fdc1ce90f50d5731c408d36b0b788d840f4d44ee5e3c7fbed2bf68a
```

The compact tracked summary is
`data/laguna-s-2.1-shared-expert-xpu-stream-negative-20260722.json`.
