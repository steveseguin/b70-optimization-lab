# Native LTX loader memory candidate, 2026-09-14

Status: **source-only candidate; inactive, no numerical or memory measurement**.
The active fault hold remains in force. The initial source audit used no Torch
import, checkpoint tensor load, GPU work, process inspection, runtime modification,
power change, swap change, or page-cache setting change. A subsequently authorized
tiny Torch CPU gate is described below; it did not complete.

Parent: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-02`,
ComfyUI commit `19e1058f4c445ef74047e77a23f9ca7684c1e4b6` with the packet's
existing encoder and dormant compiler patches. The candidate builder verifies
the parent manifest's source hashes before deriving two isolated patches.

The reported first-eager-load VmHWM of 90,513,152 KiB and later approximately
3.5 GB process RSS motivate reducing startup overlap. Source inspection alone
does not attribute that high-water mark to any one allocation, and neither the
high-water mark nor this candidate establishes a cause or fix for the later
kernel TLB/unmapping incident. File-backed resident mappings, anonymous weights,
allocator residency and driver allocations all affect the observed RSS.

## Where copies occur

- `source/comfy/utils.py:161`: with AIMDO inactive, safetensors uses `safe_open`
  and `get_tensor`. Without `--disable-mmap`, those tensor storages retain the
  normal file mapping. No candidate changes either mmap flag.
- `source/comfy/sd.py:2363`: diffusion construction creates the ordinary CPU
  parameter tree; line2368 loads with `assign=model_patcher.is_dynamic()`.
  This static runtime uses `assign=False`. `model_base.py:362` passes the state
  into `load_state_dict`, so the checkpoint storage and destination CPU weights
  can overlap. Linear reset initialization is already disabled in `ops.py:563`;
  the candidate does not add another model implementation or meta initialization.
- `source/scripts/resident_node.py:75`: the complete transformer remains on CPU
  while the encoder, both VAEs and upscaler are constructed. Sharding currently
  happens only after all those loads, and GPU placement happens later in sampling.
- `source/comfy/sd.py:1577` retains the encoder checkpoint dictionaries throughout
  model construction. `CLIP.load_sd` sets `can_assign_sd=False` on this static
  runtime; `comfy/sd1_clip.py:313` and `text_encoders/lt.py:215` subsequently use
  copy-based state loading for the Gemma encoder and connector components.
- VAE construction casts its destination model to the selected BF16 dtype before
  `load_state_dict(assign=False)` at `sd.py:1095`. These checkpoints are much
  smaller, and the resident loader already deletes each local `weights` dictionary
  afterward. No VAE loader change is proposed.

## Candidate and exactness boundary

The prepared artifacts are in [loader-memory-candidate-02](../data/loader-memory-candidate-02/manifest.json).

1. `ltx-native-bf16-assign.patch` adds a disabled-by-default model option to the
   diffusion loader. It applies only to static CPU construction of unquantized
   native BF16 LTXAV with standard operations and AIMDO inactive. It checks the
   complete state-key set, CPU devices, tensor type, shape and stride against the
   existing destination model. Matching tensors are assigned without a second
   CPU copy. Dtype mismatches are converted to the original destination dtype
   first, explicitly preserving the existing F32 checkpoint table to BF16 runtime
   conversion. Source and destination byte counts and every dtype conversion are
   included in the component receipt.
2. `ltx-transformer-preload.patch` exposes `loader_policy` with `baseline` as the
   default. `assign` tests only the first patch. `assign_preload` additionally
   shards and fully loads the transformer onto GPU0/1 before constructing the
   large text encoder, using ordinary `load_models_gpu` and existing placement
   checks. Encoder and VAE loaders, numerical operations, sampler and precision
   remain unchanged. Resident-component reuse includes the policy in its key.

Assignment alone removes the transformer source/destination overlap, but may
leave the later encoder load as the highest peak: approximately42 GB of CPU
transformer plus the encoder's source and destination tensors can coexist.
Early transformer placement removes that CPU transformer overlap. This is an
allocation-lifetime inference, **not a measured RAM-saving amount or guaranteed
VmHWM bound**. The encoder's own copy remains intentionally unchanged.

`assign=True` without destination-dtype preservation is not equivalent to the
baseline: it retains F32 tables as F32. Likewise, blindly enabling dynamic VRAM,
changing all encoder `can_assign_sd` flags, or constructing directly on GPU would
change more than this audited loader path. Those are not part of the candidate.

The candidate retains checkpoint storage until the corresponding parameter is
moved to GPU. This changes storage lifetime/aliasing and the host memory backing
the initial device copy; unchanged output math alone cannot certify its driver
stability. Existing no-LoRA/no-in-place-weight-mutation restrictions of the shard
experiment still apply. Full parameter/buffer byte equivalence after loading,
and all four generated-output comparisons, remain required.

## Validation and next action

Only standard-library source checks are authorized under this audit: parent
hash binding, AST parsing, patch application to temporary source copies, and
graph-delta checks. No candidate is installed into the prepared or live packet.

After the independent fault hold is resolved, first perform a small CPU test
comparing ordinary copy loading with dtype-preserving assignment, including
F32→BF16 halfway rounding values, shape/stride rejection and parameter lifetime.
Then prepare a new immutable runtime packet and compare `baseline`, `assign`,
and `assign_preload` with distinct request/capture/diagnostic names, strict
determinism and the native output gates. Measure process RSS/VmHWM, component
load phases, device residency and kernel faults. Do not restart/retry a failed
request or describe startup allocation reduction as a demonstrated fault fix.

The initial builder attempt stopped on a nonunique source-string anchor before
producing the resident patch. Its partial diffusion patch remains in
`data/loader-memory-candidate-01`; no numerical experiment or runtime change
occurred. Candidate02 corrects the anchor and supersedes that incomplete build.

## Follow-up CPU gate and builder pin

Root review requested an explicit parent-manifest pin and a tiny CPU test of the
candidate's extracted assignment AST using actual `torch.nn.Module` loading.
The future builder now pins parent manifest
`f1fc467a4620caabac9065e72fb7fd1628db437d1c977c86237bb0378ef8f952`.
`data/loader-memory-builder-pin-01` preserves the old builder, exact pin patch,
before/after hashes and the source-only check. Candidate02 was not regenerated.

The single test attempt used OMP/MKL thread counts1 and requested Torch CPU
threads1. It creates only tiny synthetic BF16 weights/F32 rounding-boundary tables,
imports no Comfy code, and requests no GPU operation, enumeration or compilation.
Its script is `scripts/test-loader-memory-cpu.py`. The AST extraction completed,
but no final receipt or log output appeared within120seconds. One Ctrl-C was sent
through tool session18086; the tool still reported the session running afterward,
so actual SIGINT delivery is not established. The tool did not expose an OS PID.

`data/loader-memory-cpu-01/operator-incomplete.json` preserves this incomplete
state. The last durable artifact does not prove the exact stalled line. No
pre/post XPU initialization, dtype-equivalence, CPU-forward or memory-saving
claim can be made without the final receipt. No retry was started, and neither
the candidate nor test source was changed while that attempt remained active.

Root subsequently identified the test as PID102144 by its stdout descriptor
pointing to `data/loader-memory-cpu-01.log`. Bounded reads of that known PID's
status show one thread, state R, RSS388236KiB, CPU affinity6 and shared pending
SIGINT (`ShdPnd=0000000000000002`). CPU6 was already implicated in the host
lockup. These observations establish the pending interrupt, not process exit,
the stalled Python instruction, or why its affinity is CPU6. No affinity change
or additional signal was made. The earlier operator receipt is preserved as
the agent's observation at that time; `root-observation.json` adds this evidence.
