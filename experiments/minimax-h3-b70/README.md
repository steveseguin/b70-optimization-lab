# MiniMax-H3 on the two-B70 host: lane packet (opened 2026-09-17)

Status (2026-09-19): **FIRST LIGHT. The pipeline renders a clip on two cards, and it repeats bit for
bit.** On 2026-09-19 18:16-18:28 EDT the pruned BF16 denoiser, split across both B70s at block 24,
produced a 448x256, 124-frame, 5.17 s clip with 32 kHz stereo audio in **83 s of wall time** (`sample`
**17.68 s** for 8 NFE), and two further runs at the same seed matched all four hashes --
`REPEAT GATE: bytewise-equal`, without `--deterministic`. The INT8 ConvRot path rendered the same
prompt in the same window at **30.80 s of sampling** (1.74x slower: no fused int8 GEMM on XPU, so
every weight is widened to bf16 on every step). Measured card peaks came in at or under the
`--plan-memory` budget everywhere, and `sample` came in **3.6 GiB under**, which says the XPU is not
materializing the attention matrix. Zero `xe` fault lines. Full account, the five blockers it took to
get here, the memory table and the INT8-vs-pruned numbers:
[first light](notes/2026-09-19-first-light.md); receipts in
[`data/2026-09-19-first-light/`](data/2026-09-19-first-light/).

Next: the canvas walk toward the trained 544x960 with a 320x576 step first (read the `[vram]` lines),
the 51-step base schedule against the 9-step turbo LoRA, and a small prompt set before either
denoiser is called the lane's default.

Earlier status (2026-09-18), for the record: **all weights on disk, both denoisers loadable, no clip
generated yet.** The
full INT8 ConvRot denoiser finished downloading (34.04 GB, 1035 tensors, header data-end == EOF), so
`scripts/run_h3_t2v.py` now has two denoiser load paths -- `--denoiser {pruned,int8}`, env
`B70_H3_DENOISER`, default still `pruned`. Both pass the CPU dry run with exact coverage. First light on 2026-09-18 03:05 UTC died
in the text-encoder load and took the user's desktop session with it (a 4 GiB cgroup ceiling on a 27 GB load,
beside a kernel build, on a 15 GiB host). The lane is gated on a CPU host-memory measurement and now runs under
`scripts/mem-watchdog.sh`: [first-light plan](notes/2026-09-18-first-light-plan.md).

**2026-09-18, the step count is no longer a guess.** `num_inference_steps` in this scheduler counts
*sigma grid points* with the terminal zero included, so it drives `steps - 1` transformer
evaluations (`MiniMaxH3Scheduler.set_timesteps`, `scheduling_minimax_h3.py:133-136`) -- and every
step count published upstream is the other kind of count. `--steps` therefore defaults to **51**
(the reference runner's 50 NFE + 1), and the **8-step turbo LoRA** is on disk and wired into
`--lora PATH[:scale]`, which makes **9** (8 NFE) legitimate. There is no `guidance_scale` to set at
any step count: the checkpoint is CFG-distilled and every step is one forward pass. Full citation
list and the LoRA key mapping: [notes/2026-09-18-steps-and-lora.md](notes/2026-09-18-steps-and-lora.md).

## What the model is

[MiniMaxAI/MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) is not a language model. It is a video-with-audio
generation system (text/image/reference to video, 4-15 s, 24 fps, 32 kHz stereo, license: MiniMax-H3 Community License):

| Component | Parameters / size (BF16) | Role |
| --- | ---: | --- |
| `transformer` (H3-Base-FL2VA, first/last-frame mode) | ~33B, 66.3 GB | the video+audio diffusion denoiser |
| `transformer_ref` (H3-Base-Ref2VA, reference mode) | ~33B, 66.3 GB | the reference-input denoiser (separate checkpoint) |
| `text_encoder` (Qwen3-VL 32B) | 66.7 GB | prompt and image understanding, run once per generation |
| `vae` (video), `audio_vae` | 10.4 GB, 0.6 GB | decode latents to frames and audio |

So the "llama.cpp or vLLM" question does not apply: it runs as a diffusers-style pipeline (PyTorch), or through
stable-diffusion.cpp with the GGUF builds. The lab's [LTX 2.5 lane](../ltx25-b70/README.md) is the precedent: a
PyTorch XPU pipeline with the BF16 transformer split across two cards and the encoder and decoder on others.

## What fits two 32 GiB cards without giving up quality

The BF16 denoiser alone (66 GB) does not fit two cards with activations. Third-party builds, largest first:

| Build | Denoiser | Text encoder | Notes |
| --- | ---: | ---: | --- |
| Comfy-Org `minimax_h3_fl2va_int8_convrot` | 34.0 GB (full, INT8 rotation-quantized) | `qwen3vl_32b_..._int8_convrot` 27.1 GB | the largest denoiser that splits across two cards; ComfyUI's INT8 ConvRot dequant would have to be ported to XPU |
| Comfy-Org `minimax_h3_fl2va_pruned_bf16` | 40.2 GB (BF16, **pruned**) | same | "pruned" = the timestep embedder and the blocks' AdaLN projections replaced by a `adaln_t_table [1025, 8]` plus per-block `adaln_proj` weights of 8 inputs instead of 2,688 (header comparison, 2026-09-17): the per-timestep modulation is re-parameterised through an 8-dimensional table. **Measured** ([note](notes/2026-09-17-adaln-table-exactness.md)): a rank-8 affine fit of the timestep-modulation curve, not exact; worst error 8e-4 / 1.2e-3 on values spanning +-3.3 / +-7.3 (blocks 0 / 25), *below* the unpruned BF16 weights' own error against float32 (4e-3 / 7e-3). ComfyUI interpolates the table linearly between the 1/1024 grid points; snapping would cost 5x more. Fidelity rank on two cards: pruned BF16 > INT8 ConvRot |
| unsloth `MiniMax-H3-FP8.pt` / Comfy `fl2va_pruned_fp8_scaled` | 20-21 GB (pruned + FP8) | same | quantized on top of the pruned form |
| unsloth GGUF `fl2va_pruned-Q8_0` | 20.0 GiB (pruned) | `qwen3vl_32b_minimax_h3-Q4_K_M` 17 GiB | stable-diffusion.cpp (SYCL backend exists); text encoder on CPU needs more than this host's 15 GiB RAM, so it would run on the second card |

The user's brief is best quality that fits comfortably, no quality loss by design. No two-card option is exact: the full BF16 denoiser needs four cards. Ranked by fidelity: (1) the **pruned BF16
denoiser (37 GiB) split across the two cards** (rank-8 AdaLN fit, error below the BF16 noise floor), (2) the full denoiser at
INT8 ConvRot (34 GB, quantization error), (3) pruned + FP8/GGUF.

### The fidelity choice, and what each load path actually does

Both denoisers are on disk and both are loadable (`--denoiser {pruned,int8}`, env `B70_H3_DENOISER`, default `pruned`).
Neither is exact, and they are not on a single quality axis -- they put the error in *different places*, which is why
each one is the other's control:

| | `--denoiser pruned` (default) | `--denoiser int8` |
| --- | --- | --- |
| File | `minimax_h3_fl2va_pruned_bf16.safetensors`, 40.23 GB, 532 tensors | `minimax_h3_fl2va_int8_convrot.safetensors`, 34.04 GB, 1035 tensors |
| Block-stack weights | **exact** released BF16, bit for bit (verified against the full diffusers checkpoint) | **int8**, rotate-then-quantize, per-output-row float32 scale -- 250 of 250 block Linears |
| AdaLN / timestep branch | **approximated**: `adaln_t_table [1025, 8]` rank-8 fit, linearly interpolated; the timestep MLP and all 50 `adaln_proj` projections are re-parameterised | **exact in form**: the unpruned `time_embedder.proj_in/proj_out` and `adaln_proj.linear` 2688 -> 96768 are present, so the stock diffusers modules and stock arithmetic run unchanged (the projection weights are themselves int8) |
| Measured error | 8e-4 / 1.2e-3 on values spanning +-3.3 / +-7.3, i.e. *below* the BF16 weights' own error against float32 (4e-3 / 7e-3) | at the int8 rounding floor everywhere it was checked: `max|W R - W'|` = 2.1e-3 against a half-step of 2.2e-3 (adaln), 3.5e-3 vs 3.5e-3 (qkv), 4.7e-3 vs 4.7e-3 (out_proj) |
| What the loader does | installs `AdaLNTableEmbedder`, `PrunedAdaLNModulation`, `PrunedAdaLNOut` in place of the stock modules; `time_proj` becomes an identity | **no module swap at all**; 350 `nn.Linear`s become `ConvRotLinear`, the same class and dequant arithmetic the INT8 text encoder already uses |
| Card residency (256x448x124) | 18.797 / 18.747 GiB, split at block 24 | 16.051 / 15.650 GiB, split at block 24, **plus a 0.484 GiB transient** (the largest quantized weight widened to bf16 for one `F.linear`) |

The pruned build keeps the residual stream exact and approximates only the modulation; the int8 build keeps the
modulation structurally exact and quantizes the residual stream. On paper the pruned one wins, because its
approximation is measurably smaller than the noise floor of the format it is stored in, while int8 touches every
weight -- but that comparison is a header-level argument plus a CPU curve fit, and it stays that until both have
rendered the same prompt at the same seed. That A/B is the point of having both paths.

**The ConvRot rotation is shared, and nothing new had to be recovered.** The denoiser's attention and MLP Linears
declare `convrot_groupsize: 256` -- the rotation already in `data/convrot-hadamard-256.safetensors`. Its `adaln_proj`
declares `convrot_groupsize: 64`, because its 2688 inputs are not a multiple of 256. That order-64 rotation turned out
to be the *leading 64x64 block* of the one already recovered: the recovered order-256 sign matrix is exactly the fourth
Kronecker power of the symmetric order-4 Hadamard matrix, and since its `[0,0]` entry is +1, every `4^j` leading block
is the order-`4^j` member of the same family. Confirmed against real weights, not just algebra (see the table row
above). So one 65 KB file supplies both orders, for the denoiser, the encoder and the VAE alike. The text encoder can stay exact (BF16, 51.5 GB, streamed
layer by layer once per prompt) or use the INT8 ConvRot build (27 GB). The plan here is (1) with the streamed BF16 encoder,
and the full BF16 model on the four-card host as the reference for measuring the pruned form's actual output difference, with the INT8 text encoder run first on one card and
unloaded, and the fp16 video VAE (5.2 GB) plus audio VAE. The pruned builds are a fallback, not the plan, until their
quality is measured against the full one. The BF16 denoiser is kept as the reference/source (a BF16 reference run
needs the four-card host, 128 GiB).

## Downloaded to this host

`/mnt/fast-ai/llm-models/minimax-h3` (original: `transformer/`, `vae/`, `audio_vae/`, schedulers, processor,
tokenizer, docs; the BF16 text encoder is skipped for disk) and `/mnt/fast-ai/llm-models/minimax-h3-comfy`
(the **pruned BF16** denoiser, the INT8 ConvRot text encoder, fp16/fp32/int8 VAEs).
Script: `/mnt/fast-ai/llm-models/minimax-h3-download.sh`.

**Update, 2026-09-18:** the full INT8 ConvRot denoiser is now complete on disk (34,038,892,334 bytes, 1035 tensors,
the header's declared data end matches the file's last byte), superseding the [disk audit](notes/2026-09-18-disk-audit.md)'s
"15.7 %" line. Everything else in that audit still holds and everything listed above is size-verified against the
Hugging Face repos.

Detailed stand-up plan: [notes/2026-09-17-pipeline-plan.md](notes/2026-09-17-pipeline-plan.md).
First-light sequence, go/no-go rule and failure playbook:
[notes/2026-09-18-first-light-plan.md](notes/2026-09-18-first-light-plan.md).
CPU gates that must pass before any GPU run (`./scripts/smoke_h3.sh dry` runs all three):
`run_h3_t2v.py --dry-run --verify-remap` for **both** denoisers -- every checkpoint tensor consumed, every one of the
639 diffusers parameters produced or explicitly substituted, 0 left over either way -- plus
`scripts/test_convrot_linear.py`, which pins the INT8 ConvRot dequant arithmetic on CPU (a float64 synthetic case,
bitwise determinism, the weight/scale row pairing that the qkv split and the SwiGLU half swap depend on, and a real
64-row slice of the 34 GB checkpoint read through the pread reader), plus `scripts/test_lora.py`, which pins the LoRA
merge and the ConvRot runtime term against float64 references and re-checks the real turbo file's mapping.

### The 8-step turbo LoRA (`--lora`)

`loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` (1.956 GB, 208 pairs, rank 128 /
384-for-fused-qkv, alpha/rank = 0.0625 everywhere). Its keys are *Comfy checkpoint module names*, so
it reuses the weight remap the loader already has -- the qkv row split and the SwiGLU half swap both
act on `lora_B`'s output axis exactly as they act on the weight's rows, and `lora_A` is taken whole.
Dry run on both denoisers: **208/208 pairs matched, 0 unmatched**, giving 312 destinations on
`pruned` and 12 + 300 on `int8`.

The two paths are *not* the same arithmetic, and the difference is deliberate:

| Destination | How the adapter is applied | Cost |
| --- | --- | --- |
| dense BF16 weight | **merged at load**, `W + s*(B@A)` in float32, rounded once into the destination dtype -- exact | 0 resident; a 616 MB float32 transient on the card, one weight at a time |
| `ConvRotLinear` (int8) | **additive runtime term**, `y = dequant(W) x + s*B(A x)` -- the int8 weight cannot absorb a merge without re-quantizing, which would replace the measured rounding-floor error with a larger one | 2.294 GB resident across both cards, one rank-`r` GEMM pair per Linear per step |

The adapter adapts `W`, not Comfy's rotated `W R`, so on the ConvRot path the term is built from the
**unrotated** activation; `test_lora.py` section 4 pins that against the wrong variant. The LoRA
path, scale, sha256 and the merged/runtime split are recorded in `receipt.json`.

Host-memory safety: `scripts/mem-watchdog.sh` (kills our job before systemd-oomd kills the session) and
`scripts/profile-encoder-load.py` (CPU-only measurement of the loaders' host footprint). That measurement was a
NO-GO on the `safetensors.safe_open` path -- RssFile grew with every byte touched, 6.29 GiB at a 6 GiB budget,
because a mapped page cannot be dropped with `posix_fadvise` -- so both load loops now use a `pread` reader that
never maps the file (`B70_H3_LOADER=pread|mmap`, default `pread`; bitwise-checked against `safe_open` by
`scripts/test_tensor_reader.py`). Re-measured: 1.663 GiB encoder, 0.792 GiB denoiser, RssFile flat at 0.07 GiB.

## Next steps (not started)

1. ~~Read the official `scripts/` and `model_index.json` for the pipeline (schedulers, sampling steps, guidance; H3 is
   distilled and CFG-free).~~ **Done 2026-09-18** -- shift 12 / 3, rectified-flow Euler (eta 0), no guidance parameter
   exists, `--steps` 51 base / 9 with the turbo LoRA. See [notes/2026-09-18-steps-and-lora.md](notes/2026-09-18-steps-and-lora.md).
2. Stand up the PyTorch XPU pipeline from the LTX lane's pattern: text encoder pass, denoiser split over two cards,
   VAE decode; first with the BF16 denoiser offloaded (slow, correctness reference), then INT8 ConvRot.
3. Measure: a fixed prompt set, exact repeat determinism, time per clip, and INT8 vs BF16 reference frames.
