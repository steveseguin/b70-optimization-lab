# Shared-gate component timing-helper abort

Date: 2026-07-23 EDT / 2026-07-24 UTC

## Classification

- Outcome: rank-0 timing-setup tooling abort; no valid component timing
  measurement.
- Authorization packet:
  `data/laguna-s-2.1-shared-gate-m8-component-authorization-20260724T024800Z.json`
- Packet SHA-256:
  `a0d3cb2b05e12723909803593f6e9f6ea1b9ea633c9c98abe7c27ac4ca64dc22`
- Authorization commit: `b6a3e6b7d650ba2712b5da2023f939f0194a6d3c`
- Tools commit: `a694c7ca8d5ab6a51e7044e022ed6943d2b0735d`
- Artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-component-a694c7ca8-20260724T024800Z`
- Failure:
  `AttributeError: module 'gate_laguna_shared_gate_mm_stage0' has no attribute '_raw_equal'`
- Failure classification: `runtime_or_infrastructure` in
  `isolated_component_timing`.
- Timing evidence: absent (`timing=null`).
- Post-timing exactness: absent (`post_exactness=[]`).
- Cards 1 through 3: not started.
- Analyzer and counters: not started.
- Every downstream authorization remained false, including model generation,
  endpoint, service, network, payload, reboot, and submission.

This packet and artifact root are terminal and must not be reused.

## Exact work completed before the tooling abort

Rank 0 passed the sealed physical-device discovery, Torch/runtime card binding,
real-model constructor scope, and dispatch proof. The dispatch proof observed
the marked M=8 gate on exactly one `torch.mm` call with zero `torch.bmm` or
fallback calls; its raw BF16 output matched the literal reference. The M=1
through M=7, unmarked M=8, and marked prefill controls stayed on `torch.bmm`.

All 128 distinct pre-timing epochs, numbered 0 through 127, were durably
written. Every comparison in every epoch reported both
`raw_uint16_equal=true` and `torch_equal=true`. These checks establish
pre-timing exactness only; they do not turn this aborted packet into a
performance result.

## Preserved campaign evidence

- `campaign-start-checkpoint.json`:
  `05962f3694ce15c9466be83ef8b2137d1ecce28490508f03efa351af20fb9518`
- `card0/pre-tensor-identity-checkpoint.json`:
  `bb87afe85c5497c08af54563da9321e37b90fca56179b9e19d3742bd44d281a9`
- `card0/tensor-work-started-checkpoint.json`:
  `cbdd4c71d965d73613b30be34f1324fc7ebb76b5500db6f8dc283a0d8744c92e`
- `card0/runtime-card-binding-checkpoint.json`:
  `0d8faf32bce8931e78a1fb4cbe3692bd689a19edc35fa5dc8b46eb82784fafa4`
- `card0/constructor-scope-proof.json`:
  `d94413d5b685273381e55e3dfa7b2dfcae7c917af6d6757b805e8c6c39c6503c`
- `card0/dispatch-proof.json`:
  `0632a461fc45e04baad509365ffa2a8269b70e66e2eb7fa6a1741e84f8c311cb`
- `card0/component-result.json`:
  `bfe38d808daaf62d97013dd24e7173ce5c2adaa99ab9f4f029765ed15f3ad0e8`
- `rank-0-terminal.json`:
  `db74f77022ab942ad08be6b51dec148ecdf9d5b7a962c47e72150106f5093fa4`
- `campaign-terminal.json`:
  `d530a0428cc2f1bbb1406c826506cf0057cb0c25caaf6b1ddb4a04842981b617`

## Root cause and correction

The component runner imports the Stage-0 contract module as `stage0`, while the
private raw-BF16 comparison helper belongs to the Stage-0 runner module. The
timing preflight called `stage0._raw_equal` three times and therefore stopped
before warm-up or measurement. Other component helpers already use the local
alias `actual` for the Stage-0 runner.

The minimal correction imports `run_laguna_shared_gate_mm_stage0 as actual`
inside `_timing` and routes all three outside-timing equality checks through
`actual._raw_equal`. A CPU-only AST regression pins the import target and all
three call sites, and also verifies that the referenced helper is callable.
After full regression and independent review, only a new tools commit,
authorization packet, and NVMe campaign root may be used.
