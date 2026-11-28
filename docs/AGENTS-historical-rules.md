# Historical & Lane-Specific Agent Rules (Archived from `AGENTS.md`)

Verbatim rules and lane-specific notes archived from [`AGENTS.md`](../AGENTS.md) on 2026-11-27 to keep
the active agent contract concise and unambiguous. All historical decisions, realistic-suite submission
specifications, public-page style guides, and Qwen/MiniMax lane notes remain binding for their respective lanes.

---

### Reusable engine direction (2026-10-25)

The owner wants the complete inference engine and recipe published on GitHub
and neural.download, with current links/details on skindeep.ai. Preserve the
engine as a reusable foundation for other quants, Qwen-like model variants and
1/2/4/6 B70 configurations; possible future DeepSeek 4 Flash support is a
separate architecture extension. Optimize the current SC117 model on two and
four cards without deleting existing kernels or baking its dimensions, quant
label or placement into new general interfaces. Keep model description,
per-tensor quantization, topology and measured tuning profiles separate.
The owner explicitly authorized using all four cards in this session, including
gracefully freeing the vision cards and incident-reviewed resumption. This does
not authorize reboots, driver resets, power/memory-setting changes or retries
after new faults. Publication must retain the distinction between internal
GPU parity and the six unresolved independent-reference disagreements.
See [the review and release direction](sc117-engine-review.md).

October 25 follow-up: the owner explicitly prohibits draft-model training.
Continue quad overlap, reference-discrepancy diagnosis and portable recipes using
the existing draft weights. Do not install or initiate a training pipeline.

These come directly from the owner and override anything else in this file,
any older note, and any recipe.

### Optimization focus discipline (owner, 2026-10-25)

Keep kernel/performance work on the main path: measure the bottleneck, reuse
existing harnesses, run one meaningful correctness gate then full fair timing.
Do not let serial archival, repeated reviews/proof scaffolding, publication or
extracted builds displace speed tests; recheck only for changed risk or unresolved
failure. Delegate necessary routine records/reviews to GPT-6.1-Sol without blocking
optimization, retain terse results, and close small levers quickly when material
ones remain. Keep a 15-minute performance_focus monitor during active work.
Read actual planner floors and use fresh exclusive output paths before planning;
never invent a cause for an unexplained loading stop. Reusable abstractions must
serve concrete optimization/onboarding needs. No training or power/memory changes.
Memory: `/home/steve/identified-mistakes/2026-10-25-sc117-focus-discipline.md`.


---

## Quality Rules: No Cheating

Never promote a speed or context result unless quality is labeled and tested.

Use exact-token, semantic, arithmetic, and practical task gates where relevant.
Compressed KV modes such as FP8 KV or TurboQuant must be labeled separately
from the FP16-family baseline.

For Gemma/Qwen speculative-decoding results, diagnostic sweeps may use
synthetic or repetitive prompts, but promotion and LocalMaxxing submissions now
require the fixed realistic final gate:

- use the fixed realistic prompt suite;
- require its declared varied classes (at minimum prose, code, analysis,
  operations, and documentation/structured writing); repeated variants of one
  easy prompt shape are not representative;
- run each prompt once as a cold first response;
- require `cached_tokens=0` for every request;
- disable prompt/KV cache reuse, context checkpoints, response reuse,
  n-gram/history acceleration, and warmed repeated prompts;
- keep the target model and quantization unchanged;
- allow speculative decoding/MTP only when accepted tokens are verified by the
  declared target model;
- report the median within each input class and then the median across those
  class medians, using the conventional rate across the 99 inter-token
  intervals between generated-token timestamps 1 and 100 after TTFT, as the
  primary metric; retain the all-prompt median as a secondary diagnostic; also
  report p10, mean, TTFT, wall tok/s,
  full-natural-completion tok/s under the fixed 512-token response cap,
  prompt/output hashes, model identity, runtime commit, env vars, flags, and
  logs. Record the event count, interval count, numerator, and endpoints;
  historical 100-event/99-interval compatibility fields must be labeled.

“Cold response” does not require reloading model weights for every prompt. A
loaded model, resident weights, initialized runtime, and compiled kernels are
valid steady-state conditions. It does require that every fixed prompt is used
once per suite attempt, reports `cached_tokens=0`, and cannot benefit from
prompt/KV/response reuse, a learned draft, repeated-prompt n-grams, or a
selected high-acceptance fixture. Run the complete varied suite; a `--prompt-id`
subset or a response cap below 512 is screening evidence and must make
`realistic_final_gate.passed=false`.

Performance and quality are independent promotion gates. The optimized path
must pass the model lane's registered exact-output or quality oracle and its
repeat/fresh-server determinism requirement. Speculative accepted tokens must
be verified by the unchanged declared target. A speed result cannot substitute
for those checks, and a quality pass cannot upgrade a diagnostic workload into
a performance headline.

Before building an external submission, require a hash-bound
`neural.download.promotion-attestation.v1` artifact linking the exact
performance JSON to in-repository quality evidence, model/runtime/optimization
identity, target-oracle parity, deterministic repeats, a fresh-server repeat,
an unchanged verifier, and an explicit no-quality-loss decision. A stored
benchmark `passed` boolean is never sufficient by itself.

The current best result, its exact configuration and its superseded
predecessors live in each lane's result packet and in `results/scoreboard.md`,
not in this file. (The long Gemma 4 26B Q8 record that used to sit here is in
`results/gemma4-26b-a4b-q8-b70/README.md`.) Never promote a lower-precision,
QAT or side-lane result as a higher-precision lane's headline.

## Human-readable public results (2026-09-13)

Always report **prefill (reading the prompt)** alongside decode (writing the
answer) on neural.download: a main-table column and a short section on model
details pages. Use measured 512-token, one-user prefill rates where available;
state the input length and timing definition. Show “not measured” for missing
results. Never borrow a rate from another card count, quantization, runtime or
draft setting, or turn a diagnostic optimization into a promoted speed claim.

Write the main page and model details for a reader with no lab background,
including a ten-year-old: short sentences, familiar words, and only information
needed to understand the model, choose a setup, and read its speeds. Explain
prefill, decode, units and graph axes in plain language. Graph titles must say
what is measured; internal experiment IDs such as R187 are not public labels.
Keep captions brief and preserve meaningful differences between test setups.
Put commands, experiment history, detailed methods, logs and full evidence in
GitHub files linked as “Setup guide” or “Test details”, rather than copying
walls of technical text into public pages. Keep exact points and accessible
value tables; simplicity never permits invented or misleading measurements.

## External Projections (ML Bottleneck bridge)

`learn/assets/mlbottleneck-bridge.js` loads the ML Bottleneck physics engine
(https://mlbottleneck.com/, same author) at page load and renders projections
next to lab measurements: the landing page's "How much faster could these
get?" headroom cards and Intel mini-planner, and the Hardware guide's projected
cross-card comparison. Those numbers are model projections, never lab
measurements: keep them in their labeled sections, never copy one into a
benchmark table, result packet, README, or LocalMaxxing submission, and keep
the "projected, not measured" wording. The measured rows feed the bridge through
`data-ml-*` attributes on `<tr>` elements (model preset key, quant label,
runtime, card count, speed-up); the measured tok/s is read from the row's own
speed cell, so only the attributes need updating when a row's setup changes.
Deep links into the planner use
`https://mlbottleneck.com/?model=&hardware=&count=&format=&runtime=&spec=`.

`models/<id>.html` (one page per package) and `models/index.html` are generated
by `python3 tools/build-model-pages.py` from `packages/catalog.json`; rerun it
whenever the catalog changes and commit the output. The generator's
`PACKAGE_ML` map ties a package to its ML Bottleneck preset/quant/runtime; a
package without an entry simply gets no projection block.


---

## Lane Decisions And Lane Notes

Owner decisions that bind one lane:

- **MiniMax-H3 (2026-10-10):** Owner decision, verbatim: "we will use the H3 model as we have optimized it; that will be the package and the result we will use. It's an appropriated denoiser, but from my understanding it is lossless, just different prompt->result, but mathematically lossless. It was a trade I was willing to make for a sizable performance boost. Either way, package it, turn it into a recipe, document it, publish it, etc."
  The owner has reviewed and chosen this result; the September 19/20
  "owner reviews first" gate is satisfied for it. H3 stays featured on
  neural.download. Comfy-Org's published pruned BF16 denoiser (`minimax_h3_fl2va_pruned_bf16.safetensors`): all weights bit-exact with the official checkpoint except the AdaLN tables, which that release replaces with a fitted approximation (lab analysis: below the BF16 noise floor); the 2x result is an exact scheduling speedup against that denoiser's own reference (32 MATCH / 0 DIFFERS, 8 repeat passes). This is not a claim of losslessness versus the official model. The lab analyzed the published file; it did not produce the fit. The owner's acceptance of this exact model is the required approval for the Comfy-Org source under the October 10 source rule. The measured run and recipe target turin (`steve-TURIND8-2L2T`): two B70 cards and 15 GiB RAM. The historical 800.8 s/clip is a **ledger-recorded baseline, raw receipts not retained**; the receipted measured result is 396.6 s/clip in one eight-clip batch. Published input hashes are verified on turin; baseline/reference raw receipts, clean-build/runtime and independent full-suite repeat evidence remain pending.

- **Qwen 27B FP8 (2026-09-14):** DFlash is excluded from further work. Keep
  native MTP, official FP8 target weights, the qualified target arithmetic and
  KV settings, and lossless output gates. Investigate other transferable ideas
  without reopening the DFlash startup candidate.
- **MiniMax-H3 (2026-09-19/20):** the goal track is deterministic and lossless,
  bit-identical to the base schedule at a fixed seed. Turbo LoRA, fp16 decode
  and anything else that changes a bit are measured, recorded and left to the
  owner. Publish only after a confirmed significant improvement, and the owner
  reviews first.
- **Quantized releases are separate models (2026-10-10):** a quantized
  release such as Unsloth UD-IQ3_XXS of Qwen3.8 Flash-Next is its own model
  with its own lane, oracle and records. It is held to the full lossless and
  deterministic standard against its own weights (bit-identical across fresh
  processes, agreeing with the lab's CPU reference dequantization of the same
  bytes); no tolerance against FP8 is a gate, and FP8 differences are reported
  for information only. Label it "quantized compressed version", never as the
  Flash-Next model, and never beside the FP8 record as comparable. The FP8
  four-card line stays the Flash-Next authority. Owner: "treat the IQ3 as a
  model of its own ... lossless relative to what it is, not relative to FP8".
- **All lanes (2026-10-03): lossless only.** No lossy shortcut is a default or
  a goal: no turbo LoRA, no fp16/bf16 decode, no compressed KV, no pruned model
  as the headline. The lanes to optimize on the two-card host are Qwen 27B FP8
  (one card, or two cards in TP2) and MiniMax-H3 (faster, more stable, more
  deterministic).

Technical notes for the Qwen3.8 vLLM lane (2026-09-04/05), kept because each
cost real time to learn:

- The lane compiles with `CompilationMode.VLLM_COMPILE` (the CLI's `mode: None` is unresolved). Plain Python logging inside model code is traced away by Dynamo; a probe must be a custom op with a fake impl (`direct_register_custom_op`, `mutates_args=["tensor"]`, see `experiments/qwen38-27b-b70/docker/r182-layer-trace-v3.py`) and gate on the forward context's GDN metadata, indexing the last real row by `num_actual_tokens`. Any such op splits the graph and changes numerics; it is not observation-neutral.
- CPU import tests inside the lane images need `docker run -w / ...`: the container WORKDIR is a vLLM source checkout that shadows the installed package for bare `python -c`, while the server uses `/opt/venv`.
- Any Python branch on the batch/row count inside a compiled forward (padding, kernel selection, chunking) must live inside a registered custom op with a fake impl (`direct_register_custom_op`). An in-graph branch survives the strict stage and then fails the ladder config with `ConstraintViolationError` (R213 -> R213b, 2026-09-05).
- Judge the MTP first-token phantom by divergence at index 0 against the oracle, not by token 60 (it also appears as 220). Its signature is an inserted token that the model never saw: the tokens after it equal the normal answer for 16-18 tokens, then drift. It occurs on the unmodified upstream XPU image in any compile mode (R192/R194); on this deterministic build `splitting_ops=[]` avoids it, it does not fix it. Say "avoids" in every published sentence.
- `COMPILATION_CONFIG` and `SPECULATIVE_CONFIG` reach `run-server.sh` / `run-w8a16-mtp1-server.sh` through the environment from any runner; the r152 runner honours `EXTRA_SERVE_ARGS`, `QUERY_ONLY`, `PROBE_AND_LADDER_MTP1`, `STRICT_MTP1_ONLY` (+`ORACLE_ROOT`), `LADDERS_ONLY`.
- Identity claims use the two-run rule: the deepest rung exact in both ladders; aggregate rates are published only through that rung.
- Any attention-path kernel for this lane must be built with the
  `CUTLASS_REVISION` the kernel CMake pins; a build against another sycl-tla
  checkout is not bit-identical (2026-09-18).
- Editing either FP8 package launcher (`packages/qwen38-27b-fp8-tp*-b70/scripts/serve.py`)
  moves bytes that frozen evidence packets pin. Follow
  `experiments/qwen38-27b-b70/notes/2026-09-19-noswap-launcher-change.md`
  and run every `run:` line of `.github/workflows/guides.yml` locally.

