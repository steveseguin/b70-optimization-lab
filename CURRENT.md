# Current Workspace State

Consolidated **2026-10-10** from the recorded ledger; this summary does not establish freshly verified host state.

The full 5,077-line source is preserved byte-for-byte in [CURRENT-history-20261010.md](CURRENT-history-20261010.md), at the same directory level so its relative links retain their meaning.

Source commit: `f7b5356bafa5bc2af06e9dffbc88822fb0d2cded`. Archive SHA256: `b0dec25fb12e796963454e28101c88b8f53c7678fff48b0c11504b5ca642036c`.

The [repository cleanup audit](audits/repository-cleanup/README.md) records the inventory, preservation rules and exact dispositions. The graph-safe research tree remains protected and in place; this consolidation archives only this page's
chronology.

## Authority And Update Rule

This is the sole cross-repository authority for recorded host state, active lanes, protected work and next actions. [AGENTS.md](AGENTS.md) supplies the owner's standing rules. Verify Git status, lane ownership, relevant processes/listeners and the
actual endpoint before operational changes; a deployable recipe does not establish what is running.

Update the affected host and lane here when ground truth changes, in the same commit as the work. Keep detailed chronology and receipts in lane notes, and date unresolved owner decisions. The [October archive](CURRENT-history-20261010.md) and
[September archive](CURRENT-history-20260909.md) are history: their launch, service, restart and cleanup instructions do not authorize new action.

## Recorded Host State

| Host | Latest operational observation in the source ledger | Current constraint |
| --- | --- | --- |
| Four B70: `steve-b70s`, 128 GiB installed, bad-memory blocks fenced | **2026-10-10 18:10 UTC:** third GPU fault incident on boot `4aafe57b-a54f-4bfd-b4ed-9f1cbb8830c7`, kernel `7.0.0-39`. LTX 137 stopped at 18:05:13 after 62 chunks of its second session. The bounded health check subsequently passed all four cards. | **GPU launches halted.** The successful health check does not clear this third incident; a new owner decision and matching admission are required. |
| Two B70: `steve-TURIND8-2L2T` (turin), 15 GiB ECC RAM | **2026-10-08 21:10 EDT:** cards empty after the retention study; that day's H3 live session had ended at 13:33 EDT. October 10 H3 input checks are provenance checks, not a newer service observation. | Qwen 27B FP8 and H3 remain its optimization lanes. Recheck actual state before using the host; the recorded empty-card observation is not a live check. |

No resident server is authorized by this consolidation. Start/measure/gracefully stop experiments; leave cards empty unless the owner explicitly requests hosting. One GPU lane per host at a time. Do not revive the withdrawn September 13
continuous-service rule or superseded relaunch queues.

## Four-Card Halt And Flash-Next

On October 10 the immediate-abrupt-exit probe completed correct computation, then card `23:00.0` logged four fault-class lines at 18:07:19 UTC. The boot then had eight fault-class lines; the bounded postflight added none. Preserve
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json` and every probe/run receipt under `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/`.

The earlier same-boot acceptance does not cover this incident. The halt remains until a newly recorded owner decision and matching admission support resolve it; a cleanup instruction is not that decision. No automatic reboot, driver reset, retry loop
or new GPU probe is authorized here.

[The corrected interpretation](experiments/qwen38-flash-next-fp8-b70/notes/2026-10-10-exit-fault-reproduced.md) supports an exit/lifetime timing problem: clean shutdown, exit after ten idle seconds, and the one-layer first-forward case with graceful
teardown passed. It does not identify the exact outstanding resource, prove full-rank loading repaired, or explain attempt 7's earlier startup fault. The older categorical remedy claim is superseded.

After the halt is resolved, the recorded next Flash-Next step is one full loading check with graceful teardown and the **96 GB loading guard**, fresh admission/health and an exclusive idle window at least **five minutes** after the preceding stop.
Another abrupt-exit probe is not needed now. Preserve failed loading/OOM runs and the A367 host-pressure evidence; memory fit is unresolved.

The certified FP8 result remains **46.854250 tok/s**, with its exact identity and gates in the [closeout](results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md), [handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md) and [reproduction
guide](repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md). Reopening diagnostics and CPU preparation do not replace that record.

## LTX Continuing Video

The recorded production arm is **137, stopped under the halt above**. Packet **138 is sealed and CPU-tested; native qualification is pending**. Its scheduled text prefetch is off by default, compares unchanged conditioning when produced and consumed,
and predicts 0.095 seconds/chunk saved without a native measurement. It retains at most 1.3125 MiB extra CPU conditioning; overlap and memory peaks remain unmeasured. See the [design](notes/2026-10-10-continuation138-stream-design.md), [build
receipt](experiments/ltx25-b70/data/resume-20261008/continuation138-build.json) and [coordinator launch packet](experiments/ltx25-b70/recovery/20261010-continuation138-stream/LAUNCH.md).

The continuing-video line uses 256×256, 145-frame chunks with 144 new frames (six seconds). For packet 135 GC-10, the first uninterrupted 52 periods had a **5.2415 s median**; the whole 747-period session had a **5.553 s raw median** affected by
client pacing. Neither the short prefix nor the later hold-free diagnostic establishes sustained unthrottled speed. [Corrected metric ledger](results/ltx25-continuation-stream-pacing-2026-10-10.md).

The goal remains coherent continuing video faster than playback, then higher resolution. Preserve the accepted short-window text-encoder reference (`stability-01-w93c-*`, `experiments/ltx25-b70/data/stability-01-window-prereg.json`) and exact
continuation lineage. Do not blend it with padded-encoder or other output-changing baselines. Unaccepted soft-latent, mixed or guide-anchor alternatives remain separate.

The **9 GiB device floor, 5 GiB capture reserve, 0.75 GiB screening band and 50 GiB disk reserve** remain in force. Preserve the full snapshot schedule; the optional reduced `a-xpu3-sync` barrier still needs owner acceptance. The latest larger-chunk
screen permits considering 169 frames with graphs off, but it was not launched and predicts no gain; larger graph arms remain unqualified.

Owner seam/audio acceptance and portable public runtime reconstruction plus independent replay remain open. The [public recipe](repro/ltx25-continuation-stream-b70-145f-20261010/README.md) records these limits. Packet 138 and any relaunch wait for
the host halt decision and their own admission; old streaming requests do not erase those gates.

Preserve `/home/steve/src/ComfyUI-ltx25-baseline`, `/home/steve/.venvs/ltx25-baseline`, `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`, `/home/steve/ltx-stream/`, all reference/unique captures, negative runs, manifests and restore receipts.
Approved duplicate retirements are recorded in lane notes; a later full proof must restore the required ordinary-copy layout first.

## Our Own Intel Xe Runtimes

The October 10 [objective](docs/own-xpu-runtime-objective.md) is our own model-specific code. Other projects supply credited ideas, not a code base. Official-publisher or Unsloth weights are permitted; another source needs written justification and
owner approval. The earlier ISTA IQ3_S proposal is withdrawn. These CPU packets do not qualify a native runtime or authorize a GPU window.

- **27B stage 1:** [identity packet 1](experiments/own-xpu-runtime/stage1/packet1/README.md) freezes tokenizer requirements, twelve saved answers and 1,606 tensors. [Packet 1b](experiments/own-xpu-runtime/stage1/packet1b/README.md) adds synthetic CPU
  arithmetic/readers. [Packet 2](experiments/own-xpu-runtime/stage1/packet2/README.md) checks the existing official USB weights: 67 large-file hashes, 14 small publisher files and repeated CPU samples. Text plus MTP requires 29.945 GB with on-card
  embedding; actual one-card fit is unproven.
- **Native preparation:** [packet 3](experiments/own-xpu-runtime/stage1/packet3-prep/README.md) tests memory ownership with mocks and compiles, but does not run, SYCL. Attention gating is corrected to sigmoid. [Packet
  4](experiments/own-xpu-runtime/stage1/packet4-prep/README.md) maps 44 source boundaries and tests synthetic capture; the native worker and internal-state bindings remain incomplete. A367 used a host environment whose extension differs from the
  reopen image; no certified image has been established.
- **Fixture-window blockers:** the [memory admission review](experiments/own-xpu-runtime/stage1/packet4-prep/MEMORY-ADMISSION-REVISION.md) derives a **133,542,784 KiB floor**, above current capacity; no lower passing floor is justified. Eighteen
  certified kernel files match, but a historical model-receipt hash mismatch and the host halt also block the [planned 60-minute Flash-only window](experiments/own-xpu-runtime/stage1/packet4-prep/WINDOW-RUNBOOK.md). Any admission revision needs the
  driver's document-bound owner receipt.
- **Flash-Next stage 2:** [packet 1](experiments/own-xpu-runtime/stage2/packet1/README.md) freezes official tensor identity and twelve certified answers; the two-card official-weight plan needs about 65 GB of experts off-device before workspace.
  [Packet 1b](experiments/own-xpu-runtime/stage2/packet1b/README.md) passes synthetic CPU math/repeats, preserving Flash's BF16 inter-row state versus 27B's FP32 state; device parity remains unverified. The
  [plan](experiments/own-xpu-runtime/STAGE2-PLAN.md) separates calculated bandwidth from measured speed.
- **Separate quantized compressed version:** Unsloth UD-IQ3_XXS has its own [lane/CPU packet](experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md). All three file hashes, tensor census and fresh-process sampled CPU repeats now pass,
  superseding the incomplete-download note. Packed target weights require **53.305 GB across two cards** with large lookup tables off-device; fit, complete-model answers and speed remain unmeasured. Next: its tokenizer/operator oracle. The [pinned
  llama.cpp measurement baseline](experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/README.md) builds for B70 and passes CPU help/version; its proposed target-only twelve-prompt, two-fresh-process run uses full 16-bit KV and still needs
  native admission.
- **Identity boundary:** IQ3 must be lossless and deterministic against its own bytes and CPU dequantization oracle; FP8 differences are informational, not a tolerance gate. Never call it the FP8 model or compare it as the same record. The [Unsloth
  header census](experiments/own-xpu-runtime/stage2/packet1c/README.md) finds no extra MTP block in the three checked variants; packed-weight arithmetic alone does not establish runtime fit. Other variant acquisition, quality and device work remain
  separately gated.

## Two-Card Lanes And Context Work

**Qwen 27B FP8:** optimize the official FP8 model with native MTP and full 16-bit KV; DFlash stays excluded by the September 14 owner decision. Read the [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md), [closed
experiments](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) and [TP2 recipe](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) before runtime changes.

The October 7 public-package acceptance passes short and 2K–8K long prompts at 16/32/64 users, two passes exact to the single-user answers. **875 tok/s is aggregate short-prompt throughput at 64 users**, not a single-user or all-workload rate. The
same acceptance session recorded a 90.31 tok/s recommended-profile median. Evidence: `experiments/qwen38-27b-b70/data/2026-10-07-fp8-two-card-multi-user/`. Clean-host qualification and multi-user drafting (R314, local only) remain open.

**MiniMax-H3:** the October 10 owner decision accepts **Comfy-Org's pruned BF16 denoiser with fitted AdaLN**, including that source as an explicit exception to the source rule. The lab analyzed this published file; it did not produce the fit. The
fit-search/redownload queue is superseded. The [draft package and recipe](repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md) targets turin, two B70 and 15 GiB RAM.

The measured eight-clip batch is **396.6 seconds/clip**, with 32 matching hash checks and eight repeat passes against this denoiser's own reference. That exact scheduling result is not losslessness versus the official model. The older 800.8 s/clip
baseline is ledger-only, with raw receipts not retained. Publisher input pins are checked; baseline/reference receipts, clean build/runtime, independent full-suite repeat and portable release evidence remain missing. Turbo LoRA and other changed
arithmetic stay separate. H3 GPU work must use `experiments/minimax-h3-b70/scripts/smoke_h3.sh` and its memory watchdog.

**Context/retention:** October 8 owner rule: decide studies within a few hours using pilots/concurrency/early stops; no more full-day soaks. The [LongMemEval stage-2 result](experiments/qwen38-27b-b70/notes/2026-10-08-longmemeval-stage2-result.md)
recommends archive-and-recall within 32K for that study; the 27B self-judge is secondary evidence, and abstention is the next weakness. Do not turn this into a general memory or speed claim.

For the two short controlled documents, [direct full-source reading](experiments/qwen38-27b-b70/notes/2026-10-07-full-source-screen-result.md) got 24/24 on each in one cold request; this is a static final-answer comparison, not an intermediate-state
or general speed guarantee. The [history study](experiments/qwen38-27b-b70/notes/2026-10-07-history-state-study-result.md) failed on ownership joins despite exact numeric checkpoints. Preserve its archive inventories and failed revisions 3/4; keep
t03/t04 and the other held-out rows unused. Do not reopen short-document interface tuning; new work needs a concrete streaming/audit requirement or relevant independent history, as the [research
priorities](experiments/qwen38-27b-b70/notes/2026-10-07-context-research-priorities.md) specify.

[Project decision recall](experiments/project-decision-recall-20261007/RESULTS.md) covered 38/38 criteria by ordinary search/read; complete-source delivery missed one caveat (37/38). These were hosted assistant sessions over curated records, not a
local-model qualification. No structured memory store or worker integration is admitted. The [local worker scoped attempt](experiments/local-coding-worker/scoped-task-20261007/CLOSEOUT.md) made no edit or accepted submission; preserve prior failed
worker/recall trials and five unused tasks. Further worker tuning/integration is parked.

## Known Issues And Next Actions

1. **Owner decision dated October 10:** resolve the four-card third-incident halt; only then admit the bounded Flash loading check or LTX native/relaunch work. CPU analysis, documentation and existing receipt review can proceed.
2. Finish the CPU runtime tokenizer/operator and adapter work, retaining the fixture memory-floor, receipt and native-window blockers above. Keep H3's missing publication evidence explicit; its source acceptance is already resolved.
3. Keep each certified result under its exact model, weights, arithmetic, topology, metric and quality identity. Preserve historical high scores and negative patches; host/session drift does not by itself justify merging different benchmark
   identities or lowering a record. Consult the [reproducibility map](docs/current-reproducibility-map.md), [effort index](docs/model-effort-index.md) and [scoreboard](results/scoreboard.md).
4. The GDN PR #45 community contribution still needs its actual mixed-session soak before production promotion; shorter strict-oracle passes do not verify that incident. Historical replay hash mismatches remain evidence, not permission to repin
   shared tools blindly. Follow the [replay audit](notes/2026-09-09-replay-and-validator-audit.md).
5. ML Bottleneck automatic refresh stays paused: 4070 interpretation, nine ambiguous measurements and calibration thresholds block publication in that repository's `docs/refresh-review-2026-09-08.md`. Keep its published evidence unchanged. Duplicate
   LocalMaxxing record `cmu6ytvxr082alq015dpjgiz4` remains flagged for owner-only withdrawal; canonical record is `cmu6ytqyr0827lq01b76whp6d`.
6. A reproducible package needs pinned inputs, a clean build, unchanged quality gates and graceful teardown, with the public asset/replay checks required by [AGENTS.md](AGENTS.md). An older runnable command, CPU test pass or accepted model choice
   does not satisfy missing gates.

## Storage And Recovery

Retain the **50 GiB free-space reserve** and admit the peak temporary writes before creating archives or copies with `scripts/check-storage-headroom.py`; old free-space numbers are not admission. Verify current capacity, mount identity and ownership
before new model downloads. Do not do bulk reads of the protected external trees during this documentation cleanup.

Cache archives live under `/home/steve/git-archives/cache-consolidation-20261006/`; eight inactive staging builds are archived under `/home/steve/git-archives/staging-consolidation-20261007/` and need restoration before old launchers work. Keep
`data/maintenance/consolidation-20261006/summary.json` and `data/maintenance/staging-consolidation-20261007/summary.json`, with their inventories, hashes and restore instructions.

The selected research/Git backup is `/mnt/usb-models/lab-backups/steve-b70s-20261007/` (nine verified archives, selected source only, not a whole-machine backup). Preserve `/home/steve/git-archives/flash-next-rescue-20261007/`,
`/home/steve/worker-container-controls-20261007/`, and the official 27B cold copy `/mnt/usb-models/worker-models/qwen38-27b-fp8-20261007/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a/`. This page does not assert the USB disk's current mount state. It is
cold backup storage, not an active model-serving path; no force, repair/reinitialization or SMART bridge passthrough.

Preserve source/build deltas, unique outputs, anchors, failure/coredump/OOM evidence, model/cache inventories, quarantined damaged LTX files, rejected/partial downloads and restore maps unless their exact disposition has been independently
established. In particular retain `/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914/FAULT.json` and all four stages, and `/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914` with its stopped incident container. A compressed archive or Git
history does not by itself demonstrate recoverability of ignored artifacts.

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: preserved source/build used by the inactive Muse fleet;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2`: accepted Qwen3.8 Q4_K_M source at
  `a4349bcee`; preserve its intentional three-file uncommitted fusion delta;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1`:
  accepted oneAPI 2026.1.1 BMG-G31 AOT build;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/`: accepted Qwen3.8 GGUF targets and MTP sidecars;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/`: official FP8 artifact retained for the separate vLLM lane;
- `/mnt/fast-ai/bench-results/qwen38-official-fp8-vllm-xpu-20260816/`:
  official FP8 eager/graph/P2P controls, final quality gate, cache-zero result,
  runtime capture, and post-run health evidence;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`: native/FP8 KV,
  semantic quality, MTP runtime-dtype, Q8/Q4 controls, and reset-window evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
- `/mnt/fast-ai/src/llama.cpp-q38-tp2-distributed-greedy-directq8`: closed
  exact distributed-argmax candidate; preserve for mechanism reuse only;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-distributed-greedy/`:
  position-balanced reasoning-off controls/candidates and exact output oracle;
- `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`: prior accepted Qwen TP2 source; preserve as control;
- `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/`: accepted Qwen model;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion/`:
  promoted Qwen evidence and bounded negatives;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps/`:
  Qwen pass-1/pass-2 evidence and current clean result;
- `experiments/qwen27_graphsafe_flash_attention/`: graph-safe INT4 source and
  generated research state;
- `experiments/qwen36-27b-autoround-int4-b70/`: INT4/MTP research packet and
  diagnostic artifacts.

Large ignored Qwen artifacts may be archived only after a complete inventory,
hash verification, and a recorded restore path. Never use broad `git clean` or
delete tracked experiment material to make the tree look tidy.

## Additional Preserved Work And Operational Guards

Preserve the pre-existing dirty files; inspect their status before editing:

- `experiments/qwen38-27b-b70/scripts/context/second-comparison.sh`
- `experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py`
- `experiments/qwen35-9b-b70/probes/drift-reproduction.py`
- `experiments/qwen35-9b-b70/scripts/analyze-admission-composition.py`
- `experiments/qwen35-9b-b70/scripts/run-20260908-drift-reproduction.sh`

The prior ledger also protects the dirty Flash-Next source tree; do not reuse or modify it for the Qwen3.8 R50 review. Root-NVMe/BIOS work remains paused: no bulk reads/scans of `/mnt/fast-ai` or `/mnt/usb-models`; do not start
`generate-q38-root-nvme-link-clearance-v1.py` or any `w13`/`hc` runner. Do not run process-search commands containing `w13-m1-xpu-graph-gate.py` or the A2 result path: frozen health checks can mistake the search itself for a surviving runner.
Preserve the [archived ownership notice](CURRENT-history-20260909.md#immediate-manager-actions) and its exact frozen-runner paths.

Power settings are off limits, including restoring old values. Host memory/swap/page-cache changes and reboot require owner authorization; do not alter any approved workaround as cleanup. On the four-card host, blocks **53–57** remain offlined by
`b70-offline-bad-memory.service`; RAM replacement is deferred for 2026. The approved deepest-idle-state and lockup-panic settings are recorded in the [stability guide](docs/host-stability-and-fault-diagnosis.md); old September statements that the
mitigation was absent are historical.

On turin retain approved `vm.swappiness=1`, earlyoom, disabled automatic kernel/GPU-firmware upgrades, and kernel `7.0.0-38` with `7.0.0-31` fallback. Only one memory-heavy job at a time on its 15 GiB host, never beside a build container. Do not
start another job close to an active server's memory-guard floor.

Follow [AGENTS.md](AGENTS.md) for main-only Git, secrets, graceful GPU shutdown, first-fault evidence and bounded health checks, strict lossless gates and full 16-bit KV. All superseded results and historical incidents remain available in the
[verbatim October ledger](CURRENT-history-20261010.md); archiving them does not retire protected work or grant operational permission.
