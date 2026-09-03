# MiniMax M2.7 Structured 94 tok/s Repro

> **Certification: `record-capsule`.** Preserves the exact result identity,
> evidence, and commands for audit; not an install guide.

This folder records the reproducible command for the MiniMax M2.7 constrained
HTML fast lane accepted on LocalMaxxing as `cmphg048s00mppc0192sahyug`.

## Result

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32 GB
- Engine: local vLLM/XPU `0.20.1-local`, TP4
- Quantization: INT4 AutoRound W4A16
- Context: `4096`
- Task: `skeleton_status_html`
- Constraint: regex2 structured HTML suffix with assistant scaffold/prefix
- Quality: `30/30` accepted, `0` rejects, `100%` first-attempt pass
- Decode: `94.406 tok/s` effective accepted output, `94.692 tok/s` post-first
- Payload: [../../data/localmaxxing-minimax-m27-autoround-structured-regex2-20260522.payload.json](../../data/localmaxxing-minimax-m27-autoround-structured-regex2-20260522.payload.json)
- Response: [../../data/localmaxxing-responses/minimax-m27-autoround-structured-regex2-20260522.response.json](../../data/localmaxxing-responses/minimax-m27-autoround-structured-regex2-20260522.response.json)
- Note: [../../notes/2026-05-22-minimax-structured-fast-lane-regex2.md](../../notes/2026-05-22-minimax-structured-fast-lane-regex2.md)

This is a constrained practical task, not an unconstrained website/chat result.
Rejected attempts are counted against effective throughput.

## Run

```bash
cd /home/steve/llm-optimizations
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset VLLM_XPU_CUDAGRAPH_PARTITION_COLLECTIVES || true
unset VLLM_XPU_CUDAGRAPH_STATIC_INPUT_COPY || true

out=/home/steve/bench-results/minimax-m2.7-quality-ramp/$(date -u +%Y%m%dT%H%M%SZ)-structured-regex2-repeat30
mkdir -p "$out"

timeout 35m /home/steve/.venvs/vllm-xpu/bin/python \
  scripts/run-minimax-structured-skeleton-quality.py \
  --mode graph \
  --warmup-runs 1 \
  --repeat 30 \
  --retry-until-pass 5 \
  --out "$out/result.json" \
  --sites-dir "$out/sites" \
  --max-tokens 96 \
  --max-model-len 4096 \
  --max-num-batched-tokens 512
```

Expected class:

- `passed=true`
- `accepted_outputs=30`
- `rejected_attempts=0`
- `effective_accepted_output_tok_s` around `94 tok/s` on matching hardware

## What Changed

The regex2 patch closed a structured-decoder loophole where the old regex could
permit apostrophe-only padding and force a retry. The compact public runner is
[../../scripts/run-minimax-structured-skeleton-quality.py](../../scripts/run-minimax-structured-skeleton-quality.py);
the historical patch artifact is
[../../patches/minimax-website-structured-regex2-20260522.patch](../../patches/minimax-website-structured-regex2-20260522.patch).
