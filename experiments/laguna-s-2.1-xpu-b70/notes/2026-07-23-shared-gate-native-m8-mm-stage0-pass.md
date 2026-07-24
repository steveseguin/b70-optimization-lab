# Laguna shared-gate native M=8 MM stage-zero pass

Date: 2026-07-23 America/Toronto / 2026-07-24 UTC

## Outcome

The first and only tensor-bearing stage-zero campaign for the shared-gate
native-M8 treatment passed its frozen one-card exactness protocol.

This is intentionally narrow evidence. It proves the actual
checkpoint-selected `ColumnParallelLinear.forward` primitive on physical card
0, followed by the preregistered incumbent operations and simulated fixed-rank
downstream. It is not a full `LagunaMoE` endpoint, timing result, model
generation, record claim, or submission authorization.

The result authorizes construction, CPU validation, source freezing, and
independent review of four-card component tooling only. Component execution,
counters, endpoint work, model generation, payload construction, network use,
reboot, and LocalMaxxing submission remain unauthorized.

## Frozen lineage

- preregistration:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-native-m8-mm-preregistration.md`
- preregistration SHA-256:
  `fce4daed9cecc57febe1c81671b2bee24484a66dd4cee374dd573eb23947f852`
- stage-zero tooling commit:
  `155d647e480c45da9b8f198df9965c432c311650`
- authorization-only child commit:
  `bbcfb67ea462dbcfd976dfd33281a8e7735f87d6`
- authorization packet:
  `data/laguna-s-2.1-shared-gate-m8-stage0-authorization.json`
- authorization raw-file SHA-256:
  `f959416c19c0e2fa34834f2ea3cda7eb846f49c2fd38b2c0ae520834b9a02bdf`
- authorization canonical-JSON SHA-256 without its tracked newline:
  `2184e190408effa1440b7eef3502e81b178fbac4d2c21b400ce7f9debf61d819`
- vLLM commit:
  `3dae2ce383a009624bc6ff3e8660851fab5c12e0`
- XPU-kernel commit:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`

The authorization commit changed exactly the authorization packet and had the
tooling commit as its parent. The main, vLLM, and kernel worktrees were clean
before execution and remained clean after production analysis.

## Fixture and command

The fixture was generated before authorization under internal NVMe:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/shared-gate-m8-stage0-fixture-v5-155d647e4.json`

- file SHA-256:
  `d0ca468f33e1e53f1858ce5e712a611600b7238213108664ef6ec19c32ec58a8`
- manifest SHA-256:
  `29426d3de3cced389838b47557ff84e4ac9b564cf76ca5ac39d570f169a00ed3`
- ordered-epoch-hashes SHA-256:
  `e907c35d4726a8178abfa40c98bfe369ad4704c9a4540ff43a9e6458c377c851`

The exact authorized command was:

```bash
/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_mm_stage0.sh \
  --authorization /home/steve/llm-optimizations/data/laguna-s-2.1-shared-gate-m8-stage0-authorization.json \
  --fixture /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/shared-gate-m8-stage0-fixture-v5-155d647e4.json \
  --output-root /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-stage0-card0-155d647e4-20260724T005343Z
```

The runner exited zero. The result began at
`2026-07-24T01:00:12.769826Z` and completed at
`2026-07-24T01:00:41.358847Z`.

## Sealed evidence

Campaign root:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-stage0-card0-155d647e4-20260724T005343Z`

- `stage0-result.json` SHA-256:
  `8180b03fc05a0b519e49a04b9cae078829a33c708853883d7820bd9d1a016bd7`
- `pre-tensor-identity-checkpoint.json` SHA-256:
  `3f85d9f95838a9eec0f4a44b871565e5223f39f6f8e223cfc460656688424c92`
- `runtime-card0-binding-checkpoint.json` SHA-256:
  `21f729b6fa772ea869422fc938ab0634e816d6d04d84128b777797ee5a71652c`
- `tensor-work-started-checkpoint.json` SHA-256:
  `7788bd0b3ae59365e3730309690b132b62f32da8f557b8c961ffe14770b540b4`
- `dispatch-proof.json` SHA-256:
  `700bcd10e7d9342359e09c03e650e84b0a35291f47be0f957516db4ea4b4f8f2`
- `constructor-scope-proof.json` SHA-256:
  `196229c14d38588fdc00f0b49d59d63a0d1c65443c2c7f723ed35cf1eed8cda8`

The terminal result is `stage0_exactness_pass`, `passed=true`,
`terminal=true`, with all 128 epochs durable.

Every epoch passed raw little-endian BF16/`uint16` equality and
`torch.equal` for:

- the stride-zero BMM gate control versus native-M8 MM candidate;
- a deterministic candidate repeat;
- the unchanged incumbent up projection;
- exact SiLU/multiply;
- the unchanged incumbent down projection;
- shared-plus-routed addition; and
- simulated sequential fixed-rank reduction.

All 128 fixture epoch hashes were unique. The control and candidate hashes for
every recorded output boundary were also unique across all 128 epochs. Input
and weight hashes remained unchanged.

The actual-forward dispatch proof showed:

- marked shared-gate M=8: exactly one MM, zero BMM, zero fallback;
- unmarked M=8, marked M=1 through M=7, and prefill: incumbent BMM, no MM;
- bad noncontiguous input and weight layouts: the frozen `RuntimeError`
  class/message; and
- shared up/down, dense, draft, and unrelated linears unmarked.

The constructor proof bound the marker to
`model.layers.1.mlp.shared_expert.gate_proj` and used
`ForwardContext.additional_kwargs["xpu_exact_spec_verifier"]`.

## Production validation

The independent production analyzer command was:

```bash
PYTHONDONTWRITEBYTECODE=1 \
  /home/steve/.venvs/deepseek-v4-xpu/bin/python \
  experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_shared_gate_mm_stage0.py \
  --fixture /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/shared-gate-m8-stage0-fixture-v5-155d647e4.json \
  --authorization /home/steve/llm-optimizations/data/laguna-s-2.1-shared-gate-m8-stage0-authorization.json \
  --result /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-stage0-card0-155d647e4-20260724T005343Z/stage0-result.json
```

It returned exactly `stage0-valid`. A separate read-only agent reran the
production analyzer and independently classified the evidence as a pass for
the preregistered narrow scope, with the same full-model/timing limitation.

## Next boundary

Port the proven shared-gate exactness and dispatch contract into new
shared-gate-specific four-card component tools. Reuse only the generic
fail-closed structure from the shared-down component lane. The new tools must
be CPU-tested, independently audited, committed, and followed by a separate
tracked authorization-only commit before any other card or any timing command
is allowed.
