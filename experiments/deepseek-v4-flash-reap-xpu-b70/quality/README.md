# DeepSeek V4 REAP/XPU Quality Contract

The primary truth is a fixed subset of official-source teacher logits and task
results captured after the Stage 4 source download. Full unpruned IQ3_XXS is a
secondary all-expert behavior control; it is quantized and runtime-confounded,
so it is not source truth.

Before Stage 4, commit `suite-v1.json` containing prompt text/hashes,
categories, scoring rules, generation settings, tokenizer revision, and
critical-case labels. Do not change it after candidate results are visible.

The frozen suite must cover:

- coding and debugging;
- math and multi-step reasoning;
- knowledge/research questions;
- tool calls and strict JSON schemas;
- instruction following and refusal behavior;
- the user's fixed practical canaries.

Promotion requires:

- zero critical failures on tool/JSON schemas and user canaries;
- at least 98% of the IQ3 normalized aggregate score when IQ3 is available;
- no loss greater than two absolute percentage points versus IQ3 on any scored
  coding, math/reasoning, or knowledge suite;
- no candidate-specific regression against the frozen official-source teacher
  cases beyond the committed logit/task tolerances;
- prompt, output, token, model, manifest, tokenizer, and runtime identities;
- identical greedy/equivalent decoding settings across candidates.

If official teacher evidence cannot be produced and IQ3 cannot run correctly,
the intelligence comparison is blocked. Uploader labels, qualitative needle
tests, or parameter counts cannot substitute for it.
