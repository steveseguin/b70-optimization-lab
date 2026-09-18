# MiniMax-H3 two-B70 stand-up: the runnable pipeline, prepared (2026-09-17/18)

Prepared without touching a GPU. No `torch.xpu` device was created, no service or container was
started or stopped, nothing was downloaded, and no tracked file outside
`experiments/minimax-h3-b70/` was modified. Everything below was validated on CPU against the
files already on disk.

## What is now in `scripts/`

| File | What it is |
| --- | --- |
| `run_h3_t2v.py` | the generation script: INT8 text encoder -> pruned BF16 denoiser split over two cards -> VAE decode -> mp4 + receipt. Has a CPU-only `--dry-run`. |
| `smoke_h3.sh` | `dry` / `one` / `repeat`. `repeat` is the bytewise gate: two runs, same seed, hashes compared. GPU modes run under `systemd-run --user --scope`. |
| `setup-venv.sh` | builds `/mnt/fast-ai/venvs/minimax-h3`. **Written but not run** -- see "the venv" below. |
| `recover-convrot-rotation.py` | recovers the ConvRot rotation from the two video-VAE builds. **Run**; output is `data/convrot-hadamard-256.safetensors`. |
| `mem-watchdog.sh` | kills THIS job on a `MemAvailable` floor, before `systemd-oomd` kills the user's session. Every GPU run and every profile is wrapped in it. |
| `profile-encoder-load.py` | CPU-only host-memory profile of the two load loops, `--loader pread\|mmap`. This is what turned "the loader holds no state dict" from an argument into a measurement. |
| `test_tensor_reader.py` | the `pread` reader returns bit-for-bit what `safe_open` returns: every dtype, row slices, real files. CPU, seconds, a few MB. |

## Three things that were unknown yesterday and are now settled

### 1. The ConvRot rotation is recovered, not unknown

The [pipeline plan](2026-09-17-pipeline-plan.md) records the rotation as unrecoverable without a
ComfyUI tree. It is recoverable, and it took a few seconds: the same video VAE is on disk twice,
once F16 and once INT8 ConvRot, so `R` is just the least-squares solution of `W[:, g] R = W'[:, g]`
per 256-column group. Measured across six probes (different layers, different Linears, different
groups):

* every `R_g` is **the same matrix**, to the sign of every entry;
* every entry is `+-1/sqrt(256)`, i.e. a Hadamard-type matrix of order 256;
* the sign matrix is symmetric, exactly orthogonal, and every row sums to `+16`.

Stored as `data/convrot-hadamard-256.safetensors`
(`sha256 ebb89aa1651e681f49461fe539bf2eb6fba0143c2733e5ad9cef438d48fb28d2`). That file is **not in
Git** -- the repo's `.gitignore` excludes `*.safetensors` -- so `recover-convrot-rotation.py` is
the artifact of record and step 0 of the sequence below regenerates it in seconds from files
already on disk. The sha256 above is what a regeneration must reproduce. The convention is
`W' = W R`, so the runtime rotates the **activation**: `y = (x R) W'^T`. `run_h3_t2v.py` implements
that, and `--te-rotation none` is the A/B control.

Caveat, stated plainly: this was recovered from the **video VAE** pair, because that is the only
pair on disk. The text encoder declares the identical `comfy_quant` string
(`{"format":"int8_tensorwise","convrot":true,"convrot_groupsize":256}`) and came out of the same
tooling, so the same `R` is assumed for it. That assumption is **not verified** and cannot be from
files on this host -- the BF16 Qwen3-VL text encoder was never downloaded. The GPU session settles
it in one shot: with the right rotation the prompt embedding conditions a sane clip, with
`--te-rotation none` it will not.

### 2. The Comfy -> diffusers key remap is verified byte-for-byte

The pruned file uses upstream/Comfy names, not diffusers ones. The remap is in
`run_h3_t2v.py::build_remap` and `--dry-run --verify-remap` checks it against the **full BF16
diffusers checkpoint** in `/mnt/fast-ai/llm-models/minimax-h3/transformer/` -- which is possible
because pruning only replaces the AdaLN branch, so every other tensor must be identical. 14/14
sampled tensors are exact. Two of those results are load-bearing and would have been coin flips:

* `blocks.N.attn.qkv_proj` splits `[0:7168] -> to_q`, `[7168:14336] -> to_k`, `[14336:21504] -> to_v`;
* `blocks.N.mlp.fc1` is `[gate ; value]` but diffusers' SwiGLU reads `[value ; gate]`
  (`activations.py` L143-146) -- **the halves must be swapped**. Loading it straight through runs
  and produces plausible-looking garbage.

The remap covers all 634 diffusers parameters from all 532 checkpoint tensors, with 0 left over.

### 3. The pruned AdaLN form is implemented and unit-checked on CPU

`time_proj` becomes an identity and `time_embedder` becomes the table lerp, so the **stock
diffusers `forward` needs no patching**; only the three modulation modules are replaced. Checked
on CPU against the real table and the real `W8`/`b8`:

* `c(0) == adaln_t_table[0]` and `c(1) == adaln_t_table[1024]` exactly;
* the lerp at a half-grid point is the midpoint of the two rows;
* the output is 6 chunks of `(3 * num_timesteps, 5376)` in the
  `shift_msa, scale_msa, gate_msa, shift_mlp, scale_mlp, gate_mlp` order diffusers expects;
* block 0's modulation spans `[-2.1809, 3.2671]` over the whole grid and `final_layer`'s spans
  `[-1.5415, 0.8207]`, against the `+-3.2667` / `+-1.5417` that
  [the exactness note](2026-09-17-adaln-table-exactness.md) measured on the *full* model. The
  implementation is reproducing the right curve.

Interpolation, not snapping, per that note: the lerp costs 1.2e-5, a nearest-row snap costs 4.2e-3.

## The dry run

```
$ ./smoke_h3.sh dry
```

```
denoiser header: 532 tensors, 40.23 GB stored
  remap covers 634 diffusers parameters from 532 checkpoint tensors
  checkpoint tensors not consumed: 0
  adaln_t_table: F32 [1025, 8]

layer split (LTX byte-balancing policy, ltx_layer_shard.py::install):
  blocks                : 50
  per-block bytes       : 774.2 MB (identical for every block)
  non-block bytes       : 1.603 GB (1.492 GiB)
  split_index           : 24  -> blocks 0..23 | 24..49
  card 0 (primary)      :   20.184 GB  18.797 GiB
  card 1 (secondary)    :   20.129 GB  18.747 GiB
  imbalance             : 54.1 MB
  free per card (32 GiB): 13.203 GiB / 13.253 GiB

text encoder (phase 1, alone on one card, freed before the denoiser loads):
  tensors               : 1602  (350 ConvRot Linears)
  resident bytes        : 27.141 GB  25.277 GiB
  free after load       : 6.723 GiB
  largest dequant buffer: model.layers.9.mlp.up_proj.weight -> 262.1 MB in bf16

requested clip (at the 256x448 smoke canvas):
  frames  : 124 (17n+5), 5.167 s at 24 fps
  latent  : 37 frames, 16 x 28
  rows    : 4144 video + 414 audio + text
  steps   : 50  <-- ASSUMED
```

At the default 768x1344 canvas the same clip is **37296 video rows**, so the packed sequence is
~37.7k rows before the prompt. Full attention only in this release.

## What I assumed, and why

| Assumption | Why | How the GPU session settles it |
| --- | --- | --- |
| **Encoder = INT8 ConvRot Qwen3-VL**, dequantized to BF16 per Linear, rotation applied to the activation | it is the only encoder on disk (the BF16 one, 67 GB, was never downloaded) and it fits alone on one card at 25.3 GiB | run once; compare against `--te-rotation none`. If the embedding is wrong the clip is obviously wrong. |
| **`num_inference_steps = 50`** | **no default exists anywhere.** The H3 blocks mark it required with no default; no file on this host declares one; the official scripts do not expose it. 50 is the generic diffusers template value, i.e. a guess. That Comfy ships 4-step and 8-step turbo LoRAs implies the base is many-step. | read `pipe.doc` / the blocks' resolved docstring once diffusers is installed, or sweep 20/30/50 and look at the frames |
| **Canvas defaults to 768 short edge -> 768x1344** | `resolve_canvas_size(16, 9, 32, 768, 1032192)` with no keyframe, per `modular_pipeline.py` L40-96 | nothing to settle; but **start the smoke at 256x448**, which is ~1/9 of the rows |
| **Modulation cast to bf16** after the float32 rank-8 projection | the unpruned checkpoint's `adaln_proj` is bf16, so this matches the full model's arithmetic; keeping float32 would promote the whole 37k-row packed sequence to float32 | `--adaln-out-dtype fp32` is the A/B |
| **VAEs from the original repo**, video in float16, audio in float32 | the Comfy `*_vae_fp16` / `*_vae_fp32` files use upstream naming and the audio one is weight-norm-**fused** (`conv.weight`) where diffusers wants the re-parameterised `weight_g`/`weight_v` -- a second unverified remap for no benefit | nothing; revisit only if VAE load time matters |
| **`t2va` workflow on the `transformer/` (FL2VA) partition** | "first/last-frame mode, no images" is exactly this: the pruned checkpoint *is* the FL2VA partition, and with no keyframes the blocks take the `t2va` path | nothing |
| **`mm_token_type_ids` is all zeros** | a `t2va` presentation is all text | nothing |

## What still needs the GPU session to find out

Ordered by how likely each is to be the thing that stops the first run.

1. **The cards.** Both B70s are held by the live FP8 service on `127.0.0.1:18124` at
   `--gpu-memory-utilization 0.95`. This lane cannot start until the user decides to stop it for a
   block. That is a user decision, not an agent one (AGENTS.md).
2. **The venv does not exist.** `setup-venv.sh` is written and guarded but was not run: it needs
   ~8-10 GB of downloads and none of the XPU wheels are cached on this host. So
   `python -c "import torch, diffusers; print(...)"` in `/mnt/fast-ai/venvs/minimax-h3` has **not**
   been executed -- the venv is a script, not a fact. Everything else was validated in
   `/mnt/fast-ai/venvs/minimax-h3-cpu` (torch 2.14.0+cpu + safetensors + numpy; it has no
   diffusers and no transformers, which is why the diffusers API calls in `run_h3_t2v.py` are
   cited to source lines rather than exercised).
3. **transformers' Qwen3-VL module layout.** The checkpoint uses `model.layers.*` / `visual.*`;
   transformers 5.17 may expose `model.language_model.*` / `model.visual.*`. The loader
   auto-detects the prefix and fails loudly if it cannot. Related and more subtle: MiniMax-H3
   conditions on the **unnormalized** state after layer 50, and transformers' `hidden_states[50]`
   is only that quantity on the *full 64-layer* stack. On the truncated 50-layer stack the loader
   replaces the final norm with an identity (the checkpoint ships no `model.norm.weight`, which is
   the corroboration) and reads `last_hidden_state`. If a future checkpoint does carry that norm
   the loader raises rather than guessing.
4. **XPU op coverage in the denoiser**: 3-axis MM-RoPE, per-head RMS qk-norm, and a packed
   sequence of thousands of rows through SDPA with no mask. `_flash_3_hub` is CUDA-only, so this
   is plain SDPA. Unverified at 37k rows.
5. **The cross-card boundary.** `hidden_states` crosses once; `temb`, `adaln_indices` and the two
   rope tensors are re-read by every block, so they go through a per-forward transfer cache (the
   LTX lane's `_move` / `_forward_transfers` policy). ~24 MB per forward at the full canvas. Cost
   unmeasured.
6. **Determinism.** `--deterministic` turns on `use_deterministic_algorithms(True)` with
   `warn_only=False`; whether every op in this stack has a deterministic XPU implementation is
   unknown. If it fails closed, record it and qualify any repeat claim -- do not soften a failed
   bytewise gate to "visually identical".
7. **Wall clock.** Nothing here is a speed estimate. A 50-layer ~20B-active denoiser over
   thousands of rows for tens of steps on two cards, with the text encoder dequantizing INT8 in
   software, is slow; the receipt reports seconds of wall per second of video and per-phase
   timings, and that is the first real number.

## Exact sequence for the orchestrator

Everything before step 3 is safe to run right now with the FP8 service up.

```bash
cd /home/steve/b70-optimization-lab/experiments/minimax-h3-b70/scripts

# 0. re-derive the ConvRot rotation (CPU, seconds, no GPU, no network)
/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python recover-convrot-rotation.py \
    --out ../data/convrot-hadamard-256.safetensors

# 1. the plan + the remap proof (CPU, no GPU)
./smoke_h3.sh dry

# ---- from here the cards must be free; stopping the FP8 service is a USER decision ----

# 2. build the GPU venv (DOWNLOADS ~8-10 GB; needs approval)
./setup-venv.sh --yes
/mnt/fast-ai/venvs/minimax-h3/bin/pip freeze > ../data/environment.txt

# 3. one clip, small canvas, to find out whether it runs at all
./smoke_h3.sh one

# 4. the bytewise repeat gate: two runs, same seed, hashes compared
./smoke_h3.sh repeat

# 5. walk the canvas up, recording seconds per clip at each stop
HEIGHT=320 WIDTH=576  ./smoke_h3.sh one
HEIGHT=544 WIDTH=960  ./smoke_h3.sh one
HEIGHT=768 WIDTH=1344 ./smoke_h3.sh one     # the trained canvas

# 6. the two open arithmetic questions, same seed, compare hashes and frames
/mnt/fast-ai/venvs/minimax-h3/bin/python run_h3_t2v.py --adaln-out-dtype fp32 ...
/mnt/fast-ai/venvs/minimax-h3/bin/python run_h3_t2v.py --te-rotation none ...
```

Evidence lands in `/mnt/fast-ai/bench-results/minimax-h3/<run>/` as `clip.mp4`, `receipt.json` and
(with `--save-tensors`) `tensors.safetensors`. Only summaries come back into the repo, per
AGENTS.md. The receipt carries the seed, every setting, per-phase timings, peak allocated and
reserved bytes per card for each phase, host peak RSS, the SHA-256 of the decoded frame tensor,
the audio tensor and both latent tensors, the resolved split plan, and the input file identities
-- so a repeat is a hash comparison, not a judgement.

## Abort rules for the session

* Any `Fault response`, CAT error, engine reset or coredump line in the kernel journal: stop
  issuing work, write the evidence, do not reset the driver and do not reboot (AGENTS.md, and the
  2026-09-16 GPU fault on this host is still open).
* A failed bytewise repeat is a result to record, not a reason to re-run until it passes.
* Do not promote any number from this lane until quality is labelled and the repeat gate has a
  verdict.

## The venv is a fact now, and the first-light session is armed (2026-09-18 02:35 UTC)

`setup-venv.sh` ran. Two things in it were wrong and are fixed in commit `a00ba16dc`:

* it installed diffusers with `--no-deps`, so nothing pulled in diffusers' own runtime imports and the script's final
  import check failed on `requests`, then on `importlib_metadata`. The pip line now also installs
  `requests regex Pillow importlib_metadata`.
* `MiniMaxH3CoreDenoiseStep` is **not** re-exported by `diffusers.modular_pipelines.minimax_h3`; it has to come from
  `...minimax_h3.modular_blocks_minimax_h3`. Both `setup-venv.sh` and `run_h3_t2v.py` import it from the module.

`/mnt/fast-ai/venvs/minimax-h3` now holds torch 2.14.0+xpu, transformers 5.17.0 and diffusers built from the git
checkout at `7221eef4`; the full freeze is recorded in [data/environment.txt](../data/environment.txt). `./smoke_h3.sh
dry` passes against it -- 14/14 remaps exact, 634 diffusers parameters from 532 checkpoint tensors, 0 left over
(`/mnt/fast-ai/bench-results/minimax-h3-dry.log`). So item 2 of "what still needs the GPU session" above is closed:
the venv is no longer a script.

**The first-light session is armed** as unit `h3-session5d-20260918`
(`/mnt/fast-ai/bench-results/h3-session5-20260918.sh`). It waits for the r312c kernel session (and for lc-3, if the
r312c census is exact and lc-3 runs), re-checks the venv imports and refuses to continue if they fail, stops the FP8
service gracefully, and then runs:

1. `STEPS=8 ./smoke_h3.sh one` -- one clip at the smoke canvas, **256x448, 124 frames**, seed 42, 90-minute timeout;
2. only if that returns 0, `STEPS=8 ./smoke_h3.sh repeat` -- two runs at the same seed with their receipt hashes
   compared, which is the bytewise gate;

then waits for port 18124 to be free and restores the service as unit `fp8-service-20260918-h3`
(state `/mnt/fast-ai/bench-results/minimax-h3/service-restore`). Evidence lands in
`/mnt/fast-ai/bench-results/minimax-h3/`.

`STEPS=8` is deliberate and is **not** a claim about the right step count (50 remains an assumption, see the table
above). First light asks two questions only: does this stack run on the cards at all, and does it repeat bit for bit.
Eight steps answers both at about a sixth of the wall clock; the step sweep comes after the repeat gate has a verdict.

## First light 2 (02:05 UTC): killed the host session

The first-light run started at **03:05:07 UTC** (`smoke_h3.sh one`, `STEPS=8`, run
`smoke-20260918T030507Z`) under `systemd-run --user --scope --property=MemoryMax=4G`. It reached phase
`encode.load` -- the 27 GB INT8 text encoder under `/mnt/fast-ai/llm-models/minimax-h3-comfy` -- at
03:05:11, and **its log has nothing after that line**. There is no clip, no receipt, no repeat gate and no
answer to either of the two questions first light was supposed to ask.

What happened instead: it started in the same second as a `JOBS=2` r312d kernel build in an 8 GiB Docker
container, on a host with 15 GiB of RAM. The build's `icpx` frontends were OOM-killed at 03:05:07;
`systemd-oomd` then killed by memory pressure up through the user's GNOME session and, at 03:09:59,
`user@1000.service` itself. That killed every `systemd-run --user` unit on the host, including the queued
FP8 sessions and the service restore. The runner (python 137924) was orphaned and reaped by the kernel at
03:18:41. No GPU was involved -- there is no `xe` fault line anywhere in the window, and both cards are
free. Full account: [host OOM incident](../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md);
evidence in `/mnt/fast-ai/bench-results/host-oom-20260917T2310/`.

**The `MemoryMax=4G` was the mistake, not the safeguard.** It was armed as a tripwire on the theory that
the cgroup would kill the runner before the host noticed. A cgroup limit far below the real working set
does not fail fast -- it thrashes in reclaim, and sustained reclaim pressure is precisely what
`systemd-oomd` kills on. The tripwire manufactured the pressure that took the desktop.

### Preconditions before any rerun

Every one of these, in order, before the lane is armed again:

1. **Measure the host-RAM need of `encode.load` on a CPU-only pass** -- no GPU, no container beside it, no
   `MemoryMax`. Record peak host RSS for that phase specifically. The dry run's "resident bytes 27.141 GB"
   is a device-side figure and says nothing about what the *loader* holds in host memory.
2. **That measured peak must sit well under free host RAM.** If it does not, the loader changes before the
   run does: dequantize and stream the encoder **tensor by tensor to the GPU**, so no full host-side copy
   ever exists.
3. **No `MemoryMax` below the measured peak.** Either size it above, or drop it and use a watchdog that
   reads `/proc/meminfo` and kills the runner on low *available* memory.
4. **Nothing else running.** No compiler container, no kernel build, no other lane -- one host-RAM-heavy
   job at a time on this host.
5. **FP8 service down for the run, and the restore waits for the port.** The 02:43 restore in this same
   session lost the race and died on `[Errno 98] Address already in use`; poll `ss -ltn` for `:18124`
   until it is gone.
6. **Re-queue behind the FP8 work, not beside it.** The r312d b/c builds come first; the lane is not armed
   while one is running.

Until 1 and 2 have numbers, this lane does not touch a GPU.

## The loader was the NO-GO, and it is fixed (2026-09-18, sessions 6-8)

Precondition 1 of "before any rerun" above -- *measure* the host-RAM need of `encode.load` -- has a
number now, and the first answer was no.

**Sessions 6 and 7** (`/mnt/fast-ai/bench-results/minimax-h3-s6-20260918/` and `-s7-`) ran
`profile-encoder-load.py` at a 6 GiB budget, plain and with `--drop-pagecache`. The loader's own
memory was never the problem: RssAnon peaked at one tensor's worth -- 1.661 GiB for the encoder
(its largest tensor, `model.embed_tokens.weight`, is 1.556 GB) and 0.499 GiB for the denoiser --
and came straight back down after each tensor, exactly as a streaming loader should. What failed
the gate was **RssFile: 6.291 GiB at a 6 GiB budget, growing with every byte touched**, which on
the full files means 27 GB for the encoder and 40 GB for the denoiser. Go/no-go numbers 6.634 GiB
(s6) and 6.695 GiB (s7) against a 6 GiB rule: **NO-GO, twice.**

`--drop-pagecache` made it slightly worse rather than better, and that is the whole diagnosis: a
`safetensors.safe_open` handle keeps the file mapped for its lifetime, and
`posix_fadvise(DONTNEED)` cannot evict a page that is still mapped. Those pages are reclaimable, so
this would not have shown up as an out-of-memory kill -- it would have shown up the way 2026-09-17
did, as sustained reclaim, which is the memory *pressure* `systemd-oomd` kills the user's session
on.

**The fix, in `run_h3_t2v.py`:** both load loops now go through `open_tensor_reader()`, and the
default reader does not map anything. `B70_H3_LOADER=pread` (the default) parses the safetensors
header once, `os.pread`s each tensor's byte range into a private buffer, re-labels it with
`torch.frombuffer(...).view(dtype).reshape(shape)`, lets the caller copy it to its card, and then
`posix_fadvise(DONTNEED)`s that one range -- which frees it, because nothing maps it. Leading-row
slices are contiguous byte ranges, so the qkv split reads a third of `qkv_proj` three times instead
of the whole tensor three times. `B70_H3_LOADER=mmap` keeps the old path for A/B, and
`profile-encoder-load.py --loader {pread,mmap}` profiles either one.

A loader swap is only allowed to change *where the bytes live*, never *what the bytes are*, so
`scripts/test_tensor_reader.py` checks that with `torch.equal`, bitwise, against `safe_open`: every
dtype the two checkpoints use (BF16/F16/F32/I8/U8/BOOL/I64), leading-row slices, the SwiGLU half
swap, and real safetensors files on disk (the ConvRot rotation and a video-VAE shard). It is CPU
only and touches a few MB.

**Session 8** (`/mnt/fast-ai/bench-results/minimax-h3-s8-20260918/`), `--max-bytes 2` because the
FP8 service was up and holding ~10 GiB of the 15:

| Loop | Loader | RssAnon | RssFile | VmHWM | GO/NO-GO |
| --- | --- | --- | --- | --- | --- |
| encoder | **pread** | 1.593 GiB | **0.070 GiB** | 1.663 GiB | **1.663 GiB -- GO** |
| encoder | mmap | 1.593 GiB | 2.081 GiB | 3.114 GiB | 3.115 GiB |
| denoiser | **pread** | 0.720 GiB | **0.073 GiB** | 0.791 GiB | **0.792 GiB -- GO** |
| denoiser | mmap | 0.432 GiB | 2.053 GiB | 2.483 GiB | 2.485 GiB |

On the mmap loader RssFile equals the bytes read; on the pread loader it is 0.07 GiB and does not
move, and that 0.07 GiB is the interpreter and torch's shared objects, not the checkpoint. The peak
is now bounded by the largest tensor in the file rather than by the file's size, so 1.663 GiB is
also the number for a full 27 GB pass. The denoiser's RssAnon rises 0.432 -> 0.720 GiB, honestly:
pread holds the source rows *and* the `cat`/`contiguous` copy at once where the mmap path could
slice out of the mapping. That is 0.29 GiB of anon traded against 2 GiB (heading for 40) of mapped
page cache.

`./smoke_h3.sh dry` still passes on the new loader: 14/14 remaps exact, 634 diffusers parameters
from 532 checkpoint tensors, 0 left over.

So precondition 1 is closed and precondition 2 -- "that measured peak must sit well under free host
RAM" -- is met with room: 1.663 GiB against the ~13-14 GiB the host has with the service down. The
remaining preconditions (3-6) are unchanged and still gate the GPU run.

## The full INT8 ConvRot denoiser is on disk, and the runner can load it (2026-09-18)

The download that the [disk audit](2026-09-18-disk-audit.md) caught at 15.7 % has finished:
`minimax_h3_fl2va_int8_convrot.safetensors`, 34,038,892,334 bytes, 1035 tensors, and the header's
declared data end lands exactly on the file's last byte. That closes the audit's one open item and
makes its "only one of the two denoisers exists on this host" paragraph stale.

`scripts/run_h3_t2v.py` now has a second load path for it. `--denoiser {pruned,int8}` (env
`B70_H3_DENOISER`) selects between a two-entry `DENOISERS` table; **the default stays `pruned`**
until the pruned control has actually rendered a clip.

### What the two headers say, side by side

The int8 file is not the pruned file quantized. It is the *unpruned* model quantized, which is the
whole reason it needs its own load path rather than a flag:

| | pruned BF16 (532 tensors) | int8 ConvRot (1035 tensors) |
| --- | --- | --- |
| `adaln_t_table` | `F32 [1025, 8]` | **absent** |
| `time_embedder.proj_in / proj_out` | **absent** | `F32 [5376, 256]` / `F32 [2688, 5376]` |
| `blocks.N.adaln_proj.linear.weight` | `F16 [96768, 8]` | `I8 [96768, 2688]` + `F32 [96768, 1]` scale |
| `final_layer.adaln_proj.linear.weight` | `F16 [10752, 8]` | `BF16 [10752, 2688]` (**not** quantized) |
| `blocks.N.attn.qkv_proj / out_proj / mlp.fc1 / fc2` | BF16 | `I8` + `F32` per-row scale |
| `token_refiner.blocks.N.*` | BF16 | BF16 (**not** quantized -- only the 50 denoiser blocks are) |
| `blocks.N.norm1/norm2`, `attn.q_norm/k_norm` | BF16 | BF16 |

So: 250 quantized Linears (5 per block x 50), 50 of which carry a bias; 234 dense tensors; 1
`rope.inv_freq`; 1035 total, all consumed. The `time_embedder.proj_in/proj_out` pair maps onto
diffusers' `TimestepEmbedding.linear_1/linear_2` with identical shapes and dtypes to the full BF16
checkpoint, and both were checked bit-exact against it.

### The rotation question: answered, and it cost nothing

This was the one thing that could have blocked the path. The denoiser's `comfy_quant` blobs declare
**two** group sizes, not one: 256 for the 200 attention/MLP Linears, and **64** for the 50
`adaln_proj.linear`s -- necessarily, since their 2688 inputs are not a multiple of 256. The recovered
`data/convrot-hadamard-256.safetensors` only covers order 256.

A second least-squares recovery pass turned out to be unnecessary. The recovered order-256 sign
matrix is *exactly* the fourth Kronecker power of

    A = [[ 1,  1,  1, -1],
         [ 1,  1, -1,  1],
         [ 1, -1,  1,  1],
         [-1,  1,  1,  1]]

(checked with `torch.equal`, not `allclose`), and `A[0,0] = +1`, so the leading `4^j x 4^j` block of
`A^(x)k` is `A^(x)j`. The order-64 rotation is therefore the top-left 64x64 block of the file we
already have. `convrot_rotation()` returns it and asserts exact orthogonality before handing it out.

Confirmed against real weights rather than only algebra, by least-squares recovery from the full
BF16 diffusers checkpoint against the int8 file (row slices through the pread reader, ~100 MB total,
under the watchdog):

| Linear | Group | sign agreement | `max|W R - W'|` | int8 half-step |
| --- | ---: | ---: | ---: | ---: |
| `blocks.0.adaln_proj.linear` (4 column groups) | 64 | 1.000000 | 2.105e-3 | 2.161e-3 |
| `blocks.0.attn.qkv_proj` | 256 | 1.000000 | 3.523e-3 | 3.527e-3 |
| `blocks.3.mlp.fc2` | 256 | 1.000000 | 3.408e-3 | 3.410e-3 |
| `blocks.3.attn.out_proj` | 256 | 1.000000 | 5.653e-3 | 5.708e-3 |

Every residual sits *at* the rounding floor and none above it, which is as tight as this can be: the
rotation is right, the group sizes are right, and the scale is per output row. Nothing is left
unresolved about the rotation, and no further download or recovery run is needed.

### What the loader does differently on the int8 path

* **No pruned-AdaLN module swap.** The stock diffusers modules and the stock arithmetic (silu, then
  the 2688-wide projection) run unchanged; `make_pruned_adaln_modules` is not used.
* **350 `nn.Linear`s become `ConvRotLinear`** -- the same class and the same dequant arithmetic the
  INT8 text encoder has been using, reused as-is. The only new work is the *row algebra*: Comfy's
  fused `qkv_proj` is sliced into `to_q`/`to_k`/`to_v` and its `[gate ; value]` `mlp.fc1` is
  half-swapped into diffusers' `[value ; gate]` `ff.net.0.proj`. Both act on the output axis, which
  is the axis the per-row scale is indexed by, so **weight and scale must be sliced and swapped
  together**. That pairing is what `scripts/test_convrot_linear.py` pins, including a negative case
  that swaps the weight without the scale and checks the result is grossly different.
* **`compute_dtype=bfloat16` is pinned on the 50 AdaLN Linears.** diffusers calls
  `get_parameter_dtype(self.linear)` before invoking them; a `ConvRotLinear` has no Parameters, so
  that walk falls through to its first floating-point buffer -- the float32 scale. Unpinned, the
  activation would arrive float32, the int8 weight would widen to float32 (1.04 GB transient instead
  of 520 MB) and the modulation would return float32 and promote the entire packed sequence. bf16 is
  also what the unpruned checkpoint stores, so this matches the reference rather than departing from
  it.
* One small wart fixed while there: `ConvRotLinear` applied its scale through a hardcoded `.float()`,
  which *narrows* a float64 activation. It now promotes to at least float32 instead. Bitwise
  identical for every dtype the cards run; it is what lets the unit test hold a float64 reference.

### The int8 split plan (256x448x124, STEPS=8)

```
blocks                : 50           per-block bytes : 646.3 MB   (pruned: 774.2 MB)
non-block bytes       :  1.723 GB    1.605 GiB
split_index           : 24           -> blocks 0..23 | 24..49
card 0 (primary)      : 17.235 GB   16.051 GiB       (pruned: 18.797 GiB)
card 1 (secondary)    : 16.804 GB   15.650 GiB       (pruned: 18.747 GiB)
imbalance             : 430.6 MB                     (pruned:  54.1 MB)
of which quantized    : 32.314 GB   30.095 GiB       int8 weights + f32 scales + biases
rotation per card     :  139.3 kB                    one bf16 256x256 + one 64x64
transient dequant peak:  520.2 MB    0.484 GiB       <-- must stay free ON TOP of the resident bytes
worst card + transient: 17.755 GB   16.536 GiB       -> 15.464 GiB free on a 32 GiB card
```

The imbalance is larger than the pruned form's because the block granularity (646 MB) is now large
relative to the non-block total; it is still well inside one block and both cards have >15 GiB free.

### CPU gates, both denoisers

`./smoke_h3.sh dry` now runs the dry run for **both** denoisers and then the ConvRot unit test.

| | pruned | int8 |
| --- | --- | --- |
| checkpoint tensors consumed | 532 / 532 | 1035 / 1035 |
| diffusers parameters accounted for | 639 / 639 (634 dense + 4 replaced by `adaln_t_table` + `rope.inv_freq` recomputed) | 639 / 639 (238 dense + 400 quantized-substituted + `rope.inv_freq`) |
| left over, either side | 0 | 0 |
| `--verify-remap` | 14/14 exact | 16/16 (9 dense exact, 7 dequant at the int8 floor) |

The "639 diffusers parameters" figure is not a count this script invents: it is read out of the full
BF16 checkpoint's `weight_map`, which is the authoritative parameter list, so the dry run stays
torch-free and diffusers-free while still checking the diffusers side. Separately, every produced
parameter's shape was compared against that checkpoint's headers: **0 mismatches on the int8 path**
across all 638 stored parameters, and 51 on the pruned path -- which are precisely the 50 block
`adaln_proj.linear` weights plus `norm_out.linear`, i.e. the pruning itself.

`scripts/test_convrot_linear.py` (CPU, ~1.2 MB read from the real file) covers: the
`((x R) Q^T) * scale + b` identity bitwise against a float64 reference; the folded form to float64
rounding; the int8 error floor; bitwise determinism in float64 and bf16; `compute_dtype` /
`out_dtype`; the group-size guard; the row-slice and half-swap pairing plus the negative case; the
Kronecker structure and exact orthogonality of both rotation orders; and a real 64-row slice of
`blocks.0.attn.out_proj` (group 256) and `blocks.0.adaln_proj.linear` (group 64) pushed through the
module.

### Still open

* **`--steps` is still a guess.** Nothing about the int8 build changes that; the turbo LoRA in the
  audit's recommendation 2 is still undownloaded.
* **Which denoiser is actually better** is still undecided and cannot be decided on CPU. Both paths
  now load, which is what makes the question answerable at all: same canvas, same seed, same
  conditioning via `--prompt-embeds`, one difference. That A/B is step 7 of the first-light plan, and
  it runs *after* the pruned control passes.
* **Nothing here has touched a card.** The host is still in the GPU-fault halt from session 10.
