# MiniMax M2.7 Website Task Quality Probe

Date: 2026-05-21

Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`

Hardware/runtime: 4x Intel Arc Pro B70, vLLM XPU 0.20.1-local, TP4, dtype float16, INC AutoRound W4A16, max-num-batched-tokens 512, block size 256.

## Why

The previous MiniMax speed work showed a large gap between the fast PIECEWISE graph path and the safer `cudagraph_mode=NONE` path. Exact-repeat probes already showed correctness risk in the graph path. This run adds a more realistic task-level quality check: ask the model to build complete single-file websites and validate that it returns usable HTML/CSS/JS rather than high-speed garbage.

## Harness

Added `scripts/run-minimax-website-task-quality.py`.

The harness:

- Asks MiniMax for complete single-file websites.
- Applies the MiniMax chat template by default.
- Closes the template's `<think>` prefix before generation so the model emits final HTML rather than spending the full token budget on reasoning.
- Stops generation at `</html>` while keeping the stop string.
- Extracts HTML from fenced output or full documents.
- Validates required tags, task-specific regexes, complete `<html>/<body>` structure, inline CSS/JS, CSS brace balance, control characters, and JS syntax via `node --check`.
- Records raw output, extracted HTML, token hashes, finish reason, and tok/s.

Important harness lesson: raw-completion prompting was invalid for this model. Without the chat template, MiniMax mostly continued the prompt as training/test-fixture text. With the stock chat template left open at `<think>`, it spent 4096 tokens planning and did not emit final HTML. Both are invalid quality measurements.

## Results

### Safe path: `cudagraph_mode=NONE`

Command shape:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset LLM_SCALER_KERNELS
python scripts/run-minimax-website-task-quality.py \
  --mode cudagraph_none \
  --prompt-format chat \
  --max-model-len 6144 \
  --max-num-batched-tokens 512 \
  --max-tokens 4096
```

Observed:

- `benchmark_dashboard`: pass, 3267 generated tokens, 41.403 output tok/s.
- `pricing_calculator`: pass, 1971 generated tokens, 41.020 output tok/s.
- `task_tracker`: structurally/functionally complete but failed due control characters in CSS, 1918 generated tokens, 42.539 output tok/s.

The `task_tracker` failure is real output corruption, not validator noise. The model emitted control bytes where CSS should contain numeric zeroes, for example `margin-bottom: \x00.5rem` or `margin-bottom: \x01 0.5rem` variants across reruns. `node --check` passed for its JS and the HTML structure otherwise satisfied the task. Attempted `bad_words` control suppression exposed a vLLM 0.20.1 bad-words empty-token bug. Attempted `logit_bias` control suppression did not stop control-byte output on this XPU path.

### Fast graph path: `cudagraph_mode=PIECEWISE`

Command shape:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset LLM_SCALER_KERNELS
python scripts/run-minimax-website-task-quality.py \
  --mode graph \
  --prompt-format chat \
  --max-model-len 6144 \
  --max-num-batched-tokens 512 \
  --max-tokens 4096 \
  --task benchmark_dashboard \
  --task pricing_calculator
```

Observed:

- `benchmark_dashboard`: fail, 4096 generated tokens, 87.877 output tok/s. Invalid/truncated document with control characters, unbalanced CSS, and missing inline JS.
- `pricing_calculator`: fail, 2016 generated tokens, 95.324 output tok/s. Invalid CSS/JS, `node --check` failed, and required numeric parsing logic was missing.

This is an unacceptable quality result despite attractive decode speed. It confirms the graph path cannot currently be promoted for general task use.

## Conclusion

For real coding/task output, `cudagraph_mode=NONE` is the current honest baseline. It is much slower, around 40-42 output tok/s on these website tasks, but it can produce valid complete websites. The fast graph path is not acceptable under the current quality restriction.

The control-byte issue in safe mode is also important. It appears around CSS decimal values and may be tokenizer/sampler/backend related. Until fixed, strict quality gates should reject any generated control characters, and speed results should not be considered quality-clean if controls appear in output.

## Next

- Add a smaller deterministic CSS/control-byte canary, e.g. ask for repeated `margin-bottom: 0.5rem;` and verify no controls.
- Investigate whether XPU logit bias is ignored or applied too late in this backend.
- Test whether disabling async scheduling or changing sampler path affects control-byte emission in safe mode.
- Keep graph-mode speed results separate from quality-clean results unless task-level validators pass.
