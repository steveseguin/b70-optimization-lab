# MiniMax-H3 audio and video on two Intel Arc Pro B70s — review draft

**Draft, 2026-10-10. Research status; expert audience; not published or approved.**
MiniMax-H3 generates video with audio. It is not MiniMax M2.7, the language model.
The best retained batch made eight clips in **3173 seconds**, or **396.625 seconds
per clip** (396.6 rounded). Each clip has **124 frames at 960×544**, played at
**24 fps**, with **32 kHz stereo audio**. Generation is **0.313 frames/second**,
not real time. The older single-clip base schedule is recorded at **800.8 seconds**;
the historical ratio is **2.02×**. [Receipts and calculation](EVIDENCE.md).

The scheduling and decoding changes preserve the tested lane's output hashes.
However, that lane uses a **pruned BF16 denoiser and an INT8 ConvRot text encoder**.
It has not established equality to the full official BF16 model. “Lossless” in
older lane notes means unchanged relative to this local reference, not lossless
pruning or quantization. Under the current owner rules this cannot become a
lossless official-model headline. Public input closure and owner review are also
pending. [Decisions and promotion procedure](OWNER-REVIEW.md).

## Exact measured identity

| Field | Retained identity |
| --- | --- |
| Run | `duet-20261004T042838Z`, eight distinct prompts, one batch, seed 42 for each clip |
| Host / topology | `steve-TURIND8-2L2T`, two Arc Pro B70s, nominal 32 GiB each; model split at block 25, one sampling process per card |
| Workload | Text-only FL2VA partition (`t2va`); 960×544; 124 frames; 51 sigma grid points = 50 transformer evaluations (NFE) |
| Sampler | Base schedule, rectified-flow Euler; video/audio shifts 12/3; no guidance scale; no LoRA |
| Denoiser | `minimax_h3_fl2va_pruned_bf16.safetensors`; BF16 block weights, approximate rank-8 AdaLN table; AdaLN compute FP32 and output BF16 |
| Encoder | `qwen3vl_32b_minimax_h3_int8_convrot.safetensors`; INT8 ConvRot, Hadamard256; prompt computed independently for each clip |
| Decode | Official video/audio VAEs; FP32 video arithmetic, `vae_autocast=off`, tiling on; two-process persistent video decode and overlapped audio |
| Transfer / loader | Host-staged inter-card transfer, `pread`; `PYTORCH_ALLOC_CONF=expandable_segments:True` |
| Runtime | Python 3.12.3; torch 2.14.0+xpu; diffusers 0.41.0.dev0; transformers 5.17.0 |
| Source inventory | diffusers `7221eef4573574925b67a69e9fc1482bf093e569`, from [environment inventory](../data/environment.txt); editable checkout cleanliness not bound by the run |
| Lab evidence commit | `34ec68887431c9d64a5688aa35a5e220ddaa5e69` retains the soak and corresponding source; a reconstruction anchor, not a source hash recorded inside the runtime receipt |
| Determinism | Observed receipt equality; `deterministic=false` in receipts. Do not claim strict deterministic-algorithm mode was enabled |
| Output file | libx264, CRF 16, `mbtree=0`, bitexact muxer; repeatable encoding does not mean lossless H.264/AAC compression |

The complete argv, settings, prompt, shapes and output hashes are in each
[soak receipt](../data/2026-10-04-soak8/). The exact
[prompt list](../notes/h3-soak8-prompts.txt) and all eight receipt paths are in
[EVIDENCE.md](EVIDENCE.md). There is no LLM KV cache or speculative decoder here.
The measured batch amortizes weight loading; it does not reuse another prompt's
conditioning or response. It is not a one-clip cold-start latency measurement.

## Official weights, actual weights and missing pins

The official source is
[MiniMaxAI/MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3).
A metadata-only lookup on 2026-10-10 resolved the official repository to
**`42ed227ee7df40d41602854ae760620d6eb651fe`**. This is a review-time source pin,
**not a verified revision for the files used in the historical run**. The run's
model revision is **not recorded**. Matching every measured file's full hash to
that revision remains a publication gate. The
[official card at that revision](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/README.md)
describes the 33B model and distinguishes the released base model from hosted
components. This packet measures only the configuration above.

| Input needed for this historical replay | Source and retained verification |
| --- | --- |
| Pruned denoiser | `Comfy-Org/MiniMax-H3`, `diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors`; historical repo revision and full-file SHA256 absent; only header SHA256 recorded |
| INT8 encoder | Same Comfy repository, `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors`; historical revision/full-file hash absent |
| VAEs, configs, tokenizer, processor and schedulers | Official repository: `vae/`, `audio_vae/`, `transformer/config.json`, `text_encoder/` configuration files, `tokenizer/`, `processor/`, `scheduler/`, `audio_scheduler/`; complete revision-bound file manifest absent |
| ConvRot matrix | `data/convrot-hadamard-256.safetensors` under the lane; SHA256 `ebb89aa1651e681f49461fe539bf2eb6fba0143c2733e5ad9cef438d48fb28d2`; ignored by Git; [recovery script](../scripts/recover-convrot-rotation.py) needs the separate Comfy FP16/INT8 video VAE pair |
| Remap test reference | Full official `transformer/` shards; needed by the existing CPU remap test even though the measured generation uses the pruned file |

The pruned denoiser's **header-only** hash is
`59916d0f1ea260e0d9e0ce7a3cb2ceb4d59ecbb08a9f2e466de009cbc6fe26c0`.
It is not a weight-file integrity check. Comfy's review-time repository revision
is `e5eb578a89295337b8ff433a035929ce0279e0b6`, also unbound to the historical bytes.
Neither current revision is substituted for a missing benchmark pin.

The owner now allows official publisher or Unsloth downloads by default. A new
Comfy download requires a written justification and explicit approval. No weights
were downloaded for this draft. Before providing download commands, recover the
historical revisions and full-file sizes/hashes, verify ordinary and direct-I/O
reads, and produce `DOWNLOAD-MANIFEST.txt`; seal verified files read-only. Using
new official or Unsloth weights needs a new matched benchmark and oracle.

## Hardware, installation and source restoration

Use the measured two-card Linux topology on an otherwise idle, authorized host.
The originating machine has 15 GiB host RAM. The wrapper requires at least
11264 MiB available before starting and keeps its memory watchdog at a 2048 MiB
floor. The soak log records a lowest available reading of 5643 MiB. These are
admission/observed values, not a portable minimum-RAM qualification. Complete
process-tree peak VRAM for the eight-clip profile is **not retained**; coordinator
allocator counters do not measure the separate sampling/decode workers.

A complete disk requirement and clean supported-OS installation are not yet
qualified. Space must cover both measured checkpoints, official VAEs/configs,
CPU remap references, rotation-recovery inputs, the runtime and output evidence.
The [disk audit](../notes/2026-09-18-disk-audit.md) records historical sizes only;
it is not a current capacity check or a complete hash manifest.

The lab implementation is in [run_h3_t2v.py](../scripts/run_h3_t2v.py),
[h3_duet.py](../scripts/h3_duet.py),
[h3_vae_duet.py](../scripts/h3_vae_duet.py) and
[h3_audio_proc.py](../scripts/h3_audio_proc.py).
Use [smoke_h3.sh](../scripts/smoke_h3.sh) with its required
[mem-watchdog.sh](../scripts/mem-watchdog.sh). The
[environment inventory](../data/environment.txt) records observed packages,
including PyAV 18.1.0 and Intel runtime wheels 2026.1.0; it is not a wheel lock.
[setup-venv.sh](../scripts/setup-venv.sh) uses a pre-existing editable diffusers
checkout and installs some unpinned dependencies. Its final check queries XPU.
It is not a CPU-only validation command or a publicly closed installer.

Before replay, publish an immutable runtime/build inventory, all local deltas,
portable input paths, the verified rotation input or fully closed recovery
recipe, and a clean-build log. Existing runner defaults use originating-host
`/mnt/fast-ai` paths. No Docker image/digest or clean-host installer is certified.
Do not run the setup script merely to check this document.

## Recorded replay procedure — future authorized experiment only

**Nothing in this section was executed by this CPU-only drafting task.** These
are exact existing-runner commands for an already reconstructed two-card lab
host. The missing inputs above must be restored first. Current host rules and
fault admission still apply. Publication approval alone is not GPU authorization.

From the repository root, the wrapper's CPU mode checks headers/remaps, tensor
reader, ConvRot, LoRA mapping and VAE tile-loop equivalence:

```bash
nice -n 19 env OMP_NUM_THREADS=2 LORA= B70_H3_LORA= \
  HEIGHT=544 WIDTH=960 FRAMES=124 STEPS=51 SEED=42 \
  bash experiments/minimax-h3-b70/scripts/smoke_h3.sh dry
```

This still requires model files and the lane CPU venv. It was not run here.
Tests: [ConvRot](../scripts/test_convrot_linear.py),
[tensor reader](../scripts/test_tensor_reader.py),
[LoRA remap](../scripts/test_lora.py),
[tile loop](../scripts/test_vae_tile_loop.py).

The historical standalone reference can be reconstructed with `repeat`,
`LORA=`, `B70_H3_LORA=`, `STEPS=51`, `VAE_AUTOCAST=off` and
`VAE_DECODE=single`. Keep both resulting receipts and time each full process
using the same timer boundary as the candidate. Do not silently use the
wrapper's auto-detected turbo defaults.

For an eight-clip candidate against the retained soak on that host:

```bash
export OMP_NUM_THREADS=2
export LORA= B70_H3_LORA= STEPS=51 SEED=42
export HEIGHT=544 WIDTH=960 FRAMES=124 SPLIT_INDEX=25
export VAE_DECODE=two-proc VAE_AUTOCAST=off VAE_SERVE=1 AUDIO_OVERLAP=1
export B70_H3_LOADER=pread B70_H3_XFER=host
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PROMPTS_FILE="$PWD/experiments/minimax-h3-b70/notes/h3-soak8-prompts.txt"
export OUT_ROOT=/mnt/fast-ai/bench-results/minimax-h3
for i in 0 1 2 3 4 5 6 7; do
  printf -v clip '%02d' "$i"
  export "BATCH_REF_${i}=duet-20261004T042838Z/clip-${clip}"
done
nice -n 19 /usr/bin/time -p \
  bash experiments/minimax-h3-b70/scripts/smoke_h3.sh duet
```

`BATCH_REF_*` is relative to `OUT_ROOT`, not an absolute path. Missing references
must fail the comparison; never replace them with the candidate's own outputs.
The wrapper chooses a new timestamped run name and writes receipts/logs. Its
preflight and watchdog are compulsory. The current source includes the later
piecewise-transfer change; this command therefore **does not reproduce the
exact historical source snapshot** and receives no inherited 396.6-second claim.
For historical source review use commit `34ec68887431c9d64a5688aa35a5e220ddaa5e69`;
any new build needs its own source hash, health admission and measurements.

This is a finite batch experiment, not a resident service. There is no H3 HTTP
health endpoint in this recipe. Keep per-process completion, exit codes, kernel
fault evidence and watchdog summaries. Let the batch finish normally; stop new
work on a fault and preserve evidence. A portable graceful-stop command and
worker teardown verification still need qualification before a package launcher
is advertised. Do not use the old service-restore scripts or a forced group kill
as routine cleanup, and leave the cards empty after an authorized experiment.

## Timing and output checks

Measure complete batch wall time, including startup/loading/encoding/decode/write,
and divide by the completed clip count. Publish all registered repeats. The
retained log rounds wall time to whole seconds; it does not retain a precise
start/end timer contract. Re-register that boundary for a new comparison.
Do not sum overlapping `sample.i` timers, nested encoder timers or the receipt's
`seconds_per_second_of_video`: those are not this batch wall metric.

Report first-clip latency separately when measured. The current eight-clip
batch samples the batch before decoding: **396.625 seconds is an amortized
throughput figure, not time to first clip or delivery interval**. Prompt reading
is **not measured as a standardized prefill rate**; encoder phase timers exist
but do not constitute an LLM 512-token prefill benchmark. Token decode, context
curves and many-user token rates are not applicable to this video packet.

The four exactness fields are video tensor, audio tensor, video latent and audio
latent SHA256. Compare all four for each fixed prompt/seed against the unchanged
reference, and compare `clip_mp4_sha256` separately. The soak log reports 32/32
matches to September's eight-clip reference; those older reference files need
recovery. The later two-clip transfer gate has both sides retained and matches
all four tensors plus MP4. The three MP4-repeat sessions use 8 NFE, so they do
not certify 50-NFE full-suite fresh-process determinism.

Human review of motion, faces, temporal/tile seams, sound and synchronization is
pending. Independent clips joined into a feed are not continuous generated
scenes. There is no H3 continuation-seam acceptance or 24/7 service qualification
here; LTX's separate evidence cannot fill that gap.

## Known publication gaps

- Owner-approved significance threshold and publication selection; current rule
  forbids a pruned-model lossless headline.
- Exact historical official/Comfy revisions, complete weight hashes, full base
  receipts and a runtime/source/optimization identity bound to the run.
- Matched fresh-process full-suite timing and deterministic repeats, with the
  reference oracle available in-repository or a public hash-addressed bundle.
- Registered video quality review and audio/seam acceptance; no valid all-pass
  promotion attestation for this headline.
- Portable installer, source closure, qualified stop/health path, release assets
  and both local/remote recipe-publication validation. Clean-host replay pending.

Keep `library.featured_metric: null` if a research package is separately approved.
Use scoped video observations with explicit pending status, not a token-speed
chart or a fabricated performance curve. This draft changes no site input.
