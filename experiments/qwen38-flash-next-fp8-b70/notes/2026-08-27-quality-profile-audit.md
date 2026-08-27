# Flash-Next quality-profile audit

Date: 2026-08-27

## Finding

The existing `enable_thinking=false`, temperature-zero battery is a valid
deterministic direct-answer and runtime-parity profile, but it is not the
official recommended quality profile for Qwen3.8 Flash-Next. Qwen enables
thinking by default and recommends sampled generation:

- thinking: temperature 1.0, top-p 0.95, top-k 20, presence penalty 0;
- non-thinking: temperature 0.7, top-p 0.8, top-k 20, presence penalty 1.5.

The official vLLM deployment recipe also enables the `qwen3` reasoning parser.
These settings define a separate operating profile; they cannot replace or be
mixed with the captured deterministic non-thinking decode rows.

Sources:

- <https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8/blob/main/README.md>
- <https://recipes.vllm.ai/Qwen/Qwen3.8-Flash-Next>

The Hugging Face repository advanced from the downloaded
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce` revision to
`970c569adaca6b35532111fd6b27351b2baefe50` on 2026-08-27. The only changed
file is `README.md` (a corrected cloud URL plus dark-mode table CSS); no model,
tokenizer, template, configuration, or weight file changed. The sealed local
checkpoint therefore remains the correct execution artifact and does not need
a 185-GB refresh for this documentation-only head.

## Existing quality reclassification

The old seven-case helper required the literal lowercase string `yes` after a
prompt that asked only for "yes or no." The model returned `Yes`, which is
semantically correct. The helper now case-folds only that yes/no case while
retaining exact matching for copy, arithmetic, code, and other canaries.

Historical raw receipts are unchanged. They remain 5/7 under the old literal
grader and are 6/7 under the corrected semantic interpretation. The
`code_execution` output `30` for `sum(i * i for i in range(4))` remains the one
substantive miss; the correct value is `14`. MTP1, MTP2, and MTP3 reproduced
the exact MTP0 outputs under the same client identity, so the retained evidence
does not attribute either raw mismatch to speculative decoding.

## Next bounded arm

Use TP4/EP4, eager, MTP0, current source/runtime, configured maximum 4,352,
and `--reasoning-parser qwen3`. This is quality-only; run no timing rows.

1. Replay the sealed non-thinking suite and require 26/26 MTP0 parity, 16/16
   repeat stability, the exact 4K cache-zero needle, and zero cache reuse.
2. Run a target-only thinking scout at `reasoning_effort=xhigh` with the
   official thinking sampling parameters and a 1,024-token output cap. Start
   with code, logic, arithmetic, and copy.
3. Require separated nonempty reasoning and final content, `finish_reason=stop`,
   complete cache-zero usage, semantic `yes`, exact `14`, and exact controls.
   Stop on the first wrong response; classify an output-limit stop as
   inconclusive rather than wrong.
4. If the scout passes, run all seven cases at three frozen seeds and require
   21/21 semantically correct final answers.

Do not run a thinking-enabled 4,096-token needle at a 4,352-token maximum: it
does not leave the preregistered 1,024-token reasoning/output budget. The
existing non-thinking exact-4K needle remains the context-integrity evidence.
Any later thinking performance result must report reasoning tokens, final
tokens, TTFT, and final-answer latency separately and must not replace or lower
the captured non-thinking decode figures.
