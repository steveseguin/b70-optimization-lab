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
