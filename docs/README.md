# B70 Optimization Lab Docs

This docs folder is the navigation layer for a multi-model Intel XPU
optimization lab. Classified reproduction artifacts live under `../repro/`, promoted or
closed-out model packets live under `../results/`, active research lanes live
under `../experiments/`, and chronological evidence lives under `../notes/`.
Docs should point to those artifacts instead of duplicating every script.

## Start Here

- [Current Workspace State](../CURRENT.md): authority for recorded host state, active work, protected artifacts, and immediate next actions.
- [Model Effort Index](model-effort-index.md): cross-model status, completed experiment arms, and lane entry points.
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
- [Single Model Slot Switching](model-slot-switching.md): historical service procedure; current launch permissions come from AGENTS.md and CURRENT.md.
- [Model Intake Queue](../model-intake/README.md): revision-pinned candidate
  downloads, USB safety checks, popularity snapshot, and already-covered
  families that should not be duplicated.
- [long-horizon-context-program.md](long-horizon-context-program.md) — the long-horizon context problem (weeks-long agents, 1M-10M histories, live cap 200K): every idea tried, proposed and seen, engine constraints (hybrid GDN / SWA state), and the benchmark design to compare solutions (2026-10-10).
- [Own Model-Specific Runtimes For Intel Xe](own-xpu-runtime-objective.md):
  the 2026-10-10 long-running objective, its rules (own project, official or
  Unsloth weights, B70 only), design pillars and staged gates.
  [Stage 0 design, inventory, idea survey and storage plan](../experiments/own-xpu-runtime/README.md)
  include the first ten packets for the one-card 27B decode core.
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
- [Qwen3.6 27B INT4 AutoRound Result Packet](../results/qwen36-27b-autoround-int4-b70/README.md): historical TP1/TP2 vLLM/XPU results, long-context service ladder, closed no-win paths, and the newer strict-fail classification. The [standalone historical repro](../repro/qwen36-27b-autoround-int4-b70/README.md) includes the exact private source bundles, dirty patches, model/runtime manifests, and original run evidence; the [independent validation](../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md), [dependency closeout](../notes/2026-08-17-qwen36-int4-input-dependency-closeout.md), and [RMSNorm closeout](../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md) preserve the validation history. The [August 18 determinism and speed account](../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md) records the later conclusion and suite-composition correction.
- [Qwen3.8 27B INT4 AutoRound Research Lane](../repro/qwen38-27b-autoround-int4-b70/README.md): retained September R294b/R304 MTP4 qualification, per-runtime concurrency profiles, and their limits. Its research-status recipe preserves earlier invalidated rows and oracle corrections; it does not establish a live deployment.
- [Flash-Next final campaign results](../results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md): approved 46.854250 tok/s exact-GDN MTP1 record, repeated 32K depth evidence, and updated [recipe](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md).
- [Qwen3.8 Flash-Next FP8 Research Snapshot](../repro/qwen38-flash-next-fp8-tp4-mtp3-b70/EXPERIMENTAL-SNAPSHOT-20260831.md): four-B70 125B-A6B ongoing-work preview, exact model/source/runtime reconstruction map, 20.727 tok/s short MTP4 screen, preferred 15.502 tok/s exact-4K MTP3 profile, and the explicit non-runnable/LocalMaxxing-withheld boundary.
- [Qwen3.6 Family Research Map](qwen36-research-map.md): consolidated navigation for the 27B Q8, INT4/MTP, Q4/DFlash, FP8, and 35B Quark identities.
- [Qwen3.6 35B Quark INT8 Result Packet](../results/qwen36-35b-quark-int8-b70/README.md): best valid 2x/4x results, invalid fast lanes, reproduction commands, and carryover lessons.
- [DeepSeek V4 Flash Investment Plan](../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md): gated four-B70 vLLM/XPU bring-up, exact-shape kernel tests, K160-first capacity selection, and quality controls.
- [DeepSeek V4 Flash K160 Result Packet](../results/deepseek-v4-flash-k160-b70/README.md): paused-lane 80.820 tok/s target-verified record, standalone pinned repro, source bundles, validity caveats, and reopen conditions.
- [MiniMax M2.7 INT4 on 4x B70, Ubuntu 24](b70-minimax-ubuntu24-deployment.md): historical expert deployment candidate; review its mutable system dependencies before use.
- [MiniMax C1 Service Recipe](minimax-production-c1-service.md): historical 32K service setup, health checks, and benchmark procedure.
- [Gemma 4 12B INT4 AutoRound profile](../experiments/gemma4-12b-int4-autoround-vllm/README.md): recorded deployment and research profiles; consult the lane status before reuse.

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
- [Host Stability And Fault Diagnosis](host-stability-and-fault-diagnosis.md): how a four-B70 host's freezes split into faulty non-ECC memory, one unresponsive GPU, an idle-state bug and a debugging setting; counts, commands and the runtime memory fence.
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

The lab works on two hosts: a two-B70 system with 15 GiB of host RAM and a
four-B70 system with 128 GiB. Results retain their original hardware identity;
card count, host memory and topology can change what fits and how it performs.
[AGENTS.md](../AGENTS.md#host-facts) records host facts and standing rules;
[CURRENT.md](../CURRENT.md) records the latest known work and restrictions.

## How To Help

The best help is evidence that is easy to reuse: exact commands, driver/runtime
versions, model identity, quality checks, logs, and negative results. This
project has already turned B70 runs into LocalMaxxing submissions, X discussion,
GitHub-indexed troubleshooting, and reusable vLLM/XPU and llama.cpp notes. To
increase the number of optimized models, the highest-leverage additions are
more independent Intel test systems, larger-VRAM Intel devices, clean
driver/runtime repros, and help turning local findings into upstream issues or
patches.

<a id="deployable-baselines-and-current-frontiers"></a>
<a id="minimax-32k-deployable-endpoint"></a>
<a id="qwen36-35b-reference-packet"></a>
<a id="qwen36-27b-int4-autoround"></a>
<a id="qwen36-27b-q8_0-gguf"></a>
<a id="gemma-4-26b-short-decode-and-service-lanes"></a>

## Finding Results And Lessons

Use the [model effort index](model-effort-index.md) to find each lane, the
[result packets](../results/README.md) for measured outcomes and caveats, and
the [reproducibility map](current-reproducibility-map.md) for exact recipes.
Those records own the performance numbers; this navigation page does not keep
another copy. Historical service recipes describe how a setup was operated,
not permission to start it or evidence that it is running today.

The [research workflow playbook](research-workflow-playbook.md) collects
transferable lessons. Each lane's handoff and negative-result ledger preserve
model-specific failures, rejected patches and conditions for revisiting them.
[Notes](../notes/README.md), [patches](../patches/README.md) and
[data](../data/README.md) retain the supporting history.

For source-backed retrieval, use the existing
[lab navigator](../tools/lab_navigator.py) and
[evidence reader](../tools/lab_evidence.py). Their indexes bind passages to a
Git revision; rebuild after changes, and follow citations for caveats. Search
indexes deliberately exclude some raw evidence and are not cleanup inventories.
The [repository cleanup record](../audits/repository-cleanup/README.md) records
coverage, dispositions, integrity checks and material still awaiting review.

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
- keep CURRENT.md a short state snapshot; put dated chronology in lane notes or linked history.
- avoid copying headline numbers into navigation pages; link the authoritative result and its identity.
- do not expand the top-level README with every run. Promote summaries into
  `results/`, `repro/`, `experiments/`, `notes/`, `patches/`, and `data/`.
