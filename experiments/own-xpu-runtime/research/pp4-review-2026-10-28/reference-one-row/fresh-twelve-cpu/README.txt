Independent fresh twelve-task CPU teacher forcing — prepared, unexecuted model

The wrapper links the exact same four static archives as validated prefix178
binary 5eaee95ad1542cd521555d5465e81a7a8ec8fdbec3faf445793efe38991f5e22.
No archive/library rebuild. It moves only model/backend lifetime outside a loop
of 12 cases: each gets a fresh context and batch, followed by llama_free. The
original exact-logits.cpp context setup, batch256 construction, logits arithmetic,
argmax/top20 reporting, and scoring loop remain byte-identical except relocating
model/backend cleanup. No observers are compiled in. No model run has occurred.

Actual independent input authority is prepared ONLY after the GPU candidate's
one lifetime finishes all seven parity gates and 12 fresh generations cleanly.
The helper authenticates the fixed matrix prompts and original prompt file SHA,
then constructs original prompt + ACTUAL new output IDs, score_from=prompt length.
Every phase-b file must equal the completed GPU result. Historical continuations
or expected outputs are never substituted. Each input is bound by JSON and
packed LEi32 SHA. All actual output/EOS extents are validated before creation.

After root confirms no GPU owners and grants CPU-model admission:
  python3 research/pp4-review-2026-10-28/reference-one-row/fresh-twelve-cpu/run.py prepare --gpu-output GPU_OUTPUT --output FRESH_INPUT_ROOT
  python3 research/pp4-review-2026-10-28/reference-one-row/fresh-twelve-cpu/run.py run --inputs FRESH_INPUT_ROOT/inputs.json --output FRESH_MODEL_ROOT --preflight-only
  python3 research/pp4-review-2026-10-28/reference-one-row/fresh-twelve-cpu/run.py run --inputs FRESH_INPUT_ROOT/inputs.json --output FRESH_MODEL_ROOT

Model invocation is nice19, cores8–15, 8 threads, one model load, 12 fresh contexts;
GGML_CPU_EXACT_F64=1, EXACT_KV=f32, no EXACT capture or rounding overrides. Startup
requires >=80GiB MemAvailable, unchanged compiled/source/archive pins and exact
same model file identities as the qualified prefix178 CPU run. Root retains
GPU exclusivity authority; this helper does not launch/check/stop GPU services.
No automatic retry or new output directory reuse. Model/source/compiler identity
and full invocation are saved before the process starts.

Coverage: each generated token has exactly one scored row at consumed position
prompt_length-1+i, with exact next token from the authenticated actual input.
The original tool also emits the final row after consuming the last generated
token; retain it, but do not count its unconsumed next prediction as fidelity.
All rows preserve top20 logits/log probabilities and derive top1–top2 margins.
receipt.json records complete row provenance and explicit mismatches. Process /
coverage success is distinct from fidelity_all_match; disagreement is a finding,
not a reason to retry, change inputs or claim lifecycle failure. This does not
renew the historical5959/5965 score or claim free-running CPU output equality.

Small mocked-llama lifecycle tests exercise the actual wrapper control flow only;
they do not prove model arithmetic. A source-body test pins unchanged scoring.
The already qualified captureOFF path and pinned arithmetic libraries supply the
numerical provenance; no additional full-model neutrality run is proposed.
