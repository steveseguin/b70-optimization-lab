# Agent Notes

This repository is a reproducible lab notebook and deployment guide for Intel
XPU local AI work across multiple B70 model efforts: MiniMax, Qwen, Gemma, and
future lanes.

## First Read

Read these in order before changing runtime behavior:

1. `CURRENT.md`
2. Current lane `HANDOFF.md` and result packet linked from `CURRENT.md`
3. `README.md`
4. `docs/current-reproducibility-map.md`
5. `docs/model-optimization-guide.md`
6. `AGENT_HANDOFF.md`
7. `docs/model-effort-index.md`
8. `docs/local-ops.md`
9. `docs/localmaxxing.md`
10. A model packet, for example
   `results/gemma4-26b-a4b-q8-b70/HANDOFF.md`,
   `results/gemma4-26b-a4b-q8-b70/README.md` and
   `results/gemma4-26b-a4b-q8-b70/reproduce.md`.

The model weights, secrets, and full raw `/mnt/fast-ai/bench-results` tree are
not in GitHub. The repo does include scripts, patch artifacts, summarized
results, payloads, and notes needed to rebuild or review the work.

Use these common folders consistently:

- `notes/` for chronological experiment notes, including negative results.
- `patches/` for patch snapshots and source-level deltas.
- `data/` for structured run summaries, payloads, responses, and logs that are
  reasonable to track.
- `results/` for promoted or summarized model result packets.
- `scripts/` for reusable harnesses and submission helpers.
- `model-intake/` for revision-pinned candidate artifacts, external-store
  planning, and the discovery-to-validation queue.
- `experiments/` for active research lanes that are not production recipes.
- `repro/` for runnable promoted reproduction recipes.
- `community/` for outside contributions at any evidence level. Contributed
  work stays here until it is reproduced on B70; never move an unverified
  contribution into `results/` or `repro/`, and never record a contributor's
  claim as a lab measurement.

## Source of Truth and Attribution

This repository is the source of truth for the lab's recipes, patches,
measurements, and optimization history. External repositories are research
inputs or provenance records; they are never the primary guide for a lab lane.

- Ingest useful knowledge into this repository as a pinned patch, focused
  note, runnable recipe, or result packet with local evidence.
- Credit an external author at the exact point where a concrete original
  patch or technique is adopted. Name the delta, pin its identity, and record
  the measured effect on the lab lane. Do not give broad recipe or performance
  provenance when the external material repackages work already present here.
- Keep intake snapshots and unverified reports under `community/`. Do not put
  them on the landing page as recommended setup paths or imply that they are
  authoritative for lab-developed lanes.
- Never use a lab measurement to confirm an outside claim unless model,
  checkpoint, quantization, runtime, patch set, GPU topology, metric, and
  quality gate match. A similar speed on a different lane is not confirmation.
- Public pages should link lab rows to `results/`, `repro/`, `experiments/`,
  `patches/`, or `data/` in this repository. Link externally only where needed
  to credit the specific contribution being discussed.

When reviewing an outside patch, recipe, result, model lead, or pull request,
use the repository-local `$review-model-contribution` skill. It connects
intake, safe review, matched validation, boost calculation, guide/package
updates, and durable contributor acknowledgement without changing the evidence
boundaries above.

When creating or updating a model package, public guide, deployment variant,
featured benchmark, or context-performance graph, use the repository-local
`$publish-model-package` skill. It requires closed in-repository dependencies,
exactly scoped measurements, honest pending states, and live-site verification.
In particular, never extrapolate or interpolate performance curves or invent
unmeasured context points.

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

## Local Secrets

Never print, paste, or commit local credentials. The Hugging Face access token
for model downloads is stored outside the repo at:

```text
/home/steve/.config/huggingface/token
```

Scripts that need faster Hugging Face downloads should read this file into
`HF_TOKEN` locally. The token file is covered by repo and global Git ignores.

LocalMaxxing credential guidance is in `docs/localmaxxing.md`; the key itself
is outside Git at `/home/steve/.config/localmaxxing/api_key` or supplied as
`LMX_API_KEY`. Never print or commit it.

The local sudo password file is `/home/steve/SUDOPASSWORD.txt`; local privileged
operations guidance is in `docs/local-ops.md`. Use it only for local driver,
runtime, service, or recovery tasks that truly require sudo. Never print or
commit the password or a copy of the file.

## Live State Authority

`CURRENT.md` is the sole cross-repository authority for the loaded service,
active optimization lane, protected work, and immediate next actions. Detailed
evidence remains in the lane handoff and result packet linked from that file.

Do not infer what is live from a deployable recipe, old handoff, service unit,
historical note, or result packet. Verify Git status, relevant processes, and
the actual endpoint before operational changes. Preserve any paths marked
active or protected in `CURRENT.md`; do not disturb shared runtime trees or GPU
work merely because another lane has a runnable recipe.

## Quality Rules

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

The current Gemma 4 26B A4B Q8 one-B70 realistic-suite best is:

- result packet: `results/gemma4-26b-a4b-q8-b70/README.md`;
- reproduction: `results/gemma4-26b-a4b-q8-b70/reproduce.md`;
- standalone current repro:
  `repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md`;
- realistic suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- best strict cold-suite result:
  published legacy `124.97714084813418 tok/s`, or
  `123.72736943965285 tok/s` under conventional 99-interval accounting,
  `cached_tokens=0` on every prompt,
  `realistic_final_gate.passed=true`;
- evidence:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`;
- latest same-recipe doc-pass rerun:
  `data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`
  at `120.92334534956485 tok/s`, valid/fresh/cached-zero with `512/512`
  canary rows; support only, not a new record;
- config:
  llama.cpp `c926ad098`, reordered-Q8 VDR2, Q4_0 MTP draft,
  `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`,
  `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`;
- representative / submitted status:
  the VDR2 selected-down fused weighted-sum path plus FA-on 32K/VMM plus final
  post-norm residual fusion is the current policy-compliant LocalMaxxing
  submission, approved as `cmr1u77na01k2ld01kalwzs1e`. Same-family support
  includes the prior `123.67689864739785 tok/s` row
  (`cmr01nnet000mld01x2tt6qds`), the prior `121.41411987308553 tok/s` row
  (`cmqztiqdn02vnoe01egox6q3f`) and
  `data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json`
  at `119.94842631460949 tok/s`. The prior selected-down repeat
  `cmqyrpox4021dqk01co5o4fcw`, initial selected-down confirmation
  `cmqyo0jyt08ippk01vhiobdnm`, VDR2/F16-p021 row
  `cmqxchyra03xmqr01b963gmi1`, F16-p021 small-ncols submission
  `cmqx3687103v4qr01ace1ft3m`, earlier VDR2 rows, and prior VDR4 rows are
  superseded;
- current clean no-spec control:
  `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`
  at `74.29709476830473 tok/s` median. Use it as the simplest target-side
  quality/control reference.

The previous Gemma 4 26B A4B Q8 one-B70 diagnostic best is:

- result packet: `results/gemma4-26b-a4b-q8-b70/README.md`;
- reproduction: `results/gemma4-26b-a4b-q8-b70/reproduce.md`;
- synthetic filled-long row0: `176.21623213048554 tok/s` after TTFT,
  `176.40259133127742` support mean, 1536 canary repeats / 6144 rows,
  LocalMaxxing `cmqwkedg303jeqr013z753j62`, now classified as diagnostic until
  the fixed realistic prompt suite passes with that configuration;
- target/verifier: UD-Q8_K_XL, Q4_0 MTP draft only; do not promote lower
  precision/QAT/Q4XL side-lane results as this Q8 headline.

## Working Rules

### Rolling Upstream And Optimization Overlay Policy

Active development starts from the newest available upstream code. A mutable
tag such as `nightly` must be pulled and resolved again at the start of active
runtime work; an older digest-pinned image is a historical reproduction anchor,
not the current nightly merely because its tag contains that word. Record the
source tag, registry manifest digest, local image ID, image creation time,
upstream source commit, and runtime package versions before launching a model.

Treat the lab's accepted optimizations as a maintained overlay on that moving
upstream base:

- inventory source patches separately from environment, launcher, topology,
  cache, and compilation settings;
- check whether upstream already contains each accepted change before applying
  it again;
- rebase or reapply still-needed accepted patches onto the newest base and
  rerun their mechanism, correctness, and performance gates;
- never silently drop a useful patch because it conflicts. Preserve the patch
  and record whether upstream superseded it, it was ported, it is temporarily
  blocked, or it failed a new gate;
- keep negative, unsafe, diagnostic-only, and default-off patches as historical
  artifacts, but do not promote them into the current overlay without a new
  qualification;
- preserve every prior high score under its exact old identity. A slower run on
  newer code is regression evidence, not permission to lower or overwrite the
  captured frontier.

Promotion on a refreshed base requires a full benchmark-identity diff against
the last known-good run, the same quality/canary bar, and matched performance
checks. Run by the resolved immutable digest after the pull so a moving tag
cannot change during a campaign.

### Main-Only Git Policy

Work directly on `main` only. Never create or maintain feature, experiment,
promotion, temporary, maintenance, or agent branches or secondary Git
worktrees. Preserve alternate implementations and recovery points as focused
commits, patches, bundles, configs, notes, tags, and result artifacts. Pull
`main` before starting when appropriate, and push focused verified commits back
to `main` rather than accumulating unpublished side histories.

- Keep c1 easy to restore.
- Record commands, logs, result paths, patches, and caveats.
- Put scripts and patches in GitHub whenever they are needed to reproduce a
  result.
- Do not claim c4, c8, TurboQuant, or CPU-paged attention is production-ready
  until the documented blockers are cleared.
- Preserve experiment patches and their results, including failed patches, so
  future agents do not rediscover the same dead ends. Promote successful
  patches only after verification, while keeping the experiment record linked.
- Commit regularly with focused commits and explicit paths. Do not use broad
  `git add -A` in a mixed experiment tree.
- When a verified realistic-suite run breaks a real LocalMaxxing record for a
  matching 1/2/3/4 GPU configuration, submit it with model, quantization, GPU
  count, mode, run identity, throughput, correctness status, prompt/output
  hashes, and supporting artifact links. Do not submit warmed/history,
  synthetic-only, or lower-precision side-lane results as the Q8/INT8 headline.

## Cross-Agent Delegation

When Claude/OpenCode is orchestrating work, prefer delegating concrete research,
audit, patch, and validation tasks to Codex/GPT through the CLI. GPT token use
is less constrained here, so Claude/OpenCode should manage/review and ask Codex
to do bulky searches, source reading, and iteration-heavy implementation where
practical.

Useful forms:

```bash
codex --cd /home/steve/llm-optimizations
codex exec --cd /home/steve/llm-optimizations "audit the Gemma docs and propose focused cleanup"
codex review --cd /home/steve/llm-optimizations
codex resume --last
```

Codex should use subagents whenever reasonable and available, especially for
parallel source audits, independent review of risky changes, log/result
classification, and research synthesis. The main Codex agent still owns final
edits, verification, and safety around active experiment processes.
