# Inactive encoder variant integration

This prepares graph-selectable encoder variants for **one future persistent
process**. No loaded source, server, launcher or GPU workload was changed.
The source packet still needs startup/client integration and full-model GPU
qualification before use. It is not deployment-ready merely because graph
inputs are defined.

Apply the following patches in order to an isolated copy of the pinned ComfyUI
source plus the frozen resident extension at `scripts/resident_node.py`:

1. [Original small-state residency](../patches/encoder-small-state-residency.patch).
2. [Additive policy guard](../patches/encoder-small-state-policy-guard.patch).
3. [Default-off crop derivative](../patches/encoder-crop-before-cpu-opt-in.patch).
4. [CLIP constructor flag propagation](../patches/encoder-clip-options.patch).
5. [Resident node variant selection](../patches/resident-node-encoder-options.patch).

The original always-enabled crop patch and its results remain unchanged. Do
not stack that original crop patch or the separate accounting patch on this
set. The additive policy fix's earlier pre-CLIP version is historical evidence,
not another patch to apply.

| Graph `encoder_variant` | Crop before CPU copy | Small state residency |
| --- | --- | --- |
| `control` (default) | Off | Off |
| `crop` | On | Off |
| `small_state` | Off | On |
| `combined` | On | On |

Flags originate in the resident node's CLIP construction options.
`LTXAVTEModel` stores the crop flag when constructed; its disabled forward keeps
the original call without the crop keyword. `CLIP.__init__` installs the
small-state flag immediately after creating the patcher, before any possible
constructor-time device load. Small-state use rejects dynamic or unpatched
patchers. Shared CLIP clones retain the component and patcher options. The
additive model-owned policy guard prevents divergent clones from silently
changing the policy of loaded weights.

Only model components are retained. The resident identity includes placement
and encoder variant. Changing either explicitly unloads the previous model set,
clears its retained tuple and collects it before constructing the next set.
Prompt encodings, noises, sampled frames and completed outputs are recomputed.

The future process must provide `LTX_ENCODER_RUN_DIR`, an absolute pre-existing
non-symlink directory directly under the evidence root, named
`encoder-server-*`. The node validates this before model changes. It refuses an
existing next component receipt before unloading anything, and also opens each
receipt with exclusive creation. Existing `speed-server` receipts are protected.
The future launcher remains responsible for creating a unique run directory,
matching its server identity and handling faults; this patch adds no launcher,
restart or retry behavior.

## CPU evidence and discovered defect

[Four integration tests](../scripts/test-encoder-runtime-integration.py) passed:

- Actual patched CLIP construction on CPU observes both flags at the first
  possible load; shared clones preserve them.
- Real tiny BF16 Gemma4 blocks, the actual token-weight encoder and actual LTX
  projection produce exact equal outputs across all four variants at three
  valid-token lengths.
- Default control projection matches the original pinned LTX forward exactly.
- Resident variant transitions unload before replacement, retain one component
  set, reuse only matching configurations and create separate receipts. An
  occupied receipt fails before any component mutation. The protected old
  receipt directory is rejected.

Non-encoder model and VAE loaders are mocked. These tests prove CPU propagation,
ownership and narrow arithmetic behavior, not full-checkpoint equivalence,
actual CPU/XPU transfers, GPU residency or speed.

The actual constructor test exposed a defect missed by the original tiny
ModelPatcher-only tests: stock CLIP installs an FP32 compute-dtype object patch,
which the original small-state guard rejected. The additive policy patch now
accepts exactly `{'manual_cast_dtype': torch.float32}` on an `is_clip` patcher;
it does not change that baseline setting. Other object patches and hooks stay
rejected. [The follow-up note](encoder-small-state-policy-followup.md) preserves
this failure and the narrower earlier patch/receipt. The updated policy suite
passes **17/17 tests**, including the original full-resident clone bypass
reproduction and its guard in both directions.

The [integration receipt](../data/encoder-runtime-integration-cpu.json) records
all five final patch hashes and the loaded-file hash comparison.
[Before](../data/encoder-integration-loaded-source-before.json) and
[after](../data/encoder-integration-loaded-source-after.json) receipts confirm
that the four loaded core files and resident helper did not change.
[Full CPU test output](../data/encoder-runtime-integration-cpu.log) is retained.
No speed gain is claimed.
