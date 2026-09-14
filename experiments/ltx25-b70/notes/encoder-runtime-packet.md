# Encoder candidate integration, inactive

The next GPU experiment compares control, crop-before-copy, small-state
residency, and both together. It preserves BF16, all model weights and sampler
steps, 256x256 final output, 25 frames at 24 fps, and the four exact output
oracles. No GPU result or new speed claim is attached to this packet.

Prepared snapshot: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-01`.
The [manifest](../data/encoder-runtime-prepared-01-manifest.json) inventories
1,205 files; [verification](../data/encoder-runtime-prepared-01-verification.json)
rehashes every file and checks that the four graph variants preserve all other
baseline inputs. Source size is 47,631,899 bytes; no weights or video are copied.
Six malformed archive cases were rejected before writing, and attempting to
reuse the existing packet path failed without changing any file hash.

The [integration tests](encoder-runtime-integration.md) pass four actual tiny
CLIP/Gemma4/LTX projection cases; the [additive guard](encoder-small-state-policy-followup.md)
passes 17 lifecycle tests. Integration also exposed the original candidate's
rejection of CLIP's ordinary FP32 compute-dtype object setting. The final guard
permits exactly that stock setting on CLIP, preserving all other patch guards.
Both defects and earlier receipts remain preserved. Neither CPU suite proves
native-weight GPU equivalence, placement, memory peaks or speed.

The source preparation helper is
[prepare-encoder-runtime.py](../scripts/prepare-encoder-runtime.py). It exports
the pinned upstream commit into a new ordinary source directory, applies the
reviewed patches there, and copies the frozen capture and routing helpers.
It creates no Git branch/worktree, imports no ComfyUI code, starts no process,
and modifies none of the running server's files. The packet manifest inventories
every source file, patch and graph. Its graphs differ from the selected baseline
only by the explicit encoder variant; unique request/output names are still
required before submission.

The original residency patch and twelve-test receipt remain historical
artifacts. Independent review found that a fully loaded shared clone could
change its option and bypass validation through `partially_load`'s early return.
The additive policy guard must accompany that patch. Otherwise a purported
control could retain the candidate's physical placement. Do not use the original
small-state patch alone, and do not stack the older generic accounting patch.

## Before any runtime use

This source packet is intentionally inactive and is not a launch recipe.
PID24848 remains the loaded service. A concrete startup and client integration
is still required before considering a maintenance transition:

- Verify the entire staged manifest, runtime version, model verification and
  exclusive GPU ownership. Reuse the established locks and fault-halt behavior.
- Bind the new source path, all changed helper hashes, new process start ticks,
  arguments and packet manifest to a new run identity. Use an exclusively created
  evidence directory; do not overwrite `speed-server` receipts.
- Inspect actual norm/scalar tensor placement after encoding, resident-byte
  accounting and unload ownership. Constructor flags alone do not demonstrate
  XPU residency or fewer transfers.
- Adapt the client identity gate to this explicit identity. Do not weaken or
  edit the original stability client's PID24848 identity requirement.
- Preserve the running server until a deliberate maintenance decision. No live
  injection, automatic restart, request retry, device reset, or power/swap/cache
  change is part of this packet.

## Bounded first endpoint comparison

Proposed order is control, crop, small_state, combined, then control again in
one process. One component set is retained at a time. An explicit variant
change unloads the previous set; construction/loading requests are recorded
separately from warm measurements. This may be expensive and is not itself a
warm speed claim.

Each arm has a maximum of five requests: one initialization request, then boat,
marble, bird, and another boat. Compare every available sample against its
protected original four-tensor oracle immediately, including initialization.
Stop on the first nonfinite value, mismatch, failed request, unexpected placement
or device fault. Do not proceed automatically to another arm after a failure.
The maximum is 25 requests, with no retry reserve. Final control helps expose
drift or a variant that left shared placement behind.

Capture original-style node timings, full client completion, memory snapshots
and per-arm mechanism evidence. Four warm requests per arm are a screening
sample, not a qualified performance headline. A passing candidate then needs
the varied 30-request gate for timing distribution and repeatability.

Retain protected references and failures. After exact comparison, keep compact
hashes/receipts and at most three new review previews across the campaign;
verified redundant tensor/media files can be pruned with the existing safe
retention mechanism. Lossless review export remains separately verified, and
lossy preview output never becomes the oracle.

Compiler integration is a separate candidate. The passing CPU block experiment
does not make the stock whole-model compile node suitable for this endpoint.
