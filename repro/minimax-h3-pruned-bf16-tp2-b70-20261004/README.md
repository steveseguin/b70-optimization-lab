# MiniMax-H3: video with audio on two B70 cards

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
a source hash or prove that its editable diffusers checkout was clean.

Restore without switching branches or modifying the active lane:

```bash
export OMP_NUM_THREADS=2
export PYTHONDONTWRITEBYTECODE=1
export H3_REPLAY="$PWD/h3-replay"
mkdir -p "$H3_REPLAY"
git archive 34ec68887431c9d64a5688aa35a5e220ddaa5e69 \
  experiments/minimax-h3-b70/scripts experiments/minimax-h3-b70/notes/h3-soak8-prompts.txt \
  experiments/minimax-h3-b70/data/environment.txt | tar -x -C "$H3_REPLAY"
```

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

From the repository root, no weights or GPU access:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B \
  repro/minimax-h3-pruned-bf16-tp2-b70-20261004/verify-evidence.py
```

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

## Exact optimized batch commands (historical replay)

These commands are for a future authorized idle-host experiment **after the
missing inputs and runtime are restored**, not a complete portable installer.
They must run through the restored `smoke_h3.sh` watchdog. That wrapper uses a
user systemd scope; publication did not execute it or create any unit.

```bash
export OMP_NUM_THREADS=2
export LORA= B70_H3_LORA= STEPS=51 SEED=42
export HEIGHT=544 WIDTH=960 FRAMES=124 SPLIT_INDEX=25
export B70_H3_DENOISER=pruned
export VAE_DECODE=two-proc VAE_AUTOCAST=off VAE_SERVE=1 AUDIO_OVERLAP=1
export B70_H3_LOADER=pread B70_H3_XFER=host B70_H3_DROP_PAGECACHE=0
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PROMPTS_FILE="$H3_REPLAY/experiments/minimax-h3-b70/notes/h3-soak8-prompts.txt"
export OUT_ROOT=/mnt/fast-ai/bench-results/minimax-h3
# Restore independent historical reference receipts here before enabling a gate.
# BATCH_REF paths are relative to OUT_ROOT, not absolute paths.
for i in 0 1 2 3 4 5 6 7; do
  printf -v clip '%02d' "$i"
  export "BATCH_REF_${i}=duet-20260920T064019Z/clip-${clip}"
done
nice -n 19 /usr/bin/time -p bash \
  "$H3_REPLAY/experiments/minimax-h3-b70/scripts/smoke_h3.sh" duet
```

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

This is a finite batch, with no HTTP health endpoint. Normal completion stops
sampling workers through their `stop` mailbox and joins them, then closes decode
and audio workers. **Let the batch finish normally** and wait for the wrapper's
exit. Record exit codes, new kernel fault lines and any H3 shared-memory leftovers.
No model is restored afterward. The retained session reports exit 0, no new
fault lines and no H3 shared-memory leftovers.

For an interruption during sampling, the worker mailbox is
`/dev/shm/h3duet-<run-name>/stop`; writing `1` asks those workers to exit.
This does not establish safe cancellation of every later decode phase. A complete
mid-batch graceful-stop command is **not qualified**; do not advertise SIGTERM,
a forced group kill or the old service-restore script as one. Preserve fault
evidence and use the owning host's recovery procedure if normal completion fails.

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
