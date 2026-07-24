# Laguna M8 actual-model gate: eager-contract abort

Date: 2026-07-24 America/Toronto

Status: sealed operational/configuration abort during target module
construction, before weight loading, target forward, generation, recorder
events, or any B/C arm. This is not a quality or performance result.

## Frozen identity

- approved record: LocalMaxxing `cmrx6p5dv001bo4017hb7sixz` at
  `33.89498511171744 tok/s`;
- corrected RPC gate tooling:
  `820d827a383e580eb0d6a9573d8b9a78bd5861d2`;
- v2 preregistration:
  `d984478b8`;
- reviewed recorder/segmented vLLM:
  `5c6c108bf152f985e126db9d77897ae442b75048`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- sealed run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-820d827a3-20260724T161333Z`.

The retained identity and arm logs have SHA-256 digests:

```text
66870dd0af475c1d4281f35bd92d1315db8b33a5be55670f0c6a2210ecb8b6d3  identity.txt
ef86b538ba43482bce2d0b3cd4d7882e9d7421f81ac03e732f1f9e3a0ba203e9  incumbent-eager/stdout.log
9306523892b2eb9ce9fc1da33c8bb761aa7d930db590d0d21bcf43b3370e1c67  incumbent-eager/stderr.log
```

The root and all three `m8p2-{a,b,c}` RPC bases are owner-readable and
non-writable and will never be reused.

## What happened

The full 118-file model-content verification passed. Global and incumbent
pre-arm strict idle checks passed. The new 100-byte AF_UNIX RPC identity also
worked: EngineCore and four TP4/EP4 worker processes started, and the retained
`m8p2-a` directory contains their short socket endpoints.

Each worker entered `load_model`, constructed the target module, and stopped
at the fail-closed shared-elementwise contract before loading checkpoint
weights:

```text
ValueError: VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1 requires the exact eager
Laguna M8 verifier record contract: target is not enforce-eager
```

The driver incorrectly set `enforce_eager=False` for all arms. That is a
material drift for A and B: the approved record was a true `dflash` eager
endpoint launched with `--enforce-eager`, no compilation config, `XPU_GRAPH=0`,
and `VLLM_XPU_ENABLE_XPU_GRAPH=0`.

The engine and all workers exited gracefully. The exact `/proc` reports before
the gate, before A, and after the failure are empty, and the strict post-arm
JSON XPU observer passed on devices 0-3. The driver created its empty private
evidence root before constructing `LLM`, but it contains no recorder event and
there is no `driver.json` or `analysis.json`. No target or draft forward and no
generation occurred. B and C did not run.

## Decision

Classify this root as
`operational_config_abort_during_model_construction_before_weights_or_generation`.
It says nothing about segmented eager/graph exactness or speed.

A and B must use the approved record's true eager identity. C must remain
non-eager with PIECEWISE Breakable capture. Because the record's
shared-elementwise selector and dispatch were intentionally proven eager-only,
simply flipping `enforce_eager` per arm is insufficient for a C arm that
retains the complete fusion stack.

Do not weaken C by silently disabling the fusion. Instead, any continuation
must add a separately committed, narrow graph-diagnostic contract that is
available only to the frozen `segmented-graph` raw-evidence arm, retains
compilation mode `NONE`, and leaves the existing production/eager selector
contract unchanged. It must receive source tests and independent audit before
the main gate can bind a new vLLM commit, fresh RPC names, and a third
preregistration.

The approved LocalMaxxing record remains unchanged.
