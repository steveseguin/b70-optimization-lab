# Inactive encoder placement and unload diagnostics

Status: **10 CPU tests passed; no GPU request or loaded-source change.**
These gates prepare the encoder comparison packet. They do not establish a
speed gain or actual four-card placement result.

The new [metadata-only helper](../scripts/encoder_diagnostics.py) registers
`LTXEncoderPlacementCheck`. Graph node `421` takes the encoder CLIP from `420`,
conditioning from CLIPTextEncode `364`, `run_name` and `encoder_variant`. Its
single CONDITIONING output replaces the corresponding conditioning input into
`365`. The node returns the exact same Python conditioning object, without
changing any tensor. It therefore gates sampling after encoding.

For `small_state` and `combined`, the production gate requires **289 RMSNorm
weights plus 48 layer-scalar buffers, 1,539,680 bytes total, all BF16 on XPU2**.
It also binds the actual component crop/small-state options, static patcher,
XPU2 load/CPU offload configuration, loaded policy/buffer markers and at least
the expected small-state bytes in loaded accounting. Control and crop variants
record actual placement without requiring small-state residency. All variants
must match their declared options.

Expectations can be injected only into the Python class constructor for tiny
CPU fixtures. They are not graph inputs. The production defaults and immutable
source packet remain the authority for a real comparison.

Each successful or failed placement check creates, exclusively:

```text
<LTX_ENCODER_RUN_DIR>/encoder-placement-<run_name>.json
```

Schema `ltx.encoder-placement.v1` includes `passed`, `failures`, `run_name`,
`encoder_variant`, `stage=post_encode`, model-verification/server-identity hashes,
expected state and actual inspection. Per-parameter and per-buffer rows include
registered name, owning-module identity, device, dtype, shape and bytes. Totals
by device/dtype accompany the patcher's reported loaded/model/offload-buffer
bytes, marked-module direct-state bytes, actual registered bytes on its load
device, and policy markers. Those fields permit accounting review without
pretending the baseline's known counter drift is an exact physical memory
measurement. No allocator peak or total device occupancy is claimed.

The helper reads metadata only: no `.cpu()`, `.to()`, tensor-content hashes,
reductions, copies, tensor allocations, XPU synchronization or active health
probes. Files are small JSON metadata; no video is saved. It validates an
existing passed model receipt, current server identity and dedicated absolute
`encoder-server-*` directory, and refuses an existing receipt. A root FAULT
latch blocks both entry and writing. A failed placement receipt is saved before
raising, so dependent sampling cannot proceed; the client must stop the
campaign on that failure.

## Explicit unload evidence

The additive [resident diagnostics patch](../patches/resident-node-encoder-diagnostics.patch)
applies after `resident-node-encoder-options.patch`. It imports/registers the
new node and surrounds the existing deliberate `unload_all_models()` with
before/after metadata inspections while the old CLIP still retains its owners.
It does not add an unload, restart or numerical operation.

The receipt is:

```text
<LTX_ENCODER_RUN_DIR>/encoder-unload-<old_generation:02d>-to-<new_generation:02d>.json
```

Schema `ltx.encoder-unload.v1` records both generation numbers and variants,
identity hashes, `before`, `after`, `passed` and `failures`. The gate requires
all registered parameters/buffers on CPU afterward, the same owner/name/shape/
dtype/byte metadata, and zero loaded/offload accounting with cleared marked
modules and small-state policy/buffer markers. A mismatch writes a failed
receipt and raises before dropping old references or constructing replacements.
Existing unload receipts are rejected before unloading. A client should bind
these receipts to actual component generations between comparison arms.

This proves offload of the inspected encoder owners, not that the GPU allocator
has returned every reserved page. Transformers, VAEs and other allocator state
are outside this encoder-specific receipt.

## CPU verification

[Ten tests](../scripts/test-encoder-diagnostics.py) use real tiny Gemma4
parameters/buffers and the prepared static ModelPatcher. They cover successful
metadata-only inspection and unchanged conditioning/tensor hashes; control
observation; production gate rejection on a CPU fixture; wrong dtype/options;
missing accounting; fault/name/collision rejection; actual detach with owner and
value preservation; missing-detach rejection; no graph expectation override;
and the additive hook through all four resident variants. The metadata test
makes tensor-copy/content/allocation APIs raise if called. The real resident
integration fixture uses mocked non-encoder loaders and CPU devices.

The [receipt](../data/encoder-diagnostics-cpu.json) binds helper and patch hashes;
[full output](../data/encoder-diagnostics-cpu.log) names the tests. A separate
[loaded-source check](../data/encoder-diagnostics-loaded-source-check.json)
confirms the original loaded core and resident helper still match the frozen
before receipt. Original patches, helpers and tests were not edited.
