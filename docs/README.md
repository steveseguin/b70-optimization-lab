# B70 Optimization Lab Docs

This docs folder is the human entry point for the B70 optimization work. The executable install recipes live under `../repro/`; docs link to those folders instead of duplicating every script.

## Start Here

- [MiniMax M2.7 INT4 on 4x B70, Ubuntu 24](b70-minimax-ubuntu24-deployment.md): deploy an OpenAI-compatible vLLM endpoint.
- [MiniMax Production C1 Service](minimax-production-c1-service.md): run the current 32K endpoint under systemd with health and benchmark checks.
- [Gemma 4 26B Result Packet](../results/gemma4-26b-a4b-q8-b70/README.md): current one-B70 Q8 target plus Q4_0 MTP draft settings, optimization history, validity notes, and LocalMaxxing context.
- [Single Model Slot Switching](model-slot-switching.md): keep one LAN OpenAI endpoint while switching which large model is loaded.
- [Current Reproducibility Map](current-reproducibility-map.md): one-page map for the stable endpoint, session-cache work, TurboQuant patch, and CPU-paged attention research.
- [Model Effort Index](model-effort-index.md): cross-model status, closed lanes, and where to put the next model packet.
- [Research Workflow Playbook](research-workflow-playbook.md): reusable prompts, validation ladders, and experiment discipline that produced the best outcomes.
- [Qwen3.6 Research Map](qwen36-research-map.md): Qwen3.6-35B/B70 lane status, current decisions, and artifact pointers.
- [Qwen3.6 35B Quark INT8 Result Packet](../results/qwen36-35b-quark-int8-b70/README.md): best valid 2x/4x results, invalid fast lanes, reproduction commands, and carryover lessons.
- [Results Index](../results/README.md): promoted model-specific result packets and how to promote a lane.
- [Model Recipes](model-recipes.md): which recipe folder to use for each model/build target.
- [FAQ](faq.md): practical answers for users new to B70s, vLLM, XPU, and local model deployment.
- [GPU Comparison for Local AI](gpu-comparison-local-ai.md): rough pricing/spec/performance framing for B70s versus common alternatives.
- [Community Results And Build Notes](community-results.md): how to share records, build photos, reproducible logs, and discussion links.
- [LocalMaxxing Submissions](localmaxxing.md): credential location, submit helper, and secret-handling rules.
- [Local Operations](local-ops.md): sudo-password location, driver/runtime ops guidance, and Claude/OpenCode-to-Codex delegation.
- [Feedback for Intel](feedback-for-intel.md): short discussion guide plus the detailed Intel feedback note.

## Build Photos

The community build guide includes example B70 photos and explains what details future contributors should capture: card spacing, airflow, power, slot order, risers, cooling, and visible diagnostics.

- [Community build photos and result format](community-results.md#build-photos)

## Repository Layout

- `docs/`: narrative guides, FAQ, community-facing summaries, comparison notes.
- `repro/`: runnable install/build/benchmark/serve recipes and pinned artifacts.
- `results/`: promoted result packets and closed-out model efforts. See [../results/README.md](../results/README.md).
- `notes/`: lab notebook entries, including negative results. See [../notes/README.md](../notes/README.md).
- `data/`: structured benchmark records, payloads, and LocalMaxxing responses. See [../data/README.md](../data/README.md).
- `patches/`: patch records and source-level optimization deltas. See [../patches/README.md](../patches/README.md).
- `scripts/`: shared harnesses used by repro folders and lab runs.
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

## Current Deployable Baseline

The current clean "start from Ubuntu 24 and serve on the LAN" baseline is:

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

The Qwen3.6 35B lane is indexed in
[qwen36-research-map.md](qwen36-research-map.md), with its final result packet in
[../results/qwen36-35b-quark-int8-b70/](../results/qwen36-35b-quark-int8-b70/).

The current Gemma 4 26B one-B70 settings are documented in
[../results/gemma4-26b-a4b-q8-b70/reproduce.md](../results/gemma4-26b-a4b-q8-b70/reproduce.md).
The older
[../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/](../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/)
folder remains useful as a standalone prior recipe, but it is superseded by
the current `123.67689864739785 tok/s` fixed realistic-suite record in the
Gemma result packet. The current long-context service candidate is the
default-off SYCL FlashAttention DV512/GQA8 tile patch documented in
`../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md`;
it improves validated prefill/service shapes without replacing the UB1024
short-record reproduction. A follow-up KV-max mask pre-scan threshold
diagnostic is archived at
`../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md`;
it showed scan-off is slower, so keep the scan enabled.
The follow-up forced-`ncols1` tile-width diagnostic is archived at
`../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.md`;
it showed forced `ncols1=1` and `ncols1=4` are both slower than the current
implicit `ncols1=2` GQA8 path.
The follow-up compile-time `nbatch_fa=128` retune for that selected tile is
archived at
`../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md`;
it matched controls rather than improving them, so keep the current
`nbatch_fa=64` tile config.
The phase-specific prompt/decode ubatch source patch is archived at
`../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-phase-prefill-ubatch-service.md`;
the v2 patch is valid as a service candidate (`LLAMA_PREFILL_UBATCH_SIZE=2048`
with `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`), but it does not beat the current
short-decode record and should not be submitted to LocalMaxxing. The runnable
service wrapper is
`../repro/gemma4-26b-a4b-q8-b70/run-vdr2-gqa8-phase-prefill-service.sh`.
