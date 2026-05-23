# B70 Optimization Lab Docs

This docs folder is the human entry point for the B70 optimization work. The executable install recipes live under `../repro/`; docs link to those folders instead of duplicating every script.

## Start Here

- [MiniMax M2.7 INT4 on 4x B70, Ubuntu 24](b70-minimax-ubuntu24-deployment.md): deploy an OpenAI-compatible vLLM endpoint.
- [Model Recipes](model-recipes.md): which recipe folder to use for each model/build target.
- [FAQ](faq.md): practical answers for users new to B70s, vLLM, XPU, and local model deployment.
- [GPU Comparison for Local AI](gpu-comparison-local-ai.md): rough pricing/spec/performance framing for B70s versus common alternatives.
- [Community Results And Build Notes](community-results.md): how to share records, build photos, reproducible logs, and discussion links.
- [Feedback for Intel](feedback-for-intel.md): short discussion guide plus the detailed Intel feedback note.

## Build Photos

The community build guide includes example B70 photos and explains what details future contributors should capture: card spacing, airflow, power, slot order, risers, cooling, and visible diagnostics.

- [Community build photos and result format](community-results.md#build-photos)

## Repository Layout

- `docs/`: narrative guides, FAQ, community-facing summaries, comparison notes.
- `repro/`: runnable install/build/benchmark/serve recipes and pinned artifacts.
- `notes/`: lab notebook entries, including negative results.
- `data/`: structured benchmark records, payloads, and LocalMaxxing responses.
- `patches/`: patch records and source-level optimization deltas.
- `scripts/`: shared harnesses used by repro folders and lab runs.

## Community Links

- Maintainer/site: https://steveseguin.com
- X feed with ongoing build notes: https://x.com/xyster
- LocalMaxxing profile/results: https://localmaxxing.com/user/steveseguin
- Project pages timeline: https://steveseguin.github.io/llm-optimizations/optimization-timeline.html

## Current Deployable Baseline

The current clean "start from Ubuntu 24 and serve on the LAN" baseline is:

- Recipe: `../repro/minimax-m27-b70-110tps-ubuntu24-20260523/`
- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- API: OpenAI-compatible vLLM endpoint on `0.0.0.0:8000`
- Served context: `32768` tokens by default
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
