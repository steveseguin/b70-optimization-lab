# Laguna width-12 target inline gathers: rejected by first smoke request

Date: 2026-07-31 America/Toronto

## Result

The default-off target inline-gather candidate is rejected. It is not a
throughput result and no scored leg was run.

The single preregistered non-scored smoke reached the intended graph topology
on all four ranks:

- target capture: 50 graphs / 49 eager breaks, 4/4 ranks;
- target replay: 50 graphs / 49 eager breaks, 4/4 ranks;
- draft capture: 14 graphs / 13 eager breaks, 4/4 ranks; and
- draft replay: 14 graphs / 13 eager breaks, 4/4 ranks.

The first 400-token request then failed the frozen q=1 prefix/cache gate. The
candidate was stopped immediately. There was no retry, scored suite, reported
token rate, device reset, driver action, shared-memory cleanup, or reboot.

## What is established

- The selector reached the live service and retired exactly the intended 96
  target eager gather boundaries.
- XPU graph construction and replay accepted the mixed design: the ordinary
  embedding all-reduce and all 48 attention calls remained eager while the 96
  gathers were recorded in surrounding graph segments.
- The resulting endpoint output did not satisfy the exact quality contract on
  request 0, so isolated changing-input gather evidence is insufficient to
  authorize the same primitives inside the full width-12 target graph.
- The smoke tool's combined response assertion did not persist its raw response
  before raising. Therefore this artifact cannot honestly localize the failure
  to token mismatch versus the cached-token field, nor name the first divergent
  token. The candidate is rejected either way; no narrower causal claim is
  made.
- Shutdown was clean: original status 1, stop status 0, worker status 0, idle
  status 0. The post-failure idle capture found only its own `xpu-smi` observer
  on devices 0-3.

The `EngineDeadError` at shutdown is not treated as a device failure. It was
logged after the harness intentionally sent SIGINT following the response-gate
failure; all four workers then logged normal shutdown completion.

## Identity

- run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-target-inline-gathers-smoke-ce2f3dfc0-20260731T0718Z`;
- vLLM worktree:
  `/home/steve/src/laguna-vllm-target-inline-gathers-20260731`;
- vLLM candidate commit:
  `ce2f3dfc02bce59095d8654d299c52b05c72d423`;
- vLLM base / incumbent commit:
  `34b43849fc7c8ff8633f223469cc2a0d525c256e`;
- XPU-kernel commit:
  `46a88e09d96fe06871c87a23de534fb47f1e039b`;
- source patch SHA-256:
  `e9af21c63f399ccace945077cf1fbef883f4e8cfbe3ec9cd412dc3233eae070e`;
- source bundle SHA-256:
  `231d391d4526e7816ba69e80d211aefb0df663699846d5211e50c659c1ee9ea7`;
- runtime-lock SHA-256:
  `792ed7a94f77881b72935f28470f6d2281b738d99c681eb09a0fc801ee6f1563`;
- grouped-GEMM SHA-256:
  `53f3d2941ce322bcdff1b0463ec6fe72387036ea54d3f602a08d690744b3459f`.

## Decision and reusable lesson

Do not rerun this selector or promote it. Keep it default-off and retain the
patch, bundle, run, and negative result.

Graph-safe component replay is compositional only when its dependency and
synchronization contract is also proved in the final graph composition. A raw
collective probe can prove transport contents for its own fixed inputs and
outputs; it does not prove that a full model graph supplies the same live
producer buffers, dependency edges, or request-varying state. Future boundary
retirement candidates need a changing-input component gate that mirrors the
actual surrounding producer and consumer segments, plus raw response
persistence before validation raises.

The verified incumbent remains `121.03724088473012 tok/s` under the historical
window (`119.82686847588282 tok/s` under conventional 99-interval accounting),
13/13 exact. This experiment does not change that record.
