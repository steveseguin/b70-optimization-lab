# Packet12 encoder release: memory attribution and next boundary

Source/saved-metadata audit only, 2026-09-14. No native imports, allocations,
endpoint requests, process control or runtime edits. This supplements
[the earlier ownership proposal](host-embedding-restored-owner-transfer-proposal-01.md);
its historical fault status is not a current runtime assessment.

Evidence and exact source hashes are preserved in
[the audit receipt](../data/host-embedding-release-memory-audit-02.json).
Sources are frozen packet11 core (inherited by packet12), the qualified adapter
v2, resident v2 and standalone gather owner. No implementation is included.

## What actually released

Packet12 screen02 r06 refused before new encoder construction. The retired CLIP,
group, encoder patcher and encoder root all died; native registry cleanup removed
the old patcher. All registered encoder state was CPU and loaded accounting zero
before release. Shared diffusion/shard/VAEs/upscaler remained resident.

The two transition gates report MemAvailable 49,228,554,240 → 50,015,182,848 bytes:
only **0.733 GiB** gained, still below the unchanged **56.890 GiB** constructor
floor. This does not mean a 24 GiB CPU encoder remained allocated. Before restore,
25,726,483,968 registered bytes were on XPU and only 505,100,404 bytes on CPU;
the temporary CPU copy created by detach was then released. Net host recovery
cannot be calculated by subtracting the entire encoder size from its starting
host footprint.

Saved request snapshots at 19:51:37.267 and 19:51:43.347 UTC show process RSS
falling **20.651 GiB**, including **20.216 GiB file-backed RSS** and **0.434 GiB
anonymous RSS**. Virtual size fell 24.925 GiB. The permitted later smaps_rollup
read agrees with the final snapshot: only 7,475,104 KiB total RSS and 6,833,124 KiB
anonymous remain. This rules out a whole 24.43 GiB encoder retained as ordinary
resident anonymous CPU allocations. Smaller allocator retention remains possible.
File-backed RSS can include device mappings; these aggregate counters do not
identify individual safetensors or driver objects.

Global MemFree rose about 3.39 GiB while Cached fell about 2.65 GiB. Unmapping
pages already considered reclaimable does not yield an equally large increase in
MemAvailable. Meanwhile every saved DRM client's GTT/shared-GTT/resident-GTT and
resident-VRAM counters remained unchanged. These facts are consistent with
continuing native/driver allocation caching or references, but do not prove a
particular allocator or leak. Shared GTT is not additive unique host RAM. No
before/during/after per-allocation trace exists, so stop attribution here.

## Smallest replacement design worth proving

Prefer a private, single-use transfer capsule over a checkpoint `assign=True`
change. Native `CLIP(no_init=True)` (sd.py239) creates an empty metadata shell;
no parameter constructor or checkpoint load runs. Its ordinary clone method
lists the metadata fields required by the fixed graph. Keep the same restored
static patcher, model and tokenizer, copy only tokenizer-options metadata and
explicit native CLIP fields, then install a fresh ownership group. Do not call
`patcher.clone`: it creates parent-linked patchers and complicates lifetime.

A new transfer helper plus a resident successor can leave the frozen numerical
candidate/core untouched. Required order:

1. Preserve the existing actual non-CPU-state restore budget plus 8 GiB headroom.
   Detach and restore using the qualified adapter, including original embedding
   registration, CPU state, zero loaded/offload accounting and observer/callback
   removal. Retain a capsule containing only the restored native owners and
   whitelisted CLIP metadata; never capture the old wrapper or group wholesale.
2. Drop the old component tuple and local CLIP. Require weak death of **every
   bound old CLIP wrapper, old ownership group, old host owner, old host patcher,
   old host container, and retired delegate**. Original encoder patcher/model,
   tokenizer and restored embedding/table intentionally survive in the capsule;
   they must not be included in the death set. A retained clone/output tuple or
   group must halt before a replacement becomes visible. Require no other live
   known patcher clone, and clean dead host records through native cleanup only.
3. Consume a model-bound generation token once, create the native empty shell
   and new group, verify original registration/metadata and post-detach owner
   identities, then publish. Failures retain the capsule/shared components and
   latch refusal. No retry, competing lease, or resurrected retired group.
4. Keep the reused encoder's existing native LoadedModel bookkeeping: the same
   patcher may remain in the registry at zero loaded bytes and be reused by the
   ordinary loader. Require retired host records gone and no duplicate table
   accounting. Do not require the deliberately reused encoder ID to disappear.

This weak-death boundary avoids adding a broad tombstone API to surviving old
wrappers: none may survive publication. It cannot detect or revoke exported raw
model/tensor/patcher references. Support only the pinned serial fixed graph with
no external raw-state consumers; do not promise universal alias detection.
Parameter/storage IDs must be stable from **after restoration through transfer**,
not across CPU/XPU moves, which can legitimately replace storage.

The new path would omit constructor admission because it performs no new
constructor/checkpoint allocation, not because the existing floor was lowered.
It still requires the restore admission, post-restore headroom, ordinary unchanged
loader budgeting, and explicit receipt that no constructor was called. Current
packet12 has already discarded its encoder and latched failure; this proposal
cannot reconstruct it or bypass that failure in the running process.

`assign=True` alone is a weaker next choice: static CLIP already constructs CPU
parameter storage before load, native load propagates assign=False through
multiple component loaders, and direct assignment changes parameter/storage
ownership and checkpoint mmap lifetime. Avoiding constructor storage also needs
meta/lazy construction and nonpersistent-buffer initialization qualification.
It cannot reuse the already restored weights as narrowly as the capsule does.

## Proof and immediate work choice

Future guarded actual CPU proof must run control→host→control→host, count zero
constructor/checkpoint reads after the initial load, compare every parameter and
buffer's raw bytes/dtype/shape, preserve post-restore owner IDs, verify observer
and callback cleanup, check exact loader accounting, and reject retained wrappers,
clones/output tuples, replayed tokens, conflicting leases and failure recovery.
Follow with one bounded native all-four-output oracle campaign and memory receipts;
source feasibility is not CPU/native qualification.

A normal persistent application need not change placement mode at all. A later
single **fixed host-table initial construction** with ordinary cold admission,
then repeated new encodings and sampler diagnostics, avoids this transition
entirely. It can use existing qualified ownership paths and should not wait for
transfer engineering. Tradeoff: this does not complete a same-process bracketed
control/host/control speed comparison. Preserve the five exact packet11 host
clips as correctness evidence, and qualify any new fixed session on its own.
