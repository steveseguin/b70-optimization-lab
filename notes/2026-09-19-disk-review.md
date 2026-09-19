# Disk review, two-B70 host (2026-09-19 EDT)

Both disks are nearly full. Nothing was deleted *for this review*; every number below is from `du`, `docker`,
and `df` as of 2026-09-19 morning. The cleanup itself ran later the same day, on the user's direction --
see [Executed, 2026-09-19 afternoon](#executed-2026-09-19-afternoon) at the end for what actually happened. The cleanup script `scripts/disk-cleanup-20260919.sh` (dry-run by default)
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

---

## Executed, 2026-09-19 afternoon

The user's direction: keep only the **Qwen3.8-27B FP8** and **MiniMax-H3** lanes on the fast disk, move the other
models to external drives, delete the caches, build trees and research images, and leave swap alone. All of that
ran between 13:04 and 13:25 EDT. Nothing on the GPUs was touched; the FP8 service was already down.

### Timeline

| Time (EDT) | Step | `/mnt/fast-ai` free after |
| --- | --- | ---: |
| 13:04 | `scripts/disk-cleanup-20260919.sh --tier 0,1,2,3 --yes` | 122 GB (24 GB before) |
| 13:05 | the same 518 vetted tier-0/1 paths re-deleted **with `sudo`** (see below) | 252 GB |
| 13:06-13:15 | 17 model directories moved to the external SSD (`move-cold-storage-20260919`) | 396 GB |
| 13:15-13:20 | 902 campaign directories archived, user-level (`archive-bench-results-20260919`) | 412 GB |
| 13:20-13:21 | `/mnt/fast-ai/src` (14 GB of llama.cpp worktree sources) moved (`move-src-20260919`) | 426 GB |
| 13:22-13:25 | the remaining 348 campaign directories archived **as root** (`archive-bench-sudo-20260919`) | 503 GB |

Logs, all under `/mnt/fast-ai/bench-results/`: `disk-cleanup-20260919.log` (+ the 226 MB stdout capture
`disk-cleanup-20260919-run.log`), `move-to-cold-storage-20260919.log`, `archive-bench-results-20260919.log`,
`archive-bench-results-sudo-20260919.log`, `move-src-20260919.log`. The four movers are now in the repo as
[`scripts/disk-archive-20260919/`](../scripts/disk-archive-20260919/), parameterized for reuse.

### The lesson: user-level `rm` over container-written state

The cleanup script printed **"Freed 97.94 GiB on `/mnt/fast-ai`, 128.89 GiB on `/`"** and that was wrong for
`/mnt/fast-ai`. Tier 1 and part of tier 0 had silently failed. The torch-compile caches under
`bench-results/*/…/cache` and the `.incomplete` shards under
`llm-models/minimax-h3/.cache/huggingface/download/` were written by the serving container, so they are owned by
**root**. A user-level `rm -rf` over them emits one `Permission denied` per file -- **744,805 lines** in the run
capture -- and still exits 0. The script logged `WARNING -- still exists after removal` 521 times (1 in tier 0,
494 in tier 1, 26 in tier 2) and then reported the tier totals as if nothing had gone wrong; the `df` delta it
also printed was real, but read next to the tier totals it looked like the tiers had done their job.

Re-running the same 518 vetted paths through `sudo rm -rf` freed a further **106 GB** (146 -> 252 GB free). The
same thing then bit the campaign archive: the first, user-level pass could not even *read* 348 of the 1,250
directories, which is why there is a second, root pass at all.

The script is fixed. Every removal now goes through `remove_path()`, which removes as the user, retries as root
via `sudo -S -p '' rm -rf -- <path> < /home/steve/SUDO_PASSWORD.txt` when the path is not owned by the caller or
survives the first attempt, and **counts what still exists afterwards**. The summary now prints removed-vs-planned
per tier, lists every path that survived, states that the `df` delta is the only measurement that counts, and
exits 5 on a partial run. The password file is never printed, logged, or put on a command line. Recorded as a
[do-not-repeat row](../experiments/qwen38-27b-b70/DO-NOT-REPEAT.md).

### Verify, then remove

None of the movers deleted a source on the strength of an exit code. Each directory was copied with
`rsync -a --no-inc-recursive`, then re-checked with `rsync -a -n -i | grep -c '^>f'`; only a count of zero -- no
file left to transfer, so every size and mtime matched -- authorized the `rm`. **0 mismatches across all 17 model
directories and all 1,250 campaign directories.**

### What moved where

Cold storage is `/media/steve/extended-ssd/model-cold-storage/b70-host-20260919/`, one directory per host per
session, with the source disk in the path so same-named directories cannot collide:

| Destination | Contents |
| --- | --- |
| `llm-models-fast-ai/` | 12 dirs from `/mnt/fast-ai/llm-models`: nemotron-3.5-lightning-30b, qwen3.6-35b-a3b-int4, qwen3.6-27b-int4-autoround, qwen3.6-27b-q8_0-gguf, qwen3.6-27b-dflash-q8_0-gguf, qwen36-27b-dflash-q8, qwen35-9b-q8-gguf, ornith-1.5-9b-q8, lfm2.5-2.6b-q8, qwen35-0.8b-q8-tp-probe, qwen3.8-27b-gguf, qwen3.8-27b-unsloth-gguf |
| `llm-models-root/` | 5 dirs from `/home/steve/llm-models`: gemma4-26b-a4b-it-q8-gguf, qwen35-9b-fp8-dynamic, qwen35-9b-w4a16, qwen35-4b-fp8-dynamic, qwen35-4b-w4a16 |
| `bench-results-pre-20260914/` | 1,250 campaign dirs (902 user pass + 348 root pass, the root pass alone 78 GB), original names kept |
| `src-llama-cpp-worktrees/` | the 26 llama.cpp worktrees from `/mnt/fast-ai/src`, sources only |

**How the 1,250 were chosen.** `comm -23` of two sorted lists: directories in `bench-results` whose mtime is
older than 2026-09-14, minus every `bench-results/<name>` path grepped out of `experiments/*/scripts`,
`packages/*/scripts` and `scripts/`. The subtraction protected 10 older directories that runners still name --
`gemma4-26b-a4b-q8`, `qwen35-4b-w4a16-20260913-rt2`, `qwen35-9b-w4a16-20260913-rt2`, the `qwen38-fp8`
r147 / r156f / r165 sets, `r304-real-content-depth-20260913b`, `rebase-v0290-rb1`, the INT4 r304 rebase and the
r307 qualification -- and `gpu-fault*` / `host-oom*` incident evidence was excluded by name on top of that.
`/mnt/fast-ai/bench-results` now holds only the 2026-09-14-and-later campaigns, those 10, and the evidence folders.

Two things did **not** happen: the NFS share `/mnt/lab-models` (10.0.0.65) was unreachable, so nothing was staged
there; and the 3 TB green HDD is the user's personal media, not lab storage. Swap was untouched, as asked.

### Final state

| Disk | Size | Free before | Free after |
| --- | ---: | ---: | ---: |
| `/mnt/fast-ai` (nvme0n1p1) | 916 GB | 24 GB (98 % used) | **503 GB (43 % used)** |
| `/` (nvme1n1p2) | 457 GB | 15 GB (97 % used) | **208 GB (53 % used)** |
| `/media/steve/extended-ssd` (cold storage) | 1.9 TB | -- | 679 GB free (62 % used) |

42 docker images remain: the five package pins (R276, R304, R310, R311b, R312d-c), the pristine base, the r312c
parent, the r312d builders and the oneAPI-2026.0 image they came from, plus the images the Gemma and other lanes
still serve. Tier 4 (models) and tier 5 (swap) of the cleanup script were not used; the model moves above were
done by the movers instead, which relocate rather than delete, and `minimax-h3/transformer` -- the 62 GB BF16
reference behind the exactness checks -- is still on the fast disk, which the FP8 and MiniMax lanes now share
with 503 GB to spare.

### "Do we actually need to keep all those docker images?"

No -- and the 42 that remain are already more than the floor. Every image that qualified a shipped lane is on
`ghcr.io` and every package README pins it **by digest**, so a `docker pull` of that digest on any other host
gets byte-for-byte the image the acceptance evidence was taken against; the local copy is a cache, not the
record. The research images are throwaway by design: each one has its Dockerfile, its build script and its
kernel patch checked into `experiments/*/docker/` and `patches/`, so the repo is the durable record of *how* an
image was made and the registry is the durable home for anything that was published, while the 250-odd `rNNN`
tags were only ever the local by-product of building them. What the local store genuinely needs is the images
the packages currently pin (so the service starts without a pull), the builders you would use to make the next
one, and whatever another lane is actively serving -- everything else can be re-pulled or rebuilt, and deleting
it costs a rebuild, never a result.
