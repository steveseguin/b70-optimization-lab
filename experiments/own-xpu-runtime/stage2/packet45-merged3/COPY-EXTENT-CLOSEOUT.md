# Packet45 fix 5: full-size P39 fixture copies

<!-- campaign-closeout -->

The first P39 expert fixture uploads a 268,697,600-byte IQ2 weight bank in one call.
That exceeds CopyEngine's 134,217,728-byte transfer limit; both allocations are live and large enough.
The repair splits the transfer into waited 4 MiB chunks without changing the checker, weights or arithmetic.

The violating site is `OwnerBackend::copy` in `p39_fixture.cpp`, called by
`P39Fixture::init<IQ2_S,2560,expert_checks>` at the first `weights` upload.
Its original tuple is `(dst=p39-fixture-0, off=0, src=p39-fixture-1,
soff=0, n=268697600)`. Both allocations have 268,697,600 bytes and are live.
Only `n > limit_` is violated. Allocation handles are process-global counters;
the labels, extents and offsets identify the site independently of those counters.

## Incident attribution

Both card-pair incidents on boot `13858eef` retain `run0/p39-failure.json`.
Their event streams end at `fusion:small.ffn`, workload `small.ffn.q8`,
`p30.small.rows4`, repetition 199, event 910322. Thus all three small-GEMV
classes completed after the printed logits lines. P39 is next in
`fixture_driver.cpp`, and its first supported case is `expert-checks-iq2`.
There are no P39 timing events: its initial upload failed before submission.

The logits winner is not adopted inside the C++ timing loop. After **all**
fixtures finish, Python `k2_summary.summarize` selects implementations and
writes JSON; serialization performs no CopyEngine operation. P33's segmented
scratch does not change the final BF16 output allocation. Neither winner
adoption nor dispatch JSON emission caused this incident.

The original copy path fails on CPU for all three production expert banks:
268,697,600 bytes (IQ2), 360,448,000 bytes (IQ3), and 471,859,200 bytes (down).
All three fail before the backend receives even one copy. The five smaller
P39 classes pass. Retained negative evidence is in
[`evidence/copy-extent-fix/before.json`](evidence/copy-extent-fix/before.json).

## Repair and coverage

The P39 owner allocates a pinned staging slab of at most 4 MiB. Each chunk uses
the appropriate source/destination offset, waits for completion, then retires
the completed event before reusing the slab. This applies to upload, readback
and owned-to-owned copies. The first bank takes 65 copies (64 full slabs and
a 262,144-byte tail). The CopyEngine limit and all extent/lifetime guards stay
unchanged. No kernel, weight layout, numerical expression or ABI is changed.

`copy_extent_gate.cpp` instantiates the actual `P39Fixture` and `OwnerBackend`
for all eight merged P39 classes, with production rows, 512 experts where
applicable, and all eight weight/peer rotations. It runs initialization,
reset, snapshot and release through the real CopyEngine. Its sparse CPU backend
does no arithmetic and does not dereference device-labelled allocations; the
owner still checks every actual allocation ID, lifetime, offset and length.
Separate ordinary CPU copies compare bytes through upload, owned-to-owned and
readback at four slab-boundary sizes. Five rejection checks retain zero-length,
oversized, destination/source overrun and dead-allocation enforcement.

`copy_adoption_gate.py` enumerates every GEMV class and `qsa.attention` from the
K2 registry. Synthetic measurements force each selectable candidate to win;
same-kernel entries exercise incumbent retention. Every other candidate remains
in its class comparison, including both timing modes where registered. The
actual selector emits `dispatch-measured.json`; the native closed parser loads
that file and submits the selected implementation through the actual K2 owner.
The GEMV arm retains full production geometry and visits all eight rotated
banks. Attention covers every registered length at capacities 256, 4096 and
32768 with resident preparation and readback. GEMV geometry is independent of
capacity, so each GEMV choice is swept once. These are copy/binding checks;
synthetic timestamps and skipped arithmetic are never speed or quality evidence.
The complete CPU arithmetic and model suite remains a separate required gate.

## Why the rehearsals missed it

P39 used `timing && !fixture_validation::only` to select production geometry.
CPU K2 therefore used four rows and ten experts (down used 2560 rows and ten
experts), one bank, and no full-size timing setup. The normal P39 arithmetic
gate used the same reduced cases. Rehearsing the coordinator did not imply
exercising its production allocations. Separately, CPU zero timestamps cannot
select a measured winner, so previously no rehearsal forced every adoption.

The coordinator CPU gate now requires current, source-bound full-size copy and
selection-sweep evidence before starting its chains, records its hash, and the
final seal requires that exact binding. Eight mutation tests reject incomplete
coverage, stale sources/logs, oversized copies and missing guard tests. This
closes the size/selection gap without inventing device timing in a rehearsal.

## Reproduction and retained evidence

Use the priority/thread prefix in [CPU-REPRO.md](CPU-REPRO.md).
Historical full reproduction (not the current owner-authorized handoff):
`copy_extent_campaign.py all` runs the new gates, the six-arm fusion compiler
matrix, all four builds, the full CPU suite, all three nine-window rehearsals,
and sealing/admission. Device mode only compiles and links. Run
`copy_extent_summary.py` last to verify all seals and protected bytes.

The evidence directory retains the previous seals, negative reproduction,
compiler commands, raw gate logs, synthetic selection inputs/dispatches and
native receipts in a hash-verified archive. Large archives retain reproducible
test inputs and exact coverage evidence; they are intentional, not caches.
One initial standalone test build mixed generated and original header paths;
its failed compiler log is retained as `bootstrap-selection-compile.log.gz`.
The corrected test generates consistent CPU validation headers from source.
A subsequent compiler-matrix wrapper used a relative evidence directory where
its writer required an absolute path. Its first arithmetic arm passed before
receipt writing refused; the retained `bootstrap-relative-*.log.gz` files record
that harness error. The complete matrix was restarted with the corrected path.
Incident directories and device-produced results are read-only throughout.

Final counts and identities are recorded in
[`evidence/copy-extent-fix/qualification-summary.json`](evidence/copy-extent-fix/qualification-summary.json).
This closes the host fixture transfer defect, not the runtime optimization lane.
Fresh device chains remain necessary to qualify the new sealed executable identity.

## October 15 owner-directed handoff

Repair and audit committed before resealing. The existing seal is not current. All four build modes match the current compiled-source closure and all program binaries were linked after the last P39/GEMV source change; no rebuild is needed. Production decode does not call either changed fixture translation unit, although the common object linkage includes them in the executable. All five device executable hashes changed; ABI and kernel arithmetic are unchanged. Real-model CPU repetition was stopped by the owner; existing exactness evidence will be explicitly rebound. See [audit 6](COPY-AUDIT-6.md).

The owner superseded full reruns at 01:10 UTC. Follow [diagnostic handoff](DIAGNOSTIC-UNSEALED.md), then `taskset -c 4-15,20-31 nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B minimal_reseal.py` from this packet. This performs no model execution or rebuild.
