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

## Input integrity failure before first generation

The September 12 RAID copy of the distilled transformer failed its fresh
staging hash. The copied file hashes to
`ad9eb77d12e611917f91cc71df924c6383a30cbf306b4d4afdf990912af0ebe9`;
authenticated publisher metadata at the pinned revision confirms the expected
`31eb3cad89b9e54e99dd3baf286f70825ac4f6c660a70d9184d895be76d7bff4`.
Size and first MiB match; a zero-page screen found no entirely zero 4 KiB pages.
No inference used these bytes. The original RAID is unchanged; the rejected
internal copy is preserved in the evidence root's `quarantine/` directory.

The original download helper reported a successful hash but did not explicitly
fsync files and trusts old verified statuses plus size on resume. That does not
establish the timing or cause of the present corruption. It is not a GPU result.

`scripts/download-verified.py` fetches a replacement at the same pinned revision,
checks network SHA-256, fsyncs the file, checks persisted bytes via O_DIRECT,
then renames and fsyncs the parent directory. It makes one attempt, with no
automatic retry or server restart. Other selected components are being checked
separately. The initial failed receipt and log remain preserved; the server
gate stays closed until the complete component set is verified.

The repair localized 79 changed bytes in one 8 MiB region starting at byte
310,378,496. Replacing that region in a separate copy restored the full
publisher SHA-256; an O_DIRECT reread also passed. The exact reversible delta
is preserved in `data/transformer-corruption-byte-delta.json` and the proof in
`data/localized-repair-promotion.json`. The original rejected file, old/new
region bytes and partial publisher download remain outside Git in the evidence
root. The now-redundant download was stopped once, after verification succeeded;
the ComfyUI server was not stopped or restarted.
