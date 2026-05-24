# MiniMax Speed Recovery Quality Plan

Date: 2026-05-23

Goal: recover some of the older 89-93 tok/s behavior without accepting any
quality regression and without changing target weights, KV dtype, sampling, or
served 32K context defaults.

## Rules

- Same model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`.
- Same quantization: INT4 AutoRound W4A16 target weights.
- Same production KV dtype: `auto`/FP16-family baseline, not FP8/TurboQuant.
- Same user-facing serving default: `max_model_len=32768`.
- No speculative decoding unless explicitly labeled as a separate experiment.
- No expert dropping, router approximation, sampling relaxation, or power-limit
  change.
- Quality gates run before any speed result is promoted.

## Required Gates

Minimum gate before considering a runtime/graph candidate:

- raw145 n64 exact token hash
- raw145 n256 exact token hash
- semantic suite n64, two repeats
- arithmetic repeat
- no NUL/control-token regression
- one practical structured-output task if the candidate touches graph replay,
  logits, sampler, or attention/KV behavior

For anything that claims to recover 90+ tok/s:

- add a longer generated-output repeat or practical task repeat
- compare against the current OpenAI-compatible 32K endpoint measurement script
- record cold versus warm behavior separately

## Candidate Order

1. Reproduce current baseline with the endpoint metrics script.
2. Recheck known-good current 2K strict lane only if the server-side endpoint
   numbers look inconsistent.
3. Review the older 93-class graph path and identify the exact delta from the
   current 84 tok/s serving recipe.
4. Reintroduce one runtime/graph flag at a time.
5. Stop immediately on exact-token mismatch, NUL/control output, HTTP 500, or
   XPU device loss.

## Current Safe Measurement Tool

Use:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:8000 \
  --prompt-tokens 510 \
  --output-tokens 1536 \
  --repeats 1 \
  --out /mnt/fast-ai/bench-results/minimax-m27-b70-serve/endpoint-metrics-$(date -u +%Y%m%dT%H%M%SZ).json
```

The script records client-side streamed TTFT, vLLM Prometheus TTFT/e2e deltas,
generated-token-only throughput after first streamed chunk, total throughput,
VRAM snapshots, and a conservative prefill lower-bound.

## First Endpoint Measurement

Artifact:

`data/minimax-m27-openai-endpoint-metrics-32k-20260524.json`

Live 32K endpoint, p510/n1536, one warmup request excluded:

- Generated-token-only throughput after first streamed chunk: `85.453` tok/s.
- Total client throughput: `111.635` tok/s.
- Client TTFT: `352.786 ms`.
- vLLM Prometheus TTFT: `351.068 ms`.
- vLLM e2e request latency: `18.326 s`.
- Conservative prefill lower-bound from TTFT: `1445.634 tok/s`.
- vLLM metric deltas: `510` prompt tokens, `1536` generation tokens.
- Observed VRAM: about `32655.95 MiB` peak per B70 during the request.

The prefill value is deliberately labeled as a lower-bound because the endpoint
does not expose a separate prefill-complete timestamp. It is computed as prompt
tokens divided by TTFT, so it includes queue/scheduler and first-token overhead.

Prepared LocalMaxxing payload:

`data/localmaxxing-minimax-m27-autoround-openai-32k-endpoint-metrics-20260524.payload.json`

Submission attempts returned HTTP 502, so this follow-up is not yet submitted.
