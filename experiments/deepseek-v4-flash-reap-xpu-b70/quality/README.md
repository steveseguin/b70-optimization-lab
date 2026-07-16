# DeepSeek V4 REAP/XPU Quality Contract

The primary truth is a fixed subset of official-source teacher logits and task
results captured after the Stage 4 source download. Full unpruned IQ3_XXS is a
secondary all-expert behavior control; it is quantized and runtime-confounded,
so it is not source truth.

`spec-eval-contract-v1.json` is the separate anti-cheating contract for any
new speculative decoder or routing policy. It requires freeze-before-reveal
temporal holdouts, paired target/MTP1 controls, actual output-token-ID parity,
request-scoped acceptance economics, nonrepetitive short and long contexts,
and two independently generated packs. The repeatedly used public 12-prompt
suite remains useful for continuity, but cannot by itself promote deeper
speculation.

Use `../scripts/freeze-deepseek-spec-candidate.py` before materializing either
held-out pack. The helper hashes the candidate and both control identities,
all supplied patch/policy/draft artifacts, records the only allowed online
policy inputs, refuses overwrite, and creates a read-only manifest without a
holdout seed. Candidate changes after pack generation spend that pack.

`suite-v1.json` is frozen as a **prompt contract**, with prompt text/hashes,
categories, scoring-label placeholders, generation settings, tokenizer
revision, and critical-case labels. It is not yet an executable scoring suite:
the named rubrics, hidden tests, answer keys, scorer revision, request/chat
template, stop conditions, and aggregate pass policy still need a separate
versioned artifact. No intelligence or promotion decision may use v1 alone. Its
file SHA-256 is
`d0d825c3a4ea4a748864741d767afe1d2a2b375d5407aaec3ee76a8e8246d6e0`.
Do not change it after candidate results are visible; create a new version.

`calibration-v1-plan.json` freezes a materializable 8,000-prompt domain mix,
including dataset revisions, configs/splits, row IDs, text recipes, a
fail-closed deterministic sampler, the true-REAP metric, and nested-candidate
rules. The prior invalid request for 1,600 rows from the 164-row HumanEval set
was replaced by the 5,000-row APPS training split. The prompt JSONL and
observations remain to be materialized. Public 0xSero and sleepyeldrazi
mappings are comparison seeds, not final provenance.

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
