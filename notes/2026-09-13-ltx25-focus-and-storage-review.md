# LTX 2.5 pivot and recent-download review

User requested parking Flash-Next, moving its weights to USB after closeout,
and focusing on LTX 2.5 following another host crash. This review launched no
model or GPU probe and changed no power, swap, page-cache, driver or reboot settings.

## Flash-Next closeout

[A340–A394 closeout](../results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md)
is already committed: 46.854250 tok/s approved realistic-suite record and
repeated 32K depth median 44.052 tok/s with matching outputs. No additional
benchmark is needed to park the campaign. Outstanding stability, clean replay,
concurrency and long-context certification remain deferred, with their existing
limits intact. The [teardown audit](2026-09-13-a394-teardown-audit.md) does not
establish the crash cause.

Archive source: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`,
185,563,783,127 bytes at revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
The historical backup is `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`.
Before removing the internal duplicate, verify the external tree with
`scripts/verify-qwen38-flash-next-fp8-tree.py`, preserve a complete inventory and
receipt, and record the restore path. Preserve all runtime, patch and result artifacts.

## Current storage and incident observations

Host `steve-b70s`, boot `39a36df18b22498eb74a28384839a024`, started September 13
at 20:17:54 EDT. Initial passive process inspection found no model server or
transfer. Internal filesystem has about 301 GiB free. Both USB volumes were
initially unmounted; empty mount directories were not evidence of missing models.

- Corsair UUID `4E0E66ED0E66CD91`: one read-only `ntfs3` mount attempt failed
  with `mount(2) ... No such file or directory`. Kernel logged
  `ntfs3(sda2): It is recommended to use chkdsk.` It remains unmounted.
  No repair, forced mount or retry was attempted. Existing Qwen backup could
  not be inspected; archive/reclaim is pending and the NVMe copy is intact.
- RAID UUID `1498256698254816`: mounted successfully read-only at
  `/mnt/raid-models`. This mount is for inventory, not write qualification.
- This review does not certify storage or GPU health or determine why the
  latest host interruption occurred.

## September 12 downloads

Source: `/mnt/raid-models/models/intake-20260912/download-manifest.json`.
The manifest reports complete and per-file verified statuses. This review
checked file existence and exact recorded sizes, not fresh weight hashes.
All 71 recorded files matched their expected sizes. Manifest SHA-256:
`457d943aa2e7e0f3b29f835687cda132000df568fa62208fe0a556331e35fcbc`.
LTX revision: `5e6e71018ee1756ed329b697a7b4aedc934dfce9`.

| Model | Bytes present excluding cache | Files |
| --- | ---: | ---: |
| Lightricks/LTX-2.5 | 123,751,115,945 | 13 |
| m-a-p/YuE2-3B | 7,295,775,046 | 28 |
| m-a-p/YuE2-Vae | 531,343,726 | 15 |
| openbmb/MiniCPM5-2B | 5,043,811,638 | 11 |
| openbmb/MiniCPM5-2B-DSpark | 647,565,544 | 4 |

MiniCPM's earlier BF16 pilot failed 4/6 strict format checks; its
[existing packet](../experiments/minicpm5-2b-b70/README.md) remains unpromoted.
YuE2 stays queued while LTX becomes the priority.

LTX root: `/mnt/raid-models/models/intake-20260912/Lightricks--LTX-2.5`.
Present are both dev and distilled BF16 transformers (42.018 GB each), the
LTX-specific Gemma4 12B encoder with projections (26.264 GB), audio VAE,
both video VAE variants, spatial/temporal upscalers, distilled LoRA and
duration head. No additional model download was initiated.

## Proposed first LTX milestone

Use an isolated ComfyUI/PyTorch XPU environment and the downloaded distilled
BF16 model for one short, low-resolution clip, after scoped checkpoint hash
verification and an appropriate bounded health gate. Keep one process loaded
for subsequent requests and halt requests on faults. First audit the selected
LTX workflow's attention, encoder and offload paths for XPU compatibility.
Memory placement must be explicit: the transformer alone exceeds one 32 GB
B70; four cards do not automatically form one addressable memory pool.
CPU offload or supported explicit device placement needs validation.

This is a proposed route, not a tested B70 recipe. The official
[LTX model card](https://huggingface.co/Lightricks/LTX-2.5/blob/main/README.md)
documents the split components and ComfyUI workflows; its Python examples
are CUDA-oriented. [ComfyUI's installation documentation](https://github.com/Comfy-Org/ComfyUI#intel-gpus-windows-and-linux)
documents native PyTorch XPU support, which does not independently certify
this specific LTX workflow. Start with fixed seed and a short clip; preserve
the workflow, exact runtime/model identities, elapsed time, memory and output
before attempting resolution, duration or multi-GPU tuning.
