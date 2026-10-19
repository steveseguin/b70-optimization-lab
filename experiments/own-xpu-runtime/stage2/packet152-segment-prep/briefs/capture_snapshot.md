# Codex brief: packet153-capture_snapshot — reuse exact snapshot descriptors

Repo: /home/steve/llm-optimizations, main. Pull/rebase first; if unrelated dirty
files prevent it, fetch and reconcile HEAD with origin/main. Explicit paths;
`git commit --only -- <your paths>`; push after every commit.

**Current handoff:** packet150 selects this boundary, but a separately
coordinated packet153-snapshot-host task is already active. Do not duplicate
its build. This brief is the reviewable contingency; see PLAN.

## Why

Packet150 has completed and identifies capture_snapshot above 0.4 ms/cycle in
each control, or the coordinator selected it from several qualifying segments.
This is a host setup boundary, not measured removable GPU copy time. The goal
is to remove repeated descriptor preparation on packet136 bundle8 while keeping
every saved byte, bank role and rollback behavior exact.

Read [the capture design](../PLAN.md#capture_snapshot) and
[the full build contract](../BUILD-CONTRACT.md); both are binding parts of this
brief. The build contract supplies smoke/v5, environment, first-minute proof,
storage, gates and READY sequencing. No additional design request is needed.

## Do

1. Create `experiments/own-xpu-runtime/stage2/packet153-capture_snapshot/`
   from packet136 as specified in the contract. Vendor actual C++ and Python
   closure; preserve oracle symlinks. Do not copy packet150's probe image,
   model payloads, old builds or readiness. Bind completed split evidence,
   current source hashes, bundle8 selection and exact oracle.
   Add `snapshot_descriptors=original|templates`, candidate default off.

2. Edit new copies of `strict_snapshot.hpp`:
   - Constructor/source enumeration (packet136 lines 248–280): derive fixed
     source geometry, dynamic QSA-row records and maximum descriptor storage.
   - `copy` (171–204): capture the original checked extent descriptors once
     per legal geometry/generation; construct capture/full-restore/redo/
     deferred-only templates. Keep SnapshotFlat's original byte operation.
   - `begin` (282–314): use checked dynamic pointer/length/tile patches,
     preserve protected-prefix descriptors, host/shared snapshots and the
     existing rotation point. Do not move snapshot after token preparation.
   - `restore/before_command` (316–345): choose the matching direction/mode;
     preserve deferred completion, sticky failures, launch extents and parity.
   Introduce a small local header if needed; owner checks remain authoritative.

3. Cache key: owner address/generation, allocation IDs/size/live state, source
   ordering, six physical bank pairings, context bucket, selection and restore
   mode. Avoid raw pointer mutation hidden from the owner. A dynamic extent is
   revalidated through the same range predicate each use. Any key mismatch
   invalidates the template and takes the original checked fallback at a
   drained boundary. No prepared command retains an expired event dependency.
   Preserve per-call invariant checks; eliminate redundant static construction,
   not validation of changing state.

4. Keep the table upload plus flat-copy command and every snapshot byte.
   Start with one table; prior reader must complete before reuse. No BCS change,
   extra device snapshot, resident model table, per-position full table grid,
   second compute queue or shortened write set. Aim ≤2 MB new host metadata,
   derive exact maximum before allocations. Control/candidate union stays fixed
   through five views. Expose counters for template build/hit/fallback, dynamic
   descriptors, uploaded table bytes, copied bytes and generation.

5. Before extensive integration, run a bounded synthetic **mechanism test**:
   legacy and candidate derive descriptors at all positions 0…4095, all six
   bank pairings, full/redo/deferred modes, pooled-row boundaries and context
   transitions. Compare IDs, offsets, bytes, backup packing and tile endpoints.
   Alter one ID/generation/size/role and require invalidation/refusal before any
   copy. Save exact rows/digests, not a boolean alone. Time only descriptor
   work as a CPU diagnostic; do not subtract that time from the GPU record.

6. Both compilers, fresh repeats: poisoned mutable state, protected active/QSA
   prefixes, old spare, host history/lookup metadata, 64 KiB shared slot,
   cancelled prefixes, corrected half, EOS/end, abandoned redo, reset and sticky
   errors. Exercise candidate on the actual miniature native path. Preserve
   every original oracle/state/drain/limit gate; shard synthetic fixtures to
   ≤2 GB instead of dropping cases. Test new and old selectors through all
   eleven relevant startup argument paths and all six capture roles.
   All arithmetic primitives, full BF16 state and fixed draft remain unchanged.

7. Add low-overhead scopes `descriptor_build`, `descriptor_patch`,
   `snapshot_submit` and the original outer capture/accept/rollback scopes.
   No profiling queries inside capture. First-minute smoke proof must contain
   nonempty actual descriptor counters and scope rows from a completed request,
   parsed by the real analyzer. The negative test removes a required counter
   and requires failure. Exclude prefill/boundary-crossing records consistently.

8. Prepare packet-local `proposals/smoke-B.txt` and `proposals/v5-B.txt`.
   Candidate smoke 12×64, incident64/reset; then one-load original/templates/
   original/templates/original, 12×128 each, incident64 at boundaries.
   No live queue writes. Use `ops/launch_env.py`; run both actual proposals
   through `ops/rehearse_entry.py --report --json`, native loader/limits,
   real report dispatch and temporary lane planner with pin guard.
   Budget ≤3× comparable measured bytes (~250 MB/view: ≤750 MB/view,
   ≤3.75 GB for five), not inherited 1.1 GB/view. Record new build separately.

9. Commit/push source and passing CPU evidence, then write READY last and
   commit/push marker. CPU readiness must remain false on any unresolved gate.
   The coordinator alone launches smoke/v5. Give a bounded exact candidate,
   not a diagnostic duplicate-work arm.

## Saving bound and decision

Only descriptor host service is eligible: ≤min(H_capture,E_descriptor) minus
new checks/patching. The old 0.522 ms pre-bank device copy and the already-won
29,601,792-byte bank removal are excluded. If descriptor service cannot account
for a useful exposed cut, record that immediately and use PLAN's next segment.
No positive savings promised; M build, ≤250 MB target/300 MB maximum products.

The proposed v5 success gate is ≥2% in both candidate views versus fastest
control, ≤1% control drift, exact output/proposals/acceptance/state. A single
one-load result is only a screen; a speed verdict requires fresh confirmation
under the repository rules. Do not submit or promote from this brief.

## Rules

[BUILD-CONTRACT.md](../BUILD-CONTRACT.md) applies in full. CPU-only preparation,
nice19, taskset 8–15/24–31, python3 -B, stdin closed, ≤2 GB, no GPU/service/sudo/
settings/model reads. Freeze from packet58ah WS to chain end. All existing
packets, screen/*, ops/* and live queues frozen. No loss versus
`iq3-p49-split32-v1`. Decide, never ask. Commit message ends:

Co-Authored-By: Codex <noreply@openai.com>
