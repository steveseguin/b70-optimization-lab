# B70 Optimization Lab Docs

This docs folder is the navigation layer for a multi-model Intel XPU
optimization lab. Classified reproduction artifacts live under `../repro/`, promoted or
closed-out model packets live under `../results/`, active research lanes live
under `../experiments/`, and chronological evidence lives under `../notes/`.
Docs should point to those artifacts instead of duplicating every script.

## Start Here

- [Current Workspace State](../CURRENT.md): sole authority for the live service, active lane, protected work, and immediate next actions.
- [Model Effort Index](model-effort-index.md): cross-model status, closed lanes, and where to put the next model packet.
- [Model Optimization Guide](model-optimization-guide.md): start-to-finish guide for an AI agent optimizing a new model lane.
- [Research Workflow Playbook](research-workflow-playbook.md): reusable prompts, validation ladders, and experiment discipline that produced the best outcomes.
- [Reproducibility Map](current-reproducibility-map.md): stable promoted reproduction catalog; `CURRENT.md` owns live state.
- [Results Index](../results/README.md): promoted model-specific result packets and how to promote a lane.
- [Model Recipes](model-recipes.md): which recipe folder to use for each model/build target.
- [Reproduction Guide Certification](reproduction-guide-certification.md):
  starter, candidate, lab-replay, record, research, and archive definitions;
  no current repro is starter-certified.
- [Model Packages](../packages/README.md): user-facing machine-readable package
  front doors for promoted deployment and research recipes.
- [Model Family Coverage](../families/README.md): normalized lineage,
  quantization variants, TP/MTP/context axes, and explicit
  measured/screened/closed/estimated coverage states behind the public model
  family pages.
- [Single Model Slot Switching](model-slot-switching.md): keep one LAN OpenAI endpoint while switching which large model is loaded.
- [Model Intake Queue](../model-intake/README.md): revision-pinned candidate
  downloads, USB safety checks, popularity snapshot, and already-covered
  families that should not be duplicated.
- [Model Distribution And Packaging Roadmap](model-distribution-and-packaging-roadmap.md):
  novice one/two-GPU packets, contributor recognition, digest-pinned Docker
  packaging, and the bounded Windows path.
- [Intel Arc Pro B70 ECC And Usable VRAM](b70-ecc-and-vram.md): check,
  disable, or re-enable ECC on Linux and Windows; understand the verified
  capacity gain, reliability trade-off, and benchmark-disclosure boundary.

## Model Lane Entry Points

- [Muse-Glimmer-30B Q8/WOQ Result](../results/muse-glimmer-30b-q8-woq-b70/README.md): closed four-B70 no-training record, LocalMaxxing approval, validity boundary, exact source bundle, raw evidence, and standalone replay.
- [Muse-Glimmer-30B Standalone Repro](../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md): rebuild from the public llama.cpp base, verify model/evidence hashes, and rerun the canonical and cold realistic gates.
- [Laguna S 2.1 Result Resume](../experiments/laguna-s-2.1-xpu-b70/RESUME.md): historical sealed repro plus the current exact four-B70 M12 shared-elementwise record at historical 126.729 / conventional 125.462 tok/s.
- [Laguna S 2.1 Qualified Result Packet](../results/laguna-s-2.1-int4-b70/README.md): promoted identity, qualification, evidence, patches, and LocalMaxxing receipt.
- [Laguna S 2.1 125 tok/s Standalone Repro](../repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md): exact source bundles, binary/runtime lock, formal command, and first-valid cold gate.
- [Laguna Metric Accounting Correction](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md): the 100-event versus 99-interval finding, impact, and prevention rule.
- [Laguna Standalone Repro](../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md): fail-closed source/runtime restoration, historical-receipt audit, and one-cold-suite replay.
- [Laguna Campaign Transfer Ledger](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-campaign-transfer-ledger.md): condensed wins, losses, correctness failures, graph lessons, and harness rules for future models.
- [Laguna KV-Cache Precision Decision](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-kv-cache-precision-decision.md): why the exact record uses BF16 although the official quantized checkpoint specifies calibrated FP8 KV.
- [Gemma 4 26B Handoff](../results/gemma4-26b-a4b-q8-b70/HANDOFF.md): one-B70 Q8/INT8-quality production backend, speed frontier, resume bookmark, and next-work assessment.
- [Gemma 4 26B Q8 Service Runbook](gemma4-26b-q8-service-runbook.md): restore or stop the temporary llama.cpp OpenAI endpoint on one or four B70 GPUs.
- [Gemma 4 26B Result Packet](../results/gemma4-26b-a4b-q8-b70/README.md): detailed one-B70 speed frontier, long-context service lane, validity notes, and LocalMaxxing context.
- [Qwen3.6 27B INT4 AutoRound Result Packet](../results/qwen36-27b-autoround-int4-b70/README.md): historical TP1/TP2 vLLM/XPU results, long-context service ladder, closed no-win paths, and the newer strict-fail classification. The [standalone historical repro](../repro/qwen36-27b-autoround-int4-b70/README.md) includes the exact private source bundles, dirty patches, model/runtime manifests, and original run evidence; the [independent validation](../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md), [dependency closeout](../notes/2026-08-17-qwen36-int4-input-dependency-closeout.md), and [final RMSNorm closeout](../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md) are the current verdict.
- [Qwen3.8 27B INT4 AutoRound Active Lane](../repro/qwen38-27b-autoround-int4-b70/README.md): current vLLM/XPU MTP5 setup, invalidated margin-assisted rows, fresh margin-free target oracle, post-recovery TP2 replicas, and the positive sealed-cache TP1 INT4 prefill-pad causal screen.
- [Qwen3.8 Flash-Next FP8 Research Snapshot](../repro/qwen38-flash-next-fp8-tp4-mtp3-b70/EXPERIMENTAL-SNAPSHOT-20260831.md): four-B70 125B-A6B ongoing-work preview, exact model/source/runtime reconstruction map, 20.727 tok/s short MTP4 screen, preferred 15.502 tok/s exact-4K MTP3 profile, and the explicit non-runnable/LocalMaxxing-withheld boundary.
- [Qwen3.6 Family Research Map](qwen36-research-map.md): consolidated navigation for the 27B Q8, INT4/MTP, Q4/DFlash, FP8, and 35B Quark identities.
- [Qwen3.6 35B Quark INT8 Result Packet](../results/qwen36-35b-quark-int8-b70/README.md): best valid 2x/4x results, invalid fast lanes, reproduction commands, and carryover lessons.
- [DeepSeek V4 Flash Investment Plan](../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md): gated four-B70 vLLM/XPU bring-up, exact-shape kernel tests, K160-first capacity selection, and quality controls.
- [DeepSeek V4 Flash K160 Result Packet](../results/deepseek-v4-flash-k160-b70/README.md): paused-lane 80.820 tok/s target-verified record, standalone pinned repro, source bundles, validity caveats, and reopen conditions.
- [MiniMax M2.7 INT4 on 4x B70, Ubuntu 24](b70-minimax-ubuntu24-deployment.md): historical expert deployment candidate; review its mutable system dependencies before use.
- [MiniMax Production C1 Service](minimax-production-c1-service.md): run the 32K MiniMax endpoint under systemd with health and benchmark checks.
- [Gemma 4 12B INT4 AutoRound profile](../experiments/gemma4-12b-int4-autoround-vllm/README.md): current model-slot production profile and related research profiles.

## Community And Operations

- [Contribution Guide](../CONTRIBUTING.md): submission expectations and the
  required benchmark/result identity.
- [Contribution Verification](contribution-verification.md): manual evidence
  and hardware-verification policy.
- [Community Contributions](../community/README.md): where outside work lands,
  and what has to happen before it enters the promoted ledger.
- [Reference Lab Storage Layout](reference-lab-storage.md): what the
  `/mnt/fast-ai/...` and `/mnt/usb-models/...` paths throughout this repo mean.
  Read this first if a recipe points somewhere that does not exist on your
  machine.
- [Performance Index](../results/scoreboard.md): expected performance with
  explicit comparison and verification boundaries.
- [Manager Playbook](../MANAGER.md): manual human/AI review procedure.
- [Experimental Disclaimer](../DISCLAIMER.md): use and benchmark risks; the
  repository `LICENSE` remains controlling.
- [FAQ](faq.md): practical answers for users new to B70s, vLLM, XPU, and local model deployment.
- [GPU Comparison for Local AI](gpu-comparison-local-ai.md): rough pricing/spec/performance framing for B70s versus common alternatives.
- [PCIe Topology And Local-LLM Inference](pcie-topology-and-llm-inference.md): what Gen3, narrow slots, Thunderbolt, and multi-GPU fabrics can change; measured B70 examples and topology checks.
- [Community Results And Build Notes](community-results.md): how to share records, build photos, reproducible logs, and discussion links.
- [LocalMaxxing Submissions](localmaxxing.md): credential location, submit helper, and secret-handling rules.
- [Local Operations](local-ops.md): sudo-password location, driver/runtime ops guidance, and Claude/OpenCode-to-Codex delegation.
- [Feedback for Intel](feedback-for-intel.md): short discussion guide plus the detailed Intel feedback note.

## Build Photos

The community build guide includes example B70 photos and explains what details future contributors should capture: card spacing, airflow, power, slot order, risers, cooling, and visible diagnostics.

- [Community build photos and result format](community-results.md#build-photos)

## Repository Layout

- `docs/`: narrative guides, FAQ, community-facing summaries, comparison notes.
- `repro/`: classified candidates, lab replays, records, research status, and archives; see [`../repro/guide-catalog.json`](../repro/guide-catalog.json).
- `packages/`: user-facing manifests and concise entry points over verified in-repository dependencies.
- `results/`: promoted result packets and closed-out model efforts. See [../results/README.md](../results/README.md).
- `notes/`: lab notebook entries, including negative results. See [../notes/README.md](../notes/README.md).
- `data/`: structured benchmark records, payloads, and LocalMaxxing responses. See [../data/README.md](../data/README.md).
- `patches/`: patch records and source-level optimization deltas. See [../patches/README.md](../patches/README.md).
- `scripts/`: shared harnesses used by repro folders and lab runs.
- `model-intake/`: curated model discovery, immutable artifact identities, and
  the external-store download queue.
- `experiments/`: active research lanes that are not production recipes yet.
- `prompts/`: quality canaries and reusable prompt templates. See [../prompts/README.md](../prompts/README.md).

## Community Links

- Maintainer/site: https://steveseguin.com
- X feed with ongoing build notes: https://x.com/xyster
- LocalMaxxing profile/results: https://localmaxxing.com/user/steveseguin
- LocalMaxxing submission credentials and helper: [localmaxxing.md](localmaxxing.md)
- Project pages timeline: https://steveseguin.github.io/llm-optimizations/optimization-timeline.html

## Hardware Coverage

This lab currently has four Arc Pro B70 32 GB GPUs, so the total local Intel
VRAM budget is `128 GB` and every card is often occupied by active optimization
runs. That is a useful community baseline, but it also means larger model
families, larger context windows, and concurrent A/B lanes wait behind the same
four devices. Additional high-VRAM Intel hardware, including
Crescent Island-class `160-480 GB` evaluation devices if available, would turn
many of the open vLLM/XPU and driver/runtime questions here into directly
measurable lanes rather than capacity-constrained TODOs. There is also spare
EPYC 9015 platform capacity with up to ten PCIe 5.0 x16 slots, so larger Intel
GPU coverage would have an immediate place to land.

## How To Help

The best help is evidence that is easy to reuse: exact commands, driver/runtime
versions, model identity, quality checks, logs, and negative results. This
project has already turned B70 runs into LocalMaxxing submissions, X discussion,
GitHub-indexed troubleshooting, and reusable vLLM/XPU and llama.cpp notes. To
increase the number of optimized models, the highest-leverage additions are
more independent Intel test systems, larger-VRAM Intel devices, clean
driver/runtime repros, and help turning local findings into upstream issues or
patches.

## Deployable Baselines And Current Frontiers

There are multiple useful "current" paths depending on the task. Treat these as
entry points, not a single global winner.

### MiniMax 32K Deployable Endpoint

The clean "start from Ubuntu 24 and serve on the LAN" baseline is:

- Recipe: `../repro/minimax-m27-b70-110tps-ubuntu24-20260523/`
- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- API: no-auth OpenAI-compatible LAN frontdoor on `0.0.0.0:8000`
- Served context: `32768` tokens by default
- Production services:
  `../deploy/systemd/minimax-vllm.service` and
  `../deploy/systemd/minimax-openai-frontdoor.service`
- Quality: strict token-hash and semantic gates passed
- Throughput observed on 2026-05-23: `110.90` total tok/s, `83.17` output tok/s for p512/n1536
- OpenAI endpoint warm check: about `83.8` output tok/s and `1.7k-1.8k`
  prompt/prefill tok/s
- Original install snapshot commit before this context-window update: `b02ad184553a5ef4e3946a94b8e6124980bc369f`

The served endpoint was also validated at prompt 32,408 / output 64 without OOM,
and warm short decode stayed near `84.1` output tok/s afterward. The older strict
speed record and newer constrained structured-output lane remain useful
references, but they were measured on different conditions. The current host's
PCIe4 fabric measured about half the old large-message allreduce bandwidth,
which is a plausible reason this fresh deployment lands at `83` output tok/s
instead of the older `89-93` class. See
`../notes/2026-05-23-current-host-pcie4-prefill-check.md` for the math.

The 32k context promotion is documented in
`../notes/2026-05-23-b70-display-disable-32768-context.md`.

The session-cache, TurboQuant, and full-context research work is indexed in
`current-reproducibility-map.md` and
`../experiments/minimax_xpu_kv_offload/REPRODUCE.md`.

### Qwen3.6 35B Reference Packet

The Qwen3.6 35B lane is indexed in
[qwen36-research-map.md](qwen36-research-map.md), with its final result packet in
[../results/qwen36-35b-quark-int8-b70/](../results/qwen36-35b-quark-int8-b70/).

### Qwen3.6 27B INT4 AutoRound

The closed Qwen27 one- and two-B70 optimization lane is indexed in
[../results/qwen36-27b-autoround-int4-b70/](../results/qwen36-27b-autoround-int4-b70/).
The historical July row is **`95.384868 tok/s`** on TP2 under its original
metric and validation bar. It uses graph-safe Intel FlashAttention to capture
one full four-row target graph plus ReplaySSM pending/direct-output transaction
fusions, and passed the original exact cases, repeat128, baseline parity, and
1K needle. It uses
the `webhie` AutoRound checkpoint, runtime INT8 target LM-head BF16 scales,
runtime INT4 draft LM-head BF16 scales, ReplaySSM exact GDN state handling,
MTP3, unique cold prompts, and `cached_tokens=0`. The pinned
public oneCCL/libccl revision fixes deterministic packed-verifier all-reduce
graph failures in the installed runtime; an opaque compiled all-gather boundary
then enables exact draft graph capture. Both swapped four-GPU crossover
assignments favored the transaction candidate. See
[the TP2 record packet](../results/qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json).
LocalMaxxing approved the `95.384868 tok/s` row as
`cmrh35ct50092mj01h7jgydqj`; the prior `93.036242 tok/s` row is
`cmrgue7kl007pmj01yrkcyqmv`.

The newer [independent six-start review](../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md)
is the current strict classification. It centered at `98.766 tok/s` across 25
prompts, but all speculative arms diverged from target-only and fresh same-pair
starts were not exact. It is not a strict pass or a robust `>100` result, and
no new LocalMaxxing row was submitted.
The exact source and run reconstruction is now self-contained in the
[standalone INT4 repro](../repro/qwen36-27b-autoround-int4-b70/README.md).
It is explicitly separate from the Q8_0 GGUF llama.cpp/SYCL lane below.
The previous one-B70 record was `68.236 tok/s` (LocalMaxxing
`cmr9atqb800msqr01u760xh0t`), and the previous BF16-scale INT8-LM-head-only
record was `65.276 tok/s`. The
service/prompt-processing lane is separate: see
[../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-ladder-baseline.md](../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-ladder-baseline.md)
for the cold long-context ladder, including the 32K-capability anchor through
`17706` actual prompt tokens with exact JSON retrieval and `cached_tokens=0`.

### Qwen3.6 27B Q8_0 GGUF

The current lane is the target-only, text-only Unsloth Q8_0 GGUF on one B70
with a 32K context ceiling. The artifact is pinned and verified on USB; the
DNN-off baseline passed the 12-prompt exact suite at `15.550 tok/s` median and
the full 32K F16-KV retrieval gate. This is not yet a full-512 localmaxxing
promotion packet. The primary next target is four independent processes with
two F16-KV 32K slots each; parallel discovery and isolated promotion are kept
as separate evidence classes. MTP, vision, and Q8-KV long context are optional
later identities, while UD-Q8_K_XL is excluded from the one-card fit target.
Start with the
[adaptive strategy](../experiments/qwen36-27b-q8-gguf-b70/STRATEGY.md) and
[experiment lane](../experiments/qwen36-27b-q8-gguf-b70/README.md).

### Gemma 4 26B Short Decode And Service Lanes

Start with the handoff and production backend recipe:
[../results/gemma4-26b-a4b-q8-b70/HANDOFF.md](../results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
and
[../results/gemma4-26b-a4b-q8-b70/production-service.md](../results/gemma4-26b-a4b-q8-b70/production-service.md).
For the temporary OpenAI-compatible Gemma 26B endpoint used by coding agents,
start from [gemma4-26b-q8-service-runbook.md](gemma4-26b-q8-service-runbook.md);
it covers both the validated four-GPU `8 x 64K` setup and a one-GPU `2 x 64K`
setup.

The Gemma 4 26B one-B70 settings are documented in
[../results/gemma4-26b-a4b-q8-b70/reproduce.md](../results/gemma4-26b-a4b-q8-b70/reproduce.md).
The standalone strict short-decode repro is
[../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/).
The older
[../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/](../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/)
folder remains useful as a standalone prior recipe, but it is superseded by
the `124.97714084813418 tok/s` fixed realistic-suite record in the Gemma
result packet. The service/prompt-processing baseline is separate from that
short record: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`, SWA left-bound,
KQ register/broadcast, phase prefill ubatch `2048`, 32K context, FA on, and
VMM. The 2026-07-02 service ladder passed all 32 long-context rows with exact
JSON validation and `cached_tokens=0`; average lane median prefill was
`1192.965 tok/s`, average lane median long-context decode was `131.786 tok/s`,
and the longest `32571` actual-token prompt stayed around `991-1006 tok/s`
prefill and `114-115 tok/s` decode. Start with
`../repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`,
`../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-current-service-context-ladder.md`,
and
`../data/gemma4-long-context-service-gate-20260702Tservice-ladder-current-rep4.json`.
Older prefill diagnostics, including KV-max scan, forced `ncols1`,
`nbatch_fa=128`, and phase-ubatch screens, remain archived under
`../experiments/gemma4-26b-a4b-q8-b70/sweeps/`.

## Writing Future Docs

When adding or refreshing docs for another model:

- make the target audience explicit: operator, optimizer, upstream developer,
  or benchmark reader;
- link to the model packet instead of copying long command blocks into several
  places;
- label active, paused, closed, superseded, invalid, and diagnostic lanes
  plainly;
- keep model-specific lessons in the model packet and cross-model lessons in
  [model-effort-index.md](model-effort-index.md) or
  [research-workflow-playbook.md](research-workflow-playbook.md);
- do not expand the top-level README with every run. Promote summaries into
  `results/`, `repro/`, `experiments/`, `notes/`, `patches/`, and `data/`.
