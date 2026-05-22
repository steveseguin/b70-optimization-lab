# MiniMax M2.7 Structured Fast Lane Regex2

## Summary

The 4x B70 MiniMax AutoRound fast graph lane is restored above 90 tok/s for a
quality-gated practical task.

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Engine: local vLLM/XPU, TP4, llm-scaler INT4 MoE path, forced XPU graph with
  communicator capture no-op
- Task: `skeleton_status_html`
- Prompt mode: chat + `skeleton_open` assistant prefill
- Decode constraint: structured suffix regex
- Context: `max_model_len=4096`, `max_num_batched_tokens=512`,
  prefix caching enabled

## Results

Control before the regex2 patch:

- Path:
  `/home/steve/bench-results/minimax-m2.7-quality-ramp/20260522T211236Z-control-promoted-structured-skeleton-repeat30/result.json`
- Result: `30/30` accepted, but `1` rejected first attempt.
- Effective accepted output: `89.563 tok/s`.
- Accepted-output mean decode: `94.544 tok/s`.
- Failure cause: the structured regex allowed apostrophe-only chunks, producing
  a quote loop that hit `finish_reason=length` before the fixed HTML suffix.

Regex2 result:

- Path:
  `/home/steve/bench-results/minimax-m2.7-quality-ramp/20260522T212009Z-promoted-structured-skeleton-regex2-repeat30/result.json`
- Result: `30/30` accepted, `0` rejects, `100%` first-attempt pass rate.
- Effective accepted output: `94.406 tok/s`.
- Post-first effective accepted output: `94.692 tok/s`.
- Accepted-output mean decode: `94.429 tok/s`.

Structured JSON cross-check:

- Path:
  `/home/steve/bench-results/minimax-m2.7-quality-ramp/20260522T211629Z-control-promoted-structured-json-repeat3/result.json`
- Result: `9/9` accepted, `0` rejects.
- Effective accepted output: `87.956 tok/s`.
- Total tokens counting prompt per candidate: `215.633 tok/s`.
- Parsed JSON hashes were stable for all three validation tasks; one task had a
  harmless token-hash difference with identical parsed JSON.

## Patch

Changed the structured HTML suffix regex in
`scripts/run-minimax-website-task-quality.py` so generated paragraph chunks must
start with an alphanumeric character and cannot be apostrophe-only padding.

Patch record:
`patches/minimax-website-structured-regex2-20260522.patch`

The full updated harness remains in the active lab checkout at
`/home/steve/llm-optimizations-publish/scripts/run-minimax-website-task-quality.py`.
For a fresh checkout, apply the patch above to the website-quality harness after
bringing over the current local harness version.

## Repro Command

```bash
source /home/steve/llm-optimizations-publish/repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset VLLM_XPU_CUDAGRAPH_PARTITION_COLLECTIVES || true
unset VLLM_XPU_CUDAGRAPH_STATIC_INPUT_COPY || true
out=/home/steve/bench-results/minimax-m2.7-quality-ramp/$(date -u +%Y%m%dT%H%M%SZ)-promoted-structured-skeleton-regex2-repeat30
mkdir -p "$out"
timeout 35m /home/steve/.venvs/vllm-xpu/bin/python \
  /home/steve/llm-optimizations-publish/scripts/run-minimax-website-task-quality.py \
  --mode graph \
  --prompt-format chat \
  --assistant-prefill skeleton_open \
  --task skeleton_status_html \
  --warmup-runs 1 \
  --repeat 30 \
  --retry-until-pass 5 \
  --out "$out/result.json" \
  --sites-dir "$out/sites" \
  --max-tokens 96 \
  --max-model-len 4096 \
  --max-num-batched-tokens 512 \
  --enable-prefix-caching \
  --structured-skeleton-regex
```

## Interpretation

This is a quality-preserving fast lane for constrained, simple HTML generation.
It does not claim unconstrained free-form website generation is clean on the
forced XPU graph path. The broader graph corruption issue still exists for
unconstrained outputs; this patch closes one structured-decoder loophole and
keeps invalid candidates out of the promoted path.
