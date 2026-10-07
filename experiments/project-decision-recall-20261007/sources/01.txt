# Agent Notes

This repository is a shared, reproducible lab notebook for optimizing local AI
models on Intel XPUs: recipes, patches, measurements and the history of what
was tried. It covers several model lanes (Qwen, MiniMax, Gemma, LTX and future
ones) and is worked on from two machines that both push to `main`:

- the **two-card host** (`steve-TURIND8-2L2T`: two Arc Pro B70, 15 GiB of RAM);
- the **four-card host** (`steve-b70s`: four Arc Pro B70, 128 GiB of RAM).

A rule below applies to both hosts unless it names one. Reviewed and
consolidated on 2026-10-03; older dated wording that this replaces is noted
where it matters.

## Owner's Standing Rules

These come directly from the owner and override anything else in this file,
any older note, and any recipe.

### 1. The job is optimizing, not hosting (2026-10-03)

The focus of this lab is making models faster without losing quality. A server
is hosted when the optimizing is done, and it is not done.

- **No model server is left running.** A server exists only for the length of
  an experiment: start it, measure, stop it gracefully, leave the cards empty.
- Do not start, restore, queue or auto-launch a resident server unless the
  owner asks for one. A campaign runner must not end by "putting the service
  back".
- This replaces the 2026-09-13 wording "prefer one continuously running server
  and reuse its endpoint", which was an agent's reading and is withdrawn.

### 2. No cheating (standing)

A speed number only counts if the output is what the unchanged model would
have produced and the test was a fair one. The full rules are in
[Quality Rules](#quality-rules-no-cheating); in short, none of these may ever
produce a headline: cached or warmed prompts, prompt/KV/response reuse,
hand-picked easy prompts, a lower precision or a compressed KV cache presented
as the original, speculative tokens the target model did not verify,
extrapolated or interpolated points, one lucky server, or a diagnostic
workload dressed up as a benchmark. A change that alters the output is
recorded as lossy and left for the owner to judge; it is never adopted
quietly.

**KV cache stays at full 16-bit precision** (BF16, or FP16 where the runtime
uses that) by default (owner, 2026-10-03). An FP8 or otherwise compressed KV
cache is cheating, so it is not a default and never a headline. Use one only
when a 16-bit cache is not available for that model, or when the owner says
so explicitly. This rule is not meant to break things: if something
specifically should not be BF16, raise it with the owner instead of working
around it.

### 3. Keep the machine safe (2026-09-13, clarified 2026-09-14 and 2026-10-03)

- **Power settings are off limits.** Do not change ASPM, PCIe power
  management, CPU governors, GPU clocks or power limits, or any other power
  setting, including changing one back as a cleanup.
- **No automatic reboot or driver reset.** A reboot always needs the owner's
  explicit authorization. The evidence-first recovery sequence, including
  when a driver reload is appropriate on the four-card host, is in
  `docs/local-ops.md`. Never clear a device coredump before copying it out.
- **Host memory, swap and page-cache settings change only with the owner's
  approval**, and each change is recorded in `CURRENT.md`. No swap toggles,
  cache drops or host-controlled benchmark wrappers. Settings the owner has
  approved are listed under [Host Facts](#host-facts).
- **No restart loops.** Nothing restarts or retries a failed server
  automatically, and a failed client request never cycles a server. A
  preregistered campaign runner may start and stop the servers its stages
  need, each exactly once.
- **A controlled reload inside authorized work does not need an approval
  pause** (2026-09-14). Explain it in plain words, distinguish it from
  restarting the computer, and continue optimizing afterwards.
- **One fault does not end the session** (owner, 2026-10-03). On the first
  `Fault response`, CAT error, engine reset, timed-out job or coredump line:
  stop new launches, save the evidence, and do not retry in a loop. Then try
  to recover without a reboot: run one bounded health probe
  (`docs/local-ops.md`; on the two-card host
  `scripts/check-qwen36-xpu-xccl-health.sh`). If it passes and the kernel log
  stays clean, carry on with the work and note the fault in `CURRENT.md`. Do
  not ask first. If the probe fails, or a second fault follows on the same
  boot, stop and tell the owner that a reboot is needed. There is no
  one-experiment-per-boot rule.
- **Stop GPU jobs gracefully.** Hard-killing a busy GPU process (a cgroup
  kill, `docker rm -f`, a watchdog's group kill) logs fault lines by itself on
  this driver. It is the last resort, and it is handled as a fault under the
  rule above.
- **Never give a container a memory limit below what the job touches while
  also allowing it swap.** Launchers use `--memory-swap` equal to `--memory`.
  A cap that is too low is a source of memory pressure, not a safety net.
- **One kernel, driver or firmware change per boot,** each measured before the
  next (`scripts/fp8-start-cycle-soak.sh` is the measurement for the two-card
  host). Symptoms, counts and checks:
  `docs/host-stability-and-fault-diagnosis.md`.
- Historical recipes are preserved as evidence, not as current operating
  instructions.

### 4. Never stop optimizing; report in plain words (2026-10-03, strengthened 2026-10-04)

- **When the task is optimizing, keep optimizing until the owner says stop.**
  Never stop, pause or offer to stop because a result looks maxed out. "It is
  at its limit" is not a conclusion this lab accepts: it only means the levers
  tried so far are used up, and the job is then to find new ones. Do not list
  "stop here" as an option and do not ask whether to continue.
- **A lever can be closed. A lane is never finished.** When one lever is
  spent, say so in a line and move to the next. If the narrow number stops
  moving, widen the target rather than stopping: more users at once, faster
  prompt reading, longer context, lower memory, faster start, more stable,
  another kernel or runtime path, the other model in scope.
- **Carry on without being asked.** After a batch of work is done and
  reported, start the next lever in the same turn. Pause only for something
  that is the owner's to decide (a reboot, publishing, a quality judgement),
  say exactly what is needed, and keep working on everything that does not
  depend on the answer.
- **Reports to the owner are plain, everyday words: simple and direct.** Say
  what happened, then what you are doing next. Details, commands and
  experiment IDs go in lane notes, and `CURRENT.md` is written the same way.
- **Stay on the goal; do not rabbit-hole.** Before starting a lever, ask what
  it can be worth. A change that can only move a result by a percent or two
  is closed quickly or skipped, not turned into a campaign. That is a reason
  to pick a bigger lever, never a reason to stop.

## First Read

Read these in order before changing runtime behavior:

1. `CURRENT.md`
2. The active lane's handoff, notes and `DO-NOT-REPEAT.md` (linked from
   `CURRENT.md`)
3. `README.md`
4. `docs/current-reproducibility-map.md`
5. `docs/model-optimization-guide.md`
6. `docs/model-effort-index.md`
7. `docs/host-stability-and-fault-diagnosis.md`
8. `docs/local-ops.md`
9. `docs/localmaxxing.md`
10. A model packet, for example
    `results/gemma4-26b-a4b-q8-b70/HANDOFF.md`,
    `results/gemma4-26b-a4b-q8-b70/README.md` and
    `results/gemma4-26b-a4b-q8-b70/reproduce.md`.

`AGENT_HANDOFF.md` is only a pointer to the list above.

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
- `packages/` for the user-facing package manifests the site is built from.
- `audits/` for the weekly efficiency audit and its triage
  (`audits/efficiency/TRIAGE-2026-10-03.md`).
- `community/` for outside contributions at any evidence level. Contributed
  work stays here until it is reproduced on B70; never move an unverified
  contribution into `results/` or `repro/`, and never record a contributor's
  claim as a lab measurement.

## Live State Authority

`CURRENT.md` is the sole cross-repository authority for what is loaded on each
host's cards (normally nothing), the active optimization lane, protected work,
and immediate next actions. Detailed evidence remains in the lane handoff and
result packet linked from that file.

Do not infer what is live from a deployable recipe, old handoff, service unit,
historical note, or result packet. Verify Git status, relevant processes, and
the actual endpoint before operational changes. Preserve any paths marked
active or protected in `CURRENT.md`; do not disturb shared runtime trees or GPU
work merely because another lane has a runnable recipe.

Update `CURRENT.md` when ground truth changes, in the same commit as the work.
An entry that waits on the owner carries its date, and is updated when work
moves past it.

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

Any recipe that claims to be publicly reproducible must also follow
`docs/recipe-publication-standard.md`, carry a validated
`publication-manifest.json`, and pass both local and remote modes of
`tools/validate-recipe-publication.py`. A local image, an originating-host
binary, or a hand-maintained hash allow-list is not publication. Do not mark a
recipe `published` until every release asset has been downloaded from its
public URL and re-hashed.

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
`main` before starting, and push focused verified commits back to `main`
rather than accumulating unpublished side histories. The only branches that
exist are outside contributors' pull requests.

Both hosts push to the same `main`. Before rebasing onto incoming commits,
look at `git diff --stat` for unexpected deletions or emptied files (a commit
from one host once zeroed 302 files).

- Commit regularly with focused commits and explicit paths. Do not use broad
  `git add -A` in a mixed experiment tree.
- Record commands, logs, result paths, patches, and caveats. Put scripts and
  patches in GitHub whenever they are needed to reproduce a result.
- Preserve experiment patches and their results, including failed patches, so
  future agents do not rediscover the same dead ends. Promote successful
  patches only after verification, while keeping the experiment record linked.
- Check the lane's `DO-NOT-REPEAT.md` before opening an experiment arm, and add
  a row when an arm closes.
- A `package.json` dependency and the file it points at land in the same
  commit, or CI fails that commit.
- Do not call a concurrency level, a compressed-KV mode or an offload path
  production-ready until its documented blockers are cleared.
- When a verified realistic-suite run breaks a real LocalMaxxing record for a
  matching 1/2/3/4 GPU configuration, submit it with model, quantization, GPU
  count, mode, run identity, throughput, correctness status, prompt/output
  hashes, and supporting artifact links. Do not submit warmed/history,
  synthetic-only, or lower-precision side-lane results as the Q8/INT8 headline.
  If the owner is running the publish steps themselves, do not run the same
  external step in parallel.

### Diagnosis And Campaign Speed Rules (2026-09-02)

Recorded after the Qwen3.8 27B FP8 identity lane spent R64-R146 (three days)
on a defect that one operator-level sweep and one chained campaign then
settled in an evening. These are binding for every lane on both hosts.

1. **Census before bisection.** When a greedy output flips with batch shape,
   prompt length, or concurrency, run every production GEMM shape through the
   kernel invariance/determinism sweep on one card first
   (`experiments/qwen38-27b-b70/scripts/qwen38-fp8-kernel-batch-invariance-census.py`
   and `qwen38-fp8-kernel-determinism-sweep.py`; adapt the shape table per
   model). No server launch for localization until every kernel is cleared or
   blamed. Token-stream bisection on a fixed prompt pair is a one-coin
   detector and is closed as a method.
2. **An oracle is bound to a kernel identity.** A row-invariant or otherwise
   re-ordered kernel must be gated against a same-image oracle regenerated on
   that kernel, never against an oracle produced by the previous arithmetic.
   The frozen oracle stays a localization tool.
3. **No speed verdict from fewer than two fresh servers,** and speed is never
   a gate on an identity experiment; it is recorded. This host's
   control-vs-control drift is about 3% back-to-back and up to 10% across a
   session.
4. **Preregister the whole campaign, run it as one unattended runner.** The
   runner owns preflight, every server stage, the comparisons, health
   postflights, and abort rules; the human reviews once at the end. One
   server per preregistration with a human round trip in between is the slow
   path and is not the default.
5. **Fast-fail GPU faults.** A runner polls the kernel journal during server
   startup and aborts on the first `Fault response`, CAT error, engine reset,
   or coredump line instead of waiting for a health timeout. Filter with
   specific signatures; generic words such as `hang` match unrelated lines.
6. **Stop searching when a candidate passes its gate.** The first arm that
   meets its preregistered operator gate goes to the endpoint the same day;
   the endpoint result, not further geometry sweeps, decides the next step.
7. **Delegate read-only work while GPUs are busy.** Recipe audits,
   preregistration drafting, and result summarization run in parallel through
   `codex exec --sandbox read-only` or a subagent; they never wait for a GPU.
8. **One lane per host at a time.** GPU faults and reboots from one model lane cost
   the other lane its boot. Before starting GPU work, check what else is
   running on that host and what `CURRENT.md` marks active there.

### Process Hygiene

- **Long GPU jobs run in their own systemd user unit** (`systemd-run --user`),
  not in an agent's shell: the agent harness kills long jobs.
- **Kill by pid, never by pattern.** Capture the pid with `$!` at launch, or
  run the search in its own command and kill the printed pids in the next one.
  A `pgrep -f`/`pkill -f` pattern matches the calling shell's own command line
  when any path, file name or script name on that line contains it (exit 144 =
  you killed yourself; it happened three times on 2026-09-05).
- A queued wrapper that has passed its wait loop has already spawned its
  campaign; killing the wrapper does not stop the child. Check for the child
  first.
- Never put `cut`, `head`, or another block-buffered stage in a Monitor
  pipeline; a verdict sat unseen for an hour behind `cut` (R211).
- Profiling is never the first stage of a campaign and never a speed
  measurement. On the two-card host a profiler window is about 8 steps, not 30
  (`experiments/qwen38-27b-b70/notes/2026-10-03-fp8-comm5-attempt1-guard-kill.md`).
- Container-written caches and state directories are owned by root; a
  user-level `rm -rf` fails silently per file.

## Host Facts

Things that differ between the two machines. Check `hostname` first.

| | Two-card host | Four-card host |
| --- | --- | --- |
| Hostname | `steve-TURIND8-2L2T` | `steve-b70s` |
| Cards | two B70 (`0000:03:00.0`, `0000:e3:00.0`) | four B70 |
| Host memory | 15 GiB, ECC, error counters work | 128 GiB, **no ECC**, one module has a bad chip (see the stability guide) |
| Sudo password file | `/home/steve/SUDO_PASSWORD.txt` | `/home/steve/SUDOPASSWORD.txt` (as `docs/local-ops.md` records it; check which exists) |
| Active lanes | Qwen3.8 27B FP8, MiniMax-H3 | LTX 2.5, Flash-Next |

Owner-approved host settings on the two-card host, as of 2026-10-03:
`vm.swappiness=1` (`/etc/sysctl.d/90-b70-swappiness.conf`); `earlyoom` as a
low-memory backstop (`/etc/default/earlyoom`); automatic kernel and GPU-firmware
upgrades switched off (`/etc/apt/apt.conf.d/51b70-no-auto-kernel`); kernel
7.0.0-38 with 7.0.0-31 kept as the fallback. On that 15 GiB machine one
host-memory-heavy job runs at a time, never beside a build container, and
MiniMax-H3 GPU work goes only through
`experiments/minimax-h3-b70/scripts/smoke_h3.sh` (its memory watchdog is not
optional). The four-card host's approved workarounds (offlined memory blocks,
the deepest CPU idle state disabled) are in
`docs/host-stability-and-fault-diagnosis.md`.

## Lane Decisions And Lane Notes

Owner decisions that bind one lane:

- **Qwen 27B FP8 (2026-09-14):** DFlash is excluded from further work. Keep
  native MTP, official FP8 target weights, the qualified target arithmetic and
  KV settings, and lossless output gates. Investigate other transferable ideas
  without reopening the DFlash startup candidate.
- **MiniMax-H3 (2026-09-19/20):** the goal track is deterministic and lossless,
  bit-identical to the base schedule at a fixed seed. Turbo LoRA, fp16 decode
  and anything else that changes a bit are measured, recorded and left to the
  owner. Publish only after a confirmed significant improvement, and the owner
  reviews first.
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

## Publication Checklist

- Publication surface for a lane, in order: `experiments/.../data/*-result.json` + note, `repro/.../README.md`, `publication-manifest.json` chain entry (refresh every sha256 after editing an evidence file), `packages/.../package.json` (commands must be exactly benchmark/health/launch/preflight/stop; `dependencies` must be git-tracked), sync `packages/catalog.json` from it (embed + keep `manifest`), `python3 tools/build-model-pages.py`, `python3 tools/validate-repro-guides.py`, top `README.md`, `CURRENT.md`. LocalMaxxing: queue JSON in `data/`, `--server-dry-run`, then submit; record `data/localmaxxing-responses/`, `results/localmaxxing-submissions.md`.
- Before pushing anything that touches published surfaces, run both integrity checks: `python3 tools/check-doc-links.py` (repo-relative links in Markdown) and `python3 tools/check-manifest-paths.py` (repo-relative paths inside `families/*.json`, `packages/*/package.json` and `packages/catalog.json`). The second exists because the first cannot see JSON: a family manifest's `evidence` list and a package's `dependencies` are how a reader gets from a published number to the file supporting it, so a stale entry there is a broken claim, not a broken link. Both are quiet and take seconds.
- `python3 tools/check-pinned-hashes.py` exercises the repo's literal SHA256 file pins. A gate that pins shared tooling only fails when someone runs it, so an unexercised pin is indistinguishable from a satisfied one: the Laguna record's gate was unrunnable for two weeks before anyone noticed, and 224 Flash-Next clients are in the same state. Drift is not automatically a defect — a frozen packet *should* pin what it was verified against — but it should be a known fact rather than a surprise at replay time. Run it after editing anything under `tools/` or `scripts/` that a packet might pin.
- When a JSON manifest is rewritten programmatically, dump it with `ensure_ascii=False`. `json.dumps`'s default escaped 55 non-ASCII labels across the shared family manifest in one commit on 2026-09-08; the content was fine and the diff was not.
- CI is `.github/workflows/guides.yml`. Before pushing a change to a package,
  a guide, a model page or pinned evidence, run each of its `run:` lines
  locally.

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

The local sudo password file is outside the repo and its name differs by host
(see [Host Facts](#host-facts)); guidance is in `docs/local-ops.md`. Use it
only for local driver, runtime or recovery tasks that truly require sudo, and
pass it to `sudo -S` on standard input. Never print or commit the password or
a copy of the file.

## Cross-Agent Delegation

When Claude/OpenCode is orchestrating work, prefer delegating concrete research,
audit, patch, and validation tasks to Codex/GPT through the CLI. GPT token use
is less constrained here, so Claude/OpenCode should manage/review and ask Codex
to do bulky searches, source reading, and iteration-heavy implementation where
practical. Decisions and GPU actions stay with the orchestrating agent.

Useful forms (the repository is `/home/steve/b70-optimization-lab`):

```bash
codex exec --sandbox read-only -C /home/steve/b70-optimization-lab "audit the FP8 package docs and list stale numbers"
codex exec --sandbox workspace-write -C /home/steve/b70-optimization-lab "edit ONLY <files>; do not commit; do not run docker or GPU commands"
codex review -C /home/steve/b70-optimization-lab
codex resume --last
```

Give a delegated agent the files it may touch, tell it not to commit and not
to run GPU, docker or systemd commands, and verify what it reports before
relying on it.

Codex should use subagents whenever reasonable and available, especially for
parallel source audits, independent review of risky changes, log/result
classification, and research synthesis. The main agent still owns final
edits, verification, and safety around active experiment processes.

Use the repository-local skills under `.agents/skills/`:
`$review-model-contribution` for outside patches, recipes, results and pull
requests, and `$publish-model-package` for packages, public guides and
featured benchmarks.
