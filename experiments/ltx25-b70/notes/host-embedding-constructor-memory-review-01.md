# CPU encoder construction and retirement memory review

Source snapshot: sealed packet11 (`34b7ff2f…`), after the failed
`host-embedding-screen-01`; no native imports, device queries, or runtime changes.
Exact inspected source hashes and historical `/proc` values are preserved in
`../data/host-embedding-constructor-memory-review-01.json`.

The replacement CLIP has two distinct memory phases. Retiring the host-table
encoder first moves its remaining registered accelerator state back to CPU:
at most **24,218,318,452 bytes (22.555067 GiB)** beyond the table already on CPU.
This is additional state storage, not a new full-table copy. Restoring the table
only changes module registration. The original CLIP/model/patchers/table must
then become unreachable before constructing a replacement. Weakref death is an
admission condition, not an assumption that `gc.collect()` or Comfy cleanup
necessarily succeeds. A surviving clone must refuse new allocation.

A new encoder's checkpoint tensor payload is **26,263,774,294 bytes**, obtained
by reading only the safetensors header. The actual original registered encoder
contains **26,231,584,372 bytes**, including 1,552 nonpersistent buffer bytes.
With static ModelPatcher and `aimdo_enabled=False`, manual-cast Linear/Embedding
construct ordinary CPU parameter storage; CLIP `load_sd` propagates
`assign=False`, and Torch's ordinary load branch uses `param.copy_(input_param)`.
The safe-open checkpoint tensors remain live while parameters are filled.
Prefix replacement and per-component state dictionaries share tensor values;
they do not themselves duplicate the whole checkpoint.

Therefore **52,495,358,666 bytes (48.890113 GiB)** is a source-derived,
conservative checkpoint-plus-constructed working-set budget for replacement
construction after old-owner release. It is not a measured hard peak or an exact
minimum physical-RAM requirement: mmap pages are reclaimable, allocator retention
and tokenizer copies add overhead, and GPU driver/system allocations are outside
registered model accounting. No swap capacity or expected page-cache reclamation
should be credited as guaranteed headroom. Any operational floor needs an
explicit additional margin and checks before both retirement and construction;
a single fixed 8 GiB preflight cannot protect either phase.

The historical boundary evidence makes the limitation concrete. Before failed
r11, MemAvailable was 38,281,400 KiB (36.507 GiB), the process had 7,850,012 KiB in
swap, and only 420 KiB swap remained free. Earlier, initialization had already
raised process VmHWM to 98,758,332 KiB. These are whole-application observations,
not an isolated CLIP-constructor peak. Shared GTT observations must not be summed
across render clients or treated as independent allocations.

The proposed successor should retain diffusion, both VAEs, and upscaler objects;
it should retire only CLIP ownership and prove release before loading the new
CPU encoder. That removes the old global-unload path's unrelated bulk CPU
transfers, but does not by itself qualify memory safety or accelerator recovery.
All existing fault latches remain in force.
