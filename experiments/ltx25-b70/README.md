# LTX 2.5 native BF16 baseline on B70

Status: preparing first short clip; no measured generation or determinism claim yet.
User authorized bring-up and repeatability validation on September 13, 2026.

## Preregistered baseline

- Checkpoint: official distilled BF16 LTX 2.5, revision
  `5e6e71018ee1756ed329b697a7b4aedc934dfce9`. This is its own target;
  distillation is not claimed lossless relative to the distinct dev model.
- Native BF16 transformer and custom Gemma4 encoder; no additional quantization,
  LoRA, approximation, compilation or attention shortcut. Preserve upstream
  component precision and explicitly record any compute upcasting.
- Official two-stage text-to-video workflow: 256x256, 25 frames at 24 fps,
  8-step first stage and 3-step refinement; fixed seed 42 in both noise nodes.
- One XPU with synchronous CPU offload, including the text encoder. One
  continuously running local server, sequential requests, no restart chains.
- Save uncompressed generated tensors, lossless PNG frames, audio waveform,
  and a viewable video. Compare tensor hashes, finiteness and exact values
  across at least three actual recomputations with node-result caching disabled.
  Record first versus repeat timings separately. Lossless media encoding does
  not establish model quality or bitwise numerical determinism by itself.
- Fail closed on reported nondeterministic operations initially. If unsupported,
  preserve the failure and qualify any revised numerical identity explicitly.
- Faults halt new requests. No power, swap, page-cache, driver or reboot changes.
  Fresh-process repeatability is deferred under the no-restart constraint.

## Sources and storage

ComfyUI source: `19e1058f4c445ef74047e77a23f9ca7684c1e4b6`, upstream snapshot at
`/home/steve/src/ComfyUI-ltx25-baseline`. Exact environment will be frozen after
installation. Official workflow snapshot is in `data/upstream-t2v-workflow.json`;
source URL: https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_ltx2_5_t2v.json.

The selected five component files are copied sequentially from the read-only
RAID to `/mnt/fast-ai/llm-models/LTX-2.5-baseline`, with source and destination
SHA-256 matched to the original intake manifest. Model bytes stay outside Git.
Full evidence and media: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
The Qwen archive remains separately blocked on Corsair mount/verification;
its local weights and all prior research artifacts are preserved.

Before first execution, source review changed the encoder placement from CPU
to the default XPU path and removed `--lowvram`: this CPU lacks native BF16
matrix instructions. ComfyUI's normal memory mode retains partial-weight
offloading, with 6 GiB reserved. No CPU-encoder measurement was made.
