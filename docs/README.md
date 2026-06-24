# B70 Optimization Lab Docs

This docs folder is the human entry point for the B70 optimization work. The executable install recipes live under `../repro/`; docs link to those folders instead of duplicating every script.

## Start Here

- [MiniMax M2.7 INT4 on 4x B70, Ubuntu 24](b70-minimax-ubuntu24-deployment.md): deploy an OpenAI-compatible vLLM endpoint.
- [MiniMax Production C1 Service](minimax-production-c1-service.md): run the current 32K endpoint under systemd with health and benchmark checks.
- [Gemma 4 26B B70 95 tok/s Repro](../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md): copy the current one-B70 Q8 target plus Q4_0 MTP draft settings.
- [Gemma 4 26B Result Packet](../results/gemma4-26b-a4b-q8-b70/README.md): optimization history, validity notes, and LocalMaxxing context.
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

The current Gemma 4 26B one-B70 settings are packaged in
[../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/](../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/).
That repro is the shortest path for users who want the exact llama.cpp patch,
Q8 target, Q4_0 MTP draft, command line, and LocalMaxxing evidence.
