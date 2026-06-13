# Qwen3.6 Forward Bottleneck Decision 20260613m

This is a decision artifact, not a new speed benchmark.

## Target Gap

- Current clean c1 decode: `100.863 tok/s` (`9.914 ms/token`).
- Target: `200.0 tok/s` (`5.000 ms/token`).
- Required saving: `4.914 ms/token` (`49.57%`).

## Decision

- Primary bottleneck: `model_forward_or_forward_stream_dependencies`.
- Next implementation target: `route-signature overlay plus persistent one-dispatch MoE layerlet prototype`.
- Backup target: `oracle k=1 verifier/KV repair for exact multi-token acceptance`.

Deprioritized as lead levers:
- HTTP/SSE/frontdoor/response packaging for c1 decode.
- detokenization-only changes as a 2x lever.
- static lm-head/logits restriction before timing proves it matters.
- physical-card-only topology tuning as the lead hypothesis.

## Evidence

- Tail check: stream client vs vLLM decode differs by `0.018%`; queue is `0.0124-0.0155 ms`.
- Forward boundary: start sync mean is `0.001595 ms`, while forward-end wait mean is `4.569 ms`.
- Rank reversal: TP0 stayed fastest after moving to physical card `3`; rank spread remained `0.346 ms`.
- Presampler split: forward-end sync mean is `3.674 ms`; forward-start sync mean is `0.002019 ms`.
- Worker labels: model-forward mean range is `4.217-5.766 ms`; GDN attention mean range is `1.384-1.541 ms`.
- Gemma dashboard source check: latest tracked snapshot has `354` rows and the same `470.526 tok/s` top method `mao-gemma-fast-lf29pc-v1`; use it only for methodology transfer.

## Next Steps

- Add rank/layer route-signature overlay to the all-rank forward-boundary probe.
- Split model-forward timing by layer family on slow ranks: attention, router, expert gather, expert GEMM, combine, collectives.
- Prototype a persistent or route-class one-dispatch MoE layerlet only after the route overlay identifies stable hot classes.
- Keep output-tail and lm-head experiments as secondary until the new layer-family trace shows they are material.
