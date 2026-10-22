# MiniMax-H3: video with audio on two B70 cards

MiniMax-H3 turns a text prompt into a short video clip with stereo sound. This
package runs it on two Intel Arc Pro B70 cards as a finite batch of clips. There
is no server and no chat endpoint. The runtime has not been rebuilt from public
sources yet, so a new machine cannot follow this guide from start to finish
today; it is written for experts who can restore the historical runtime.

**Owner-approved target and result; expert research package. The public rebuild
recipe is incomplete.** One retained eight-clip batch took **3173 seconds**, or
**396.6 seconds per clip**. Each clip is 124 frames at 960×544, played at 24 fps,
with 32 kHz stereo audio. This is whole-batch time divided by eight, not the wait
for the first clip or an observed delivery cadence.
[Measured result](featured-observation.json) · [session receipt](../../experiments/minimax-h3-b70/data/2026-10-04-soak8/session.log).

Comfy-Org's published pruned BF16 denoiser (`minimax_h3_fl2va_pruned_bf16.safetensors`): all weights bit-exact with the official checkpoint except the AdaLN tables, which that release replaces with a fitted approximation (lab analysis: below the BF16 noise floor); the 2x result is an exact scheduling speedup against that denoiser's own reference (32 MATCH / 0 DIFFERS, 8 repeat passes). The comparison is to an 800.8 s/clip **ledger-recorded baseline, raw
receipts not retained**. The historical ratio is 2.019×; this is not a newly
matched baseline measurement. The eight repeat passes are eight clip comparisons
in one batch, not eight independently timed batches.

“Pruned” in filenames means the timestep network and large AdaLN projections
were replaced by a rank-8 fitted table and small projections. It does not mean
blocks were removed. This variant is not lossless versus the official model.
The separate INT8 ConvRot encoder is quantized. The
[AdaLN investigation](../../experiments/minimax-h3-b70/notes/2026-09-17-adaln-table-exactness.md)
measured modulation error in blocks 0 and 25 and the output layer, not end-to-end
official-model parity or all 50 blocks. The
[owner decision](owner-decision.json) accepts this trade and authorizes publication.

## Before you start

| Need | Tested with / required |
| --- | --- |
| Cards | Two Intel Arc Pro B70, 32 GiB each, with nothing else on them. The runner uses Level Zero devices 0 and 1; each denoiser worker sets `ZE_AFFINITY_MASK` to its own card, and the text encoder runs on card 0. The model is split at block 25. |
| Host | turin (`steve-TURIND8-2L2T`), the measured host and recipe target. No other host has run it. |
| OS and kernel | Linux. Distribution and kernel version: not recorded for this run. |
| GPU driver stack | Host kernel driver and Level Zero versions: not recorded for this run. The Python environment carries Intel 2026.1 runtime wheels ([environment inventory](../../experiments/minimax-h3-b70/data/environment.txt)). |
| Runtime | Native Python, no container: PyTorch 2.14.0+xpu, torchvision 0.29.0+xpu, torchaudio 2.11.0+xpu, transformers 5.17.0, diffusers 0.41.0.dev0 from `huggingface/diffusers` at `7221eef4573574925b67a69e9fc1482bf093e569`. Missing: complete editable diffusers source delta, clean build and runtime smoke. |
| Python | 3.12.3 in the GPU venv. The wrapper also uses a separate CPU venv; its contents are not recorded. Any `python3` with Git runs the CPU evidence check. |
| Host RAM | 15 GiB on turin. The wrapper refuses to start below 11264 MiB available memory, and its 2048 MiB memory watchdog is mandatory. The measured run's lowest available memory was 5643 MiB. These are recorded thresholds, not a portable minimum. |
| Disk | Model files: 45 files, 152,710,627,429 bytes (about 153 GB), per [model-manifest.json](model-manifest.json). GPU venv: about 10 GB (the setup script's own estimate). Output space: not recorded. |
| Other tools | `git`, `bash`, a systemd user session (`systemd-run --user --scope`), `ss`, `/usr/bin/time`. `docker` only if installed: the wrapper refuses to start while any container runs. |
| License | [MiniMax-H3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/LICENSE), with territory and revenue limits. Read [License and sources](#license-and-sources) first. |

Installing the Intel GPU driver is not covered or tested by this guide.

## Quick start

Run every command from the repository root after
`git clone https://github.com/steveseguin/b70-optimization-lab && cd b70-optimization-lab`.
Replace every `/path/to/...` with your own absolute directory, and use the same
directory in every step. Steps 1 and 2 cannot be completed from public sources
alone today; steps 3 to 7 describe the historical lab procedure on turin.

Anyone can check the published evidence first. It needs no weights and no GPU:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B \
  repro/minimax-h3-pruned-bf16-tp2-b70-20261004/verify-evidence.py
```

### 1. Download and verify the model

No download or verification script ships with this package.
[model-manifest.json](model-manifest.json) lists every file: 41 from
`MiniMaxAI/MiniMax-H3` at `42ed227ee7df40d41602854ae760620d6eb651fe` and 4 from
`Comfy-Org/MiniMax-H3` at `e5eb578a89295337b8ff433a035929ce0279e0b6`, each with
an immutable URL, byte size and SHA-256. Download each URL under the publisher's
license terms, and check its size and SHA-256 before use. No fitting step is
needed.

The historical runner reads fixed model roots and has no option to change them:
MiniMaxAI files go under `/mnt/fast-ai/llm-models/minimax-h3` and Comfy-Org
files under `/mnt/fast-ai/llm-models/minimax-h3-comfy`, each at its manifest
path. Portable model paths are a listed gap. For example, the two largest files:

```bash
echo 'a32572fb90b5508b201ec7c2eddcc184b13ddfd3c6f6d2cf06a0b46535d541b4  /mnt/fast-ai/llm-models/minimax-h3-comfy/diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors' | sha256sum -c -
echo 'bc2ced0fbea64757fa9acddccfc0b3f4819d1dcf1da6c124d690d368be283923  /mnt/fast-ai/llm-models/minimax-h3-comfy/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors' | sha256sum -c -
```

### 2. Get the runtime

There is no container and no prebuilt wheel. Restore the historical scripts
from the source anchor without switching branches or modifying the active lane:

```bash
export OMP_NUM_THREADS=2
export PYTHONDONTWRITEBYTECODE=1
export H3_REPLAY="$PWD/h3-replay"
mkdir -p "$H3_REPLAY"
git archive 34ec68887431c9d64a5688aa35a5e220ddaa5e69 \
  experiments/minimax-h3-b70/scripts experiments/minimax-h3-b70/notes/h3-soak8-prompts.txt \
  experiments/minimax-h3-b70/data/environment.txt | tar -x -C "$H3_REPLAY"
```

Then build the two Python environments. The GPU venv uses Python 3.12.3: install
the three XPU torch packages from `https://download.pytorch.org/whl/xpu`, then
the other exact versions in the
[environment inventory](../../experiments/minimax-h3-b70/data/environment.txt),
then diffusers from source at `7221eef4573574925b67a69e9fc1482bf093e569`. The
historical [setup script](../../experiments/minimax-h3-b70/scripts/setup-venv.sh)
is not a closed installer (see [Runtime and source reconstruction](#runtime-and-source-reconstruction)).
The wrapper also needs a CPU venv for its dry mode and its hash comparison; its
package list is not recorded. Tell the wrapper where both are (it defaults to
`/mnt/fast-ai/venvs/minimax-h3` and `/mnt/fast-ai/venvs/minimax-h3-cpu`):

```bash
export GPU_VENV=/path/to/venvs/minimax-h3
export CPU_VENV=/path/to/venvs/minimax-h3-cpu
```

The runner also needs the ConvRot rotation file next to its scripts. Recover it
on the CPU from the two video-VAE files, then check it against the recorded
SHA-256. This recovery was not rerun for this publication.

```bash
"$CPU_VENV/bin/python" "$H3_REPLAY/experiments/minimax-h3-b70/scripts/recover-convrot-rotation.py" \
  --fp16 /mnt/fast-ai/llm-models/minimax-h3-comfy/vae/minimax_h3_video_vae_fp16.safetensors \
  --int8 /mnt/fast-ai/llm-models/minimax-h3-comfy/vae/minimax_h3_video_vae_int8_convrot.safetensors \
  --out "$H3_REPLAY/experiments/minimax-h3-b70/data/convrot-hadamard-256.safetensors"
echo "ebb89aa1651e681f49461fe539bf2eb6fba0143c2733e5ad9cef438d48fb28d2  $H3_REPLAY/experiments/minimax-h3-b70/data/convrot-hadamard-256.safetensors" | sha256sum -c -
```

On a restored, authorized two-card host, the wrapper's `dry` mode
(`bash "$H3_REPLAY/experiments/minimax-h3-b70/scripts/smoke_h3.sh" dry`) checks
the remap, reader, ConvRot, LoRA mapping and VAE tile loop without the GPU. It
still reads the model files, so it was not run for this publication.

### 3. Start the server

There is no server. This step starts one finite batch of eight clips through
the mandatory [`smoke_h3.sh`](../../experiments/minimax-h3-b70/scripts/smoke_h3.sh)
wrapper. It runs the job in a user systemd scope with no swap and starts the
host-memory watchdog beside it. Use it only on an idle, authorized two-B70 host,
**after the missing inputs and runtime are restored**; publication did not run
it or create any unit.

```bash
export OMP_NUM_THREADS=2
export LORA= B70_H3_LORA= STEPS=51 SEED=42
export HEIGHT=544 WIDTH=960 FRAMES=124 SPLIT_INDEX=25
export B70_H3_DENOISER=pruned
export VAE_DECODE=two-proc VAE_AUTOCAST=off VAE_SERVE=1 AUDIO_OVERLAP=1
export B70_H3_LOADER=pread B70_H3_XFER=host B70_H3_DROP_PAGECACHE=0
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PROMPTS_FILE="$H3_REPLAY/experiments/minimax-h3-b70/notes/h3-soak8-prompts.txt"
export OUT_ROOT=/path/to/h3-output    # the lab used /mnt/fast-ai/bench-results/minimax-h3
# Restore independent historical reference receipts here before enabling a gate.
# BATCH_REF paths are relative to OUT_ROOT, not absolute paths.
for i in 0 1 2 3 4 5 6 7; do
  printf -v clip '%02d' "$i"
  export "BATCH_REF_${i}=duet-20260920T064019Z/clip-${clip}"
done
nice -n 19 /usr/bin/time -p bash \
  "$H3_REPLAY/experiments/minimax-h3-b70/scripts/smoke_h3.sh" duet
```

The September reference receipts named by `BATCH_REF_<i>` are not retained (the
first listed gap). Without them the comparison fails. That is a failed gate,
never permission to compare a run to itself. See
[About the batch command](#about-the-batch-command-historical-replay).

### 4. Wait until it is ready

There is no ready signal or health endpoint. The wrapper first checks the host
and prints `preflight: OK`. If a check fails it prints `PREFLIGHT FAIL: ...` and
`Refusing to start.`, changes nothing, and exits with code 4. The runner then
loads the text encoder and both halves of the denoiser; the run log shows
`worker 0 ready` and `worker 1 ready` once both cards hold their half.

### 5. Send a first request

There is no HTTP or chat endpoint, so there is no request to send. The prompts
come from `PROMPTS_FILE`: the eight fixed prompts in
[h3-soak8-prompts.txt](../../experiments/minimax-h3-b70/notes/h3-soak8-prompts.txt).
Each finished clip is written to its own directory:

```text
$OUT_ROOT/duet-<UTC time>/clip-00/clip.mp4        the video with sound
$OUT_ROOT/duet-<UTC time>/clip-00/receipt.json    settings, timings, four tensor/latent hashes, MP4 hash
$OUT_ROOT/duet-<UTC time>.log                     wrapper and runner output
$OUT_ROOT/duet-<UTC time>.watchdog.log            host-memory watchdog
```

The wrapper accepts any other prompt file with at least two prompts, but that
is a new batch: no timing or exactness claim transfers to it.

### 6. Check status

Replace `duet-<UTC time>` with your run's name:

```bash
tail -f "$OUT_ROOT/duet-<UTC time>.log"
ls "$OUT_ROOT/duet-<UTC time>"/clip-*/receipt.json
cat "$OUT_ROOT/duet-<UTC time>.watchdog.log"
```

Each denoiser worker also writes `$OUT_ROOT/duet-<UTC time>/worker-0.log` and
`worker-1.log`. Record the exit code, any new kernel fault lines and any H3
shared-memory leftovers in `/dev/shm`.

### 7. Stop

This is a finite batch. Normal completion stops sampling workers through their
`stop` mailbox and joins them, then closes decode and audio workers. **Let the
batch finish normally** and wait for the wrapper's exit. No model is restored
afterward. The retained session reports exit 0, no new fault lines and no H3
shared-memory leftovers.

For an interruption during sampling, the worker mailbox is
`/dev/shm/h3duet-<run-name>/stop`; writing `1` asks those workers to exit.
This does not establish safe cancellation of every later decode phase. A complete
mid-batch graceful-stop command is **not qualified**; do not advertise SIGTERM,
a forced group kill or the old service-restore script as one. Preserve fault
evidence and use the owning host's recovery procedure if normal completion fails.

## What you get

- **Measured speed:** one retained eight-clip batch took **3173 seconds**, or
  **396.6 seconds per clip** ([measured result](featured-observation.json),
  [session receipt](../../experiments/minimax-h3-b70/data/2026-10-04-soak8/session.log)).
  This is whole-batch time divided by eight, not the wait for the first clip or
  an observed delivery cadence.
- **Each clip:** 124 frames at 960×544, 24 fps, with 32 kHz stereo audio; 50
  transformer evaluations, seed 42 per prompt, no LoRA, FP32 video decode.
  Clips are independent: no seamless scene continuation and no real-time stream.
- **Exactness:** 32 MATCH / 0 DIFFERS against this denoiser's own reference,
  eight clip comparisons in one batch. The retained per-clip receipts are
  [clip-00-receipt.json](../../experiments/minimax-h3-b70/data/2026-10-04-soak8/clip-00-receipt.json)
  through `clip-07-receipt.json` in the same directory.
- **The model:** the owner-accepted Comfy-Org pruned BF16 denoiser and INT8
  ConvRot encoder. It is not lossless versus the official model. The 2.019×
  speedup is against an 800.8 s/clip ledger-recorded baseline whose raw receipts
  were not retained.
- **Memory:** 15 GiB host; lowest available memory 5643 MiB during the run. The
  full process-tree VRAM peak was not measured.
- **Not measured:** prompt reading (prefill) rate, scaling, several streams at
  once, and any projection.
- **Still missing** (from the package manifest):
  - September baseline/reference raw receipts
  - Complete editable diffusers source delta, clean build and runtime smoke
  - Independent fresh-process 50-NFE full-suite repeat
  - Portable model paths and qualified mid-batch graceful stop
  - Public release assets and native-video published certification
  - Clean-host installation and replay

## If it fails

Only failures this lane has documented are listed. On any GPU fault: stop,
keep the evidence, and do not retry in a loop.

- **`PREFLIGHT FAIL: ...` then `Refusing to start.` (exit 4).** Something still
  holds the cards or memory: a listener on 127.0.0.1:18124, a running container,
  less than 11264 MiB available memory, a missing GPU venv or watchdog, or an
  uncleared device coredump on a card. The wrapper stops and changes nothing.
  Free the host yourself. Clearing a coredump or rebooting is the host owner's
  decision. Never lower the thresholds to make a run fit.
  ([smoke_h3.sh](../../experiments/minimax-h3-b70/scripts/smoke_h3.sh))
- **`THE WATCHDOG KILLED THIS RUN -- host memory, not the GPU.`** Available host
  memory fell below the 2048 MiB floor, or memory pressure stayed high. Run one
  host-memory-heavy job at a time and read the watchdog log. Do not lower the
  floor. ([mem-watchdog.sh](../../experiments/minimax-h3-b70/scripts/mem-watchdog.sh))
- **`refusing GPU work outside smoke_h3.sh`.** The runner was started directly.
  Start it through the wrapper; the memory watchdog is mandatory.
- **`the diffusers VAE source at ... hashes ..., not the ...`.** The editable
  diffusers checkout differs from the one the two-card decode was written
  against. Restore diffusers at `7221eef4573574925b67a69e9fc1482bf093e569`. Whether
  the original checkout was clean was not recorded. The runner's suggested
  `--vae-decode single` is a different configuration, not the measured one.
- **`worker 0 died during load` (or worker 1).** Read
  `$OUT_ROOT/duet-<UTC time>/worker-<n>.log` and keep it.
- **Copy-engine (`bcs`) page faults, CAT errors or an engine reset at the first
  denoise step.** This happened on turin when hidden states first crossed from
  one card to the other. The wrapper's defaults `B70_H3_XFER=host` (stage
  cross-card copies through host memory) and
  `PYTORCH_ALLOC_CONF=expandable_segments:True` are preconditions for two-card
  runs; keep both. ([smoke_h3.sh](../../experiments/minimax-h3-b70/scripts/smoke_h3.sh) header)
- **The reference comparison fails or finds no references.** The September
  references are not retained. That is a failed gate, not a pass.

## What this package provides

| Item | Status |
| --- | --- |
| Cards / host | turin (`steve-TURIND8-2L2T`): two Intel Arc Pro B70, 32 GiB each, 15 GiB host RAM; split at block 25. Both the measured run and recipe target this two-card host. |
| Runtime | Native Python 3.12.3, PyTorch 2.14.0+xpu, diffusers 0.41.0.dev0 |
| Schedule | 51 sigma grid points / 50 transformer evaluations, seed 42 per prompt, no LoRA |
| Decode | FP32 video arithmetic; two persistent decode processes, audio overlap |
| Throughput | 396.625 s/clip, eight distinct prompts, one complete batch |
| Exactness | Session records 32 matching tensor/latent hashes; September originals absent |
| Fresh full-suite repeat | Not retained; short 8-NFE repeats do not qualify this 50-NFE result |
| Prompt reading | No separately qualified prefill rate; per-phase timers are not a token benchmark |
| Memory | 15 GiB host in the measured run; 5643 MiB lowest available in its watchdog log; full process-tree VRAM peak not measured |
| Scaling / context / projections | Not measured; no token graph or video projection |
| Public rebuild / clean-host replay | Incomplete / not tested |

The recipe uses resident weights within a finite batch; each prompt is encoded
independently. No prompt embedding reuse, response reuse, reduced steps, turbo
LoRA or FP16 decode supplies this result. There is no LLM KV cache. Independent
clips do not establish seamless scene continuation or a real-time stream.

## License and sources

This packet distributes **no model weights or fitted tensors**. It links to the
publisher and records metadata. The pinned
[MiniMax-H3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/LICENSE)
limits use and distribution to its applicable territory (excluding the EU, UK,
South Korea and US absent separate authorization). Redistribution has license,
notice and modification-marking conditions. Commercial use above US$20 million
annual revenue needs separate authorization. Users must review the full terms,
including its acceptable-use rules; a public download URL is not unrestricted
permission. The license identifies the Qwen3-VL encoder as Apache 2.0.

Comfy-Org supplied the fitted denoiser and INT8 ConvRot encoder used by the lane;
the lab did not originate that fit or quantization. The lab's adopted work is
the XPU loader, tensor remapping, bounded-memory loading, scheduling, persistent
decode and audio overlap. The [source card](https://huggingface.co/Comfy-Org/MiniMax-H3/blob/e5eb578a89295337b8ff433a035929ce0279e0b6/README.md)
identifies those converted inputs. No derived weights are rehosted here.

## Pinned inputs and verification

[model-manifest.json](model-manifest.json) records paths, byte sizes, SHA-256
and immutable upstream URLs. Weight hashes come from revision-pinned HF LFS metadata and are checked against existing turin copies in the [read-only hashing receipt](turin-file-verification.jsonl). Small metadata files are checked against HF Git-blob identities, with local SHA-256 also recorded. No weights were downloaded in this correction. [Provenance and gates](PROVENANCE-CORRECTION.md).

| Source | Revision / file hash |
| --- | --- |
| Official `MiniMaxAI/MiniMax-H3` | `42ed227ee7df40d41602854ae760620d6eb651fe`; official transformer shards, VAEs, configs, tokenizer and schedulers in the manifest |
| `Comfy-Org/MiniMax-H3` | `e5eb578a89295337b8ff433a035929ce0279e0b6` |
| Comfy-Org published pruned BF16 denoiser | `diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors`, 40,225,724,176 bytes; `a32572fb90b5508b201ec7c2eddcc184b13ddfd3c6f6d2cf06a0b46535d541b4` |
| INT8 encoder | `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors`, 27,141,342,152 bytes; `bc2ced0fbea64757fa9acddccfc0b3f4819d1dcf1da6c124d690d368be283923` |

For reproduction, download the pinned Comfy-Org and MiniMaxAI files listed in
[model-manifest.json](model-manifest.json), using each immutable URL and verifying
its size and SHA-256 before use. No fitting or newly produced denoiser is needed.
The existing lab copies are already on turin under `/mnt/fast-ai/llm-models/minimax-h3`
and `minimax-h3-comfy`; **nothing needs re-downloading for the lab**. The erroneous
recovery intake entries have been removed. External users obtain the pinned files
from the publishers under their license terms, in their own chosen model directory.

The lane's [download script](download-pruned-script.txt) explicitly downloaded the
Comfy-Org denoiser. The September [AdaLN note](../../experiments/minimax-h3-b70/notes/2026-09-17-adaln-table-exactness.md)
is an analysis of that published file, not a lab fit procedure. The
[fit directory](fit/README.md) and [recovery plan](RECOVERY-PLAN.md) are superseded
history. The owner's October 10 acceptance of this exact model also approves the
Comfy-Org source under the repository source rule; no extra approval is pending.

## Runtime and source reconstruction

[runtime-manifest.json](runtime-manifest.json) hashes every historical runner,
worker, watchdog, setup and CPU check at lab commit
`34ec68887431c9d64a5688aa35a5e220ddaa5e69`. It predates the later transfer
change and is the source reconstruction anchor. The run itself did not record
a source hash or prove that its editable diffusers checkout was clean. The
restore command is in [Quick start step 2](#2-get-the-runtime).

The [environment inventory](../../experiments/minimax-h3-b70/data/environment.txt)
pins the observed Python packages, including torch, transformers 5.17.0,
PyAV 18.1.0 and Intel 2026.1 runtime wheels. Restore diffusers from
`https://github.com/huggingface/diffusers` at
`7221eef4573574925b67a69e9fc1482bf093e569`. In a separate Python 3.12.3 venv,
install the three XPU torch packages from `https://download.pytorch.org/whl/xpu`,
then the other exact versions in that inventory and the pinned diffusers source.
The historical [setup script](../../experiments/minimax-h3-b70/scripts/setup-venv.sh)
is preserved, but is not a closed installer: some dependencies are unpinned,
it expects a pre-existing checkout, and its final check probes XPU.
No clean wheel build, package-availability test, complete upstream delta or
successful build log is retained. Do not run it as a CPU documentation check.

The runner still expects the historical model roots under `/mnt/fast-ai` and
the ConvRot file next to its source. Portability of those paths is unqualified.
The [rotation recovery script](../../experiments/minimax-h3-b70/scripts/recover-convrot-rotation.py)
accepts `--fp16`, `--int8` and `--out`; both required VAE sources are pinned in
the model manifest. Its recorded full-file rotation SHA-256 is
`ebb89aa1651e681f49461fe539bf2eb6fba0143c2733e5ad9cef438d48fb28d2`.
The file itself is absent from Git; this recovery was not rerun here.

## CPU preflight and quality gate

The evidence check at the top of the [Quick start](#quick-start) needs no weights
and no GPU access.
`--require-runnable` deliberately fails until the missing reconstruction gates
close. Passing the evidence audit is not permission to launch or a model test.
[evidence-manifest.json](evidence-manifest.json) binds the exact receipts,
source inventories and decisions. [promotion-attestation.json](promotion-attestation.json)
keeps unsupported full-suite/fresh-run/official-parity gates false.

On a reconstructed, authorized two-card host, run the historical wrapper's
`dry` mode with both venvs and the exact model/rotation files restored. It checks
the remap, reader, ConvRot, LoRA mapping and VAE tile loop; it still reads model
files, so it was not run in this publication task. The script files are all
listed and hashed in the runtime manifest.

## About the batch command (historical replay)

The exact optimized batch command is in [Quick start step 3](#3-start-the-server).
It is for a future authorized idle-host experiment **after the missing inputs
and runtime are restored**, not a complete portable installer. It must run
through the restored `smoke_h3.sh` watchdog. That wrapper uses a user systemd
scope; publication did not execute it or create any unit.

All four hashes (video/audio tensors and video/audio latents) must match per
prompt and seed. Compare the MP4 separately. Missing references are a failed
gate, never permission to compare a run to itself. For future experiments,
retain two fresh full-suite runs, all receipts, exact source/environment hashes,
wall timer endpoints and failure logs. Do not reuse short 8-NFE repeat receipts.
The old standalone baseline uses `repeat`, `LORA=`, `STEPS=51`,
`VAE_DECODE=single`, `VAE_AUTOCAST=off`; measuring it again creates new evidence,
not replacement historical receipts. No timing claim transfers automatically.

## Health and graceful stop

The historical wrapper checks free cards, no competing containers or the Qwen
endpoint, available host memory of at least 11264 MiB and uncleared device faults.
Its 2048 MiB available-memory watchdog is mandatory. These are recorded safety
thresholds, not a certified portable minimum. Never lower them to make a run fit.
The existing fault halt and host owner admission apply before any GPU probe.

This is a finite batch, with no HTTP health endpoint. How to stop it, and what
is not qualified, is in [Quick start step 7](#7-stop).

## Remaining work

Weight identity and the documented license/source position now pass, with
revision-pinned metadata and read-only verification of turin's existing files.
The publication manifest remains **draft**. Remaining gaps are September
baseline/reference raw receipts; a complete runtime source delta, clean build
and smoke test; an independent 50-NFE full-suite repeat; portable paths and a
qualified mid-batch stop; and public native-runtime release assets and clean-host
replay. The native-video-draft contract requires build/smoke/quality certification
to remain false until supported by evidence. The strict metric slot stays null.
See the [gate reassessment](publication-gates.json). The owner-selected measured
batch remains visible as a scoped video result.

[Detailed evidence audit](../../experiments/minimax-h3-b70/publication-draft/EVIDENCE.md)
· [results ledger](../../results/minimax-h3-b70/README.md)
· [publication manifest](publication-manifest.json).
