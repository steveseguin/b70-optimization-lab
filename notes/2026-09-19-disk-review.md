# Disk review, two-B70 host (2026-09-19 EDT)

Both disks are nearly full. Nothing was deleted for this review; every number below is from `du`, `docker`,
and `df` as of 2026-09-19 morning. The cleanup script `scripts/disk-cleanup-20260919.sh` (dry-run by default)
implements the tiers below; the user picks which tiers to run.

| Disk | Size | Used | Free |
| --- | ---: | ---: | ---: |
| `/mnt/fast-ai` (nvme0n1p1) | 916 GB | 846 GB | **24 GB (98 %)** |
| `/` (nvme1n1p2) | 457 GB | 419 GB | **15 GB (97 %)** |

## Where the space is

### `/mnt/fast-ai` (846 GB used)

| Path | Size | What it is |
| --- | ---: | --- |
| `llm-models/` | 420 GB | model weights (table below) |
| `bench-results/` | 175 GB | campaign outputs; **34 GB of it is 302 torch-compile caches** inside old state dirs; `local-worker-20260914` + `-readable` 25 GB (the September 14 local coding-worker experiment, its plan is in `experiments/local-coding-worker/`) |
| `vllm-cache/` | 77 GB | 250 torch-compile cache dirs keyed by experiment tag, 43 GB under `q38-official-fp8-f01e/` (August r34..r124 experiments, receipts already in the repo) |
| `src/` | 76 GB | 26 llama.cpp worktrees from the August q8 lanes; **62 GB of it is 168 `build*/` directories** (objects, rebuildable) |
| `swapfile-b70` | 32 GB | active swap (prio 10), 1 GB in use; `/swap.img` (4 GB) also active |
| `build/` | 28 GB | kernel build roots (r309..r312d, 0.1-0.7 GB each, ~3 GB total), plus 20+ older `qwen38-*` vLLM build trees of ~1 GB each from August |
| `vllm-cache-exp/` | 14 GB | May 2026 compile-size experiments |
| `venvs/` | 8.3 GB | minimax-h3 (torch XPU) + minimax-h3-cpu |
| `artifacts/` | 6.3 GB | August 17 q8 kernel artifacts (638 MB each) |
| `.incomplete` downloads | 6.5 GB | orphan partial shards from the first MiniMax pass (resume nothing) |

Models on `/mnt/fast-ai/llm-models`:

| Model dir | Size | Status |
| --- | ---: | --- |
| `minimax-h3-comfy/` | 105 GB | full INT8 ConvRot denoiser 34, pruned BF16 denoiser 40, INT8 text encoder 27, VAEs 8, turbo LoRA 2. **Both denoisers are needed until the pruned-vs-INT8 comparison has run.** |
| `minimax-h3/` | 79 GB | original repo: **BF16 transformer 62 GB** (reference; read only by `--verify-remap`, which skips cleanly if it is gone), VAE 10, audio VAE 0.6 |
| `qwen3.8-27b-gguf/` | 49 GB | llama.cpp q8 lane (August), referenced by a package |
| `qwen3.6-27b-q8_0-gguf/` | 30 GB | referenced by a package |
| `qwen3.8-27b-fp8/` | 29 GB | **the shipped FP8 lane, keep** |
| `nemotron-3.5-lightning-30b-a3b-udq4km/` | 24 GB | no package references; August 27 |
| `qwen3.6-35b-a3b-int4-autoround-abhinand/` | 21 GB | no package references; June |
| `qwen3.8-27b-gptq-int4-mtp/` | 19 GB | referenced by a package (INT4 lane) |
| `qwen3.8-27b-int4-autoround/` | 18 GB | INT4 lane source checkpoint (the relabel dir next to it is the shipped one); check before deleting |
| `qwen3.6-27b-int4-autoround/` | 18 GB | no package references; May |
| `qwen35-9b-q8-gguf/`, `ornith-1.5-9b-q8/` | 9.8 + 8.9 GB | no package references |
| smaller (`dflash`, `spec-drafts`, `unsloth-gguf`, ...) | ~10 GB | mixed |

### `/` (419 GB used)

| Path | Size | What it is |
| --- | ---: | --- |
| `/var/lib/containerd` | 279 GB | **all docker images (containerd snapshotter)**: 311 images, 61 dangling, 139 exited containers (14.5 GB reclaimable by `docker container prune`) |
| `/home/steve/llm-models` | 64 GB | a second model dir on the root disk: gemma4-26b q8 gguf 28, qwen35-9b fp8 14, qwen35-9b w4a16 11, qwen35-4b fp8 7.6, qwen35-4b w4a16 5.2 (the Qwen3.5 quick lanes and the Gemma container lane) |
| `/home/steve/.venvs` | 12 GB | `vllm-xpu` 12 GB (used by the health probe and lab tooling; keep) |
| `/opt`, `/usr`, `/snap` | 12 + 11 + 11 GB | oneAPI 2026.1/2025.3, system, snaps |
| `/home/steve/builds` | 7.2 GB | August/September kernel and wheel builds |
| `/home/steve/.cache`, `.codex`, `.local` | 4.6 + 2.3 + 2.9 GB | tool caches |

Docker images: `docker system df` cannot size them with the containerd snapshotter (it reports -420 %), so the
only reliable measure is `df` before and after a removal. The images that must stay: the five package pins
(R276 `521eb277`, R304 `7cd7bb16`, R310 `eb816507`, R311b `7baa32bd`, R312d-c `ea61e698`), the pristine base
`vllm/vllm-openai-xpu:latest` (`96db42e2`), the r312c parent (`4f3d5bb8`), the r312d builders (`r312d-a`, `r312d-b`)
and the oneAPI-2026.0 image they were built from (`gemma4-26b-q8-record:oneapi-2026.0-b9769`), plus whatever the
Gemma/LTX/other lanes still serve (`intel/llm-scaler-vllm`, `gemma4-*`). Everything tagged with an experiment
`rNNN` suffix from August and early September (about 250 images, 24 GB nominal each, sharing the same base layers)
is research history whose receipts are in the repo.

## What can be reclaimed, by tier

The **Reclaims** column below is no longer an estimate: it is what
`scripts/disk-cleanup-20260919.sh --tier 0,1,2,3` printed in dry run on 2026-09-19 (repeated three times,
identical each time). Units are GiB, as `du -b` reports them, so they read slightly smaller than the GB
figures in the sections above.

| Tier | Action | Reclaims (measured, dry run) | Risk |
| --- | --- | ---: | --- |
| **0 - safe** | `docker container prune` (139 exited + 1 created container); `docker image prune` (61 dangling images); delete the 8 `.incomplete` shards over 100 MB; delete `vllm-cache-exp/` (May) | fast-ai: **19.75 GiB** (13.33 cache-exp + 6.41 shards); root: 14.5 GB of containers + dangling layers, only measurable by `df` after the run | none: nothing referenced |
| **1 - caches** | delete the torch-compile `cache/` dirs inside `bench-results/*/` state dirs of finished campaigns; delete `vllm-cache/*` | fast-ai: **104.90 GiB** = 30.07 (259 of 302 bench-results caches) + 74.83 (248 of 250 `vllm-cache` dirs) | a compile cache is rebuilt automatically at the next server start (adds 1-3 min to that start) |
| **2 - build trees** | delete `src/*/build*` (keep the sources), the August `build/qwen38-*` vLLM build trees, `artifacts/`, `/home/steve/builds/*` older than September 10 | fast-ai: **88.62 GiB** = 60.76 (170 `src/*/build*`) + 21.60 (97 `build/qwen38-*`) + 6.27 (`artifacts/`); root: **5.43 GiB** (7 dirs) | rebuildable from the recipes in the repo; the q8 llama.cpp lanes are not active |
| **3 - research images** | `docker rmi` every `neural-download/vllm-openai-xpu:*-rNNN`, `rebase/*`, `upstream-repro/*` and `cleanclone/*` image not in the keep list (the script lists them by family first) | **230 tags / 224 distinct images**: neural-download 214, rebase 11, cleanclone 4, upstream-repro 1. Size is **not projectable** -- with the containerd snapshotter these share base layers, so the real reclaim is measured by `df -h /` after each family | none for the shipped lanes; a deleted research image can be rebuilt from its recipe under `experiments/*/docker/` |
| **4 - models (user decision)** | `minimax-h3/transformer` (BF16 reference); the un-referenced LLMs; the root-disk `/home/steve/llm-models` set if those lanes are finished | fast-ai: up to **141.18 GiB** (transformer 61.73, nemotron 23.53, qwen3.6-35b 20.61, qwen3.6-27b-int4 17.71, qwen35-9b-q8 9.73, ornith 8.87); root: up to **63.52 GiB** | the BF16 reference backs the MiniMax exactness checks (keep until a good clip exists and the INT8 comparison is done); the LLM dirs are re-downloadable |
| **5 - swap** | shrink `swapfile-b70` from 32 GB to 8 GB (`swapoff`, recreate, `swapon`; needs sudo, a quiet host, and the fstab entry updated) | fast-ai: 24 GB | the host used 1.0 GiB of it; keep at least 8 GB for the MiniMax lane. The script only prints these commands, never runs them -- AGENTS.md asks that swap be left alone for the stability effort |

Tiers 0-2 together free **213.26 GiB on `/mnt/fast-ai`** (23.71 -> 236.98 GiB free) and **5.43 GiB on `/`**.
Tier 3 adds nothing to that arithmetic because its images cannot be sized in advance; the root disk's real
relief is tier 3, and only `df` can measure it.

Two things the dry run settled that the estimates above had guessed at:

* **Nothing live mounts `/mnt/fast-ai/vllm-cache`.** Both FP8 launchers
  (`packages/qwen38-27b-fp8-tp{1,2}-b70/scripts/serve.py`) bind-mount a **per-state** compile cache,
  `<state-dir>/cache` -> `/root/.cache/vllm`, created fresh by `serve.py start`. So there is no cache tag to
  preserve there; the script keeps the two most recent dirs anyway as a margin.
* **43 of the 302 `bench-results` caches are held back**, not 0: two belong to state dirs whose `state.json`
  still reads `starting`, and 41 are newer than two days (the September 17-18 FP8 and MiniMax sessions).

Recommended order: tiers 0-2 today (213 GiB on `/mnt/fast-ai`, 5.4 GiB plus the container prune on `/`), tier 3 next (the root disk's
real problem), tier 4 and 5 as the user decides. After tiers 0-3 the MiniMax lane has room for a second denoiser
comparison and the FP8 lane for its next image without either disk pinching.
