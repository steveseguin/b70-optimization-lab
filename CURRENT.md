# Current Workspace State

Last reviewed: **2026-09-11 15:50 UTC** (2026-09-11 11:50 EDT); the four-B70 host section below was added then.

## Authority And Update Rule

**Four-B70 host `steve-b70s`, September12:** user selected a new-model native
baseline campaign. The active task is isolated MiniCPM5-2B BF16 qualification,
not Flash-Next optimization. See [lane packet](experiments/minicpm5-2b-b70/README.md).
It uses a dedicated environment and original external-drive weights, with
exclusive locks and fresh processes; no permanent listener is planned. Preserve
the older queued lanes and all protected artifacts below. Actual running state
must still be checked before another launch.

This is the sole cross-repository authority for loaded service, active lane,
protected work, and immediate next actions. Verify Git status, relevant
processes, listeners, and the actual endpoint before operational changes.
Update this page when a service starts or stops; keep experiment chronology
in lane notes.

The [archived workspace ledger](CURRENT-history-20260909.md) preserves the
previous 4,577-line page verbatim. Its live-service statements and queued
actions are historical, span multiple hosts, and are not current instructions.

## Local Host And Active Review

**2026-09-11 (EDT):** the Qwen3.5 4B/9B and Qwen3.8 27B INT4 lanes finished the
class-consistent FP16 linear work (R290-R293 overlays, `VLLM_XPU_FP16_LINEAR_CLASSPAD`):
the R224 32-row pieces re-read the vocabulary projection once per 32 rows, 25-56% of
throughput on the 4B/9B and 3-8% on the 27B, removed losslessly. 27B package staged
on R293 (`packages/qwen38-27b-int4-fixed-k-tp2-b70`, rows R295-R298); the R293
image is built locally (`sha256:40d46730`) and awaits the GHCR push
(`repro/qwen38-27b-autoround-int4-b70/scripts/publish-r293-image-ghcr.sh`). No
containers running after 19:03 EDT; both cards passed postflight.

Host: `steve-TURIND8-2L2T`, **two B70s**. At the verification time above,
no Docker containers are running; all PR45 review servers were stopped.
Both GPUs and XCCL passed final postflight. Recheck actual process and endpoint
state before operational changes.

Target-oracle follow-up completed: both fresh compiled target-only strict tests
passed, all five comparisons were 12/12 exact, and 96 additional probes passed.
All owned containers stopped; localhost 18124 is closed and postflight passed. See
[preregistration](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/target-oracle-20260909.md).
The six-hour soak has not been started.

The active task is correctness and reproducibility review. An isolated
Qwen3.8 27B official-FP8 R50 baseline/candidate comparison completed for PR #45:
normal-suite parity passed, tiny-prompt screens failed, candidate not promoted.
The initial review model containers were stopped; both GPUs and XCCL passed
postflight. Follow-up isolated the fresh one-token GDN routing defect: the
phase-guard candidate passed 120/120 probes, two fresh compiled MTP full suites,
12/12 baseline/fresh-repeat parity and pre/post workload screens. The campaign
is complete and stopped, not a permanent service. See the
[preregistered follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-followup-plan.md).
Read the
[maintainer validation record](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/README.md)
for the candidate identity, completed tests and outstanding gates.

The previous Gemma listener and Qwen3.5 active-lane claims are superseded by
this observation. Preserve the existing Qwen3.5 work listed below. Run one
GPU lane at a time; verify endpoint and health independently of an image tag.

## Working Recipes And Candidates

- **Qwen3.8 27B FP8 TP2:** the [reproduction packet](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)
  owns the lab-qualified R187 configuration, exact-output concurrency limits
  and historical results. Its certification remains `candidate-portable-repro`;
  it is not a verified beginner setup. Consult the
  [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md) and
  [do-not-repeat index](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) before work.
- **PR #45 classifier fix:** separate R50 candidate, not promoted into the
  above recipe. Actual-source CPU checks pass against both source copies.
  Normal GPU suite passed 12/12 exact baseline/candidate parity, but both
  failed tiny-prefill screens; compilation-disabled candidate also failed.
  Sustained mixed-session validation remains unperformed; not a verified fix.
  A separate maintainer GDN phase guard fixes the local one-token symptom in
  the [bounded follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-20260909/README.md),
  but is not promoted as the contributor's incident resolution.
- **Gemma 4 26B Q8:** [result/handoff](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
  and [standalone recipe](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
  preserve the measured setup. Their existence does not mean Gemma is loaded.
- Other lane status belongs in the [model effort index](docs/model-effort-index.md)
  and [reproducibility map](docs/current-reproducibility-map.md).
  The [scoreboard](results/scoreboard.md) is historical measurement evidence,
  not service state.

## Known Issues And Next Actions

1. Before promoting the GDN local fix, run the contributor's actual mixed-session
   soak. The matched-image MTP0/MTP1 strict-oracle matrix now passes; the
   multi-hour incident remains unverified. PR #45 is merged as a community
   contribution, not a production promotion.
2. Reproduce one selected recipe end to end: pinned inputs, build, launch,
   quality gate and clean teardown. Correct defects found along that route
   before additional speed tuning.
3. Audit recent changes by affected runtime, shared harness and published
   recipe. The [September 8 review](notes/2026-09-08-targeted-correctness-cleanup.md)
   was bounded: syntax checks are not execution coverage, and commit author
   labels do not establish which model wrote a change.
4. Three promoted Flash-Next replay paths now use exact frozen verifier
   snapshots; four replay clients now stop their servers on failure. Bundle
   chains were restored and verified from the public base. See the
   [audit record](notes/2026-09-09-replay-and-validator-audit.md).
   The broader 229 historical experimental hash mismatches were not blindly
   repinned. Four-card runtime replay remains untested on this two-card host.
5. Keep ML Bottleneck automatic refresh paused. Numerical fixture tests are
   now separated from refreshed-data checks. The ingestion parser correction
   passes 94 tests and resolves the 3060 interpretation in a migration test.
   Publication still blocks on the 4070, nine ambiguous measurements and
   calibration thresholds. Published evidence remains unchanged. Details are in
   that repository's `docs/refresh-review-2026-09-08.md`.

## Other Host: Four-Card Work

MiniMax M2.7 INT4 and Flash-Next TP4 belong to the **four-B70 host**, not
this two-card machine. The [MiniMax post-reboot note](notes/NEXT-minimax-after-reboot.md)
is that host's resume packet; its remount, driver and launch instructions
must not be applied here. It records an unresolved bring-up validation after
a driver wedge, not a successful serving result. On the owning host, avoid
polling `xpu-smi` during initialization, verify the four devices and use its
bounded health checks before continuing.

Flash-Next history and accepted identities live in its
[handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md) and
[result packet](results/qwen38-flash-next-fp8-b70/README.md).
Historical reboot notices in the archive do not describe this boot.

### Four-B70 host, 2026-09-11: Qwen3.5-9B W4A16 lane closed, Flash-Next next

The Qwen3.5-9B W4A16 one-B70 lane on `steve-b70s` is closed and published: the
static depth-3 headline (113.27 tok/s) stands, and a second operating
configuration - one server for every batch size, draft depth scheduled by
batch size on three pure-Python overlays over R276 - is promoted in the
[guide](repro/qwen35-9b-w4a16-b70/README.md#one-server-for-every-batch-size-campaigns-cudynm1--cudynm1r-2026-09-11),
[package](packages/qwen35-9b-w4a16-b70/package.json) and
[performance index](results/scoreboard.md): 110.7 tok/s at one user, 1,184 at
64 users, exact through 32 users, 18/18 exact 2K-32K. The env-knob ladder for
single-user decode on this lane is exhausted (defaults optimal on every axis);
what remains is kernel work (fused INT4 draft head) recorded in the
[campaign note](experiments/qwen35-9b-b70/notes/2026-09-10-one-server-for-every-batch-size.md).
No lane container is running. The next active lane on this host is Qwen3.8
Flash-Next (its [handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md)).

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

Pre-existing dirty Qwen3.5 work at review start; inspect and preserve:

- `experiments/qwen35-9b-b70/probes/drift-reproduction.py`
- `experiments/qwen35-9b-b70/scripts/analyze-admission-composition.py`
- `experiments/qwen35-9b-b70/scripts/run-20260908-drift-reproduction.sh`

The prior ledger also protects the dirty Flash-Next source tree; do not
reuse or modify it for the Qwen3.8 R50 review. Root-NVMe/BIOS work remains
paused. Retain the existing frozen-runner guards: no bulk reads/scans of
`/mnt/fast-ai` or `/mnt/usb-models`; do not start
`generate-q38-root-nvme-link-clearance-v1.py` or any `w13`/`hc` runner.
Do not run process-search commands containing
`w13-m1-xpu-graph-gate.py` or the A2 result path: frozen health checks can
mistake the search itself for a surviving runner. See the
[archived ownership notice](CURRENT-history-20260909.md#immediate-manager-actions)
for the original guard and its recorded false positives.

Do not place new model downloads on NVMe based on an old free-space report.
Verify current capacity, mount identity and lane ownership first. Follow
[AGENTS.md](AGENTS.md) for main-only Git, secrets, runtime isolation,
quality gates and exact publication requirements.
