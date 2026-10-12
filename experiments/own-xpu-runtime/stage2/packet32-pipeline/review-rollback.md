# Independent rollback review

Status: final mechanical inventory and host rollback gate review passed. Device behavior remains untested.

This inventory was derived independently from packet29 `main.cpp`, the shared
`packet3/step/plan.hpp` builder, and packet29 `adapter.cpp`, `kernels.hpp`, and
`specialised.hpp`. It was not derived from packet32 ROLLBACK.md. No device or
discovery code was run. Sizes below use the admitted production geometry.

| Temporal storage | Writer and read dependence | Bytes / extent | Safe treatment without changing arithmetic |
| --- | --- | --- | --- |
| `blk.L.gdn.state` | GDN recurrence reads old state, writes every state element | 1,572,864 per GDN layer | Distinct committed input and candidate output banks; promote on confirmation |
| `blk.L.gdn.history` | Conv reads three old samples per channel and shifts history | 61,440 per GDN layer | Distinct old/new history pointers; promote on confirmation |
| `blk.1.ple.history` | Dilated PLE conv reads nine old samples per channel | 184,320 | Distinct old/new history pointers; promote on confirmation |
| `token_history` | `ple_hash` reads AND MUTATES its input pointer | 16 | Candidate history must be initialized with old bytes, or save/restore these 16 bytes |
| `position` | QSA/RoPE read it, commit increments it | 4 | Advance once per confirmed position; restore before redo if advanced speculatively |
| `error` | Explicit check-status/argmax outputs plus implicit sticky writes by guarded operators | 4 | Errors abort; wrong-guess rollback must never erase a real failure |
| `active` | Guard input on all launches; initialized to one | 4 | Not written by the half; remains immutable |
| `blk.L.qsa.keys`, `.values` | Append writes current position row; attention reads prior/current rows | 1,024 each per QSA layer and position | Append only; redo overwrites same position |
| `blk.L.qsa.raw` | Append writes current row; completed pool reads the earlier three rows | 256 per QSA layer and position | Append only; redo overwrites same position |
| `blk.L.qsa.pooled` | Writes current pool only on positions 3 modulo 4 | 256 per QSA layer at a pool boundary | Redo overwrites same pool using unchanged preceding raw rows |
| Host `history0`, `history1` | `prepare_token` advances both before launch dispatch | 16 | Snapshot before speculative preparation and restore before redo |

The QSA keys, values and pooled arrays carry temporal data despite incomplete
read dependencies in the whole-buffer launch metadata. Their kernel row ranges
must be inspected; a whole-buffer first-writer analysis alone is insufficient.

The other planned rank0 outputs are per-position values. In particular,
`streams` is fully overwritten by embedding broadcast before PLE/HC reads it;
there is no cross-position hyper-connection carry. QSA `.ids` is overwritten,
including sentinel padding, by each select. PLE IDs and lookup rows are fully
regenerated from the restored history. Token is uploaded before each attempt.
Weights, RoPE, metadata and the unit scalar are immutable. `next_token` belongs
to rank1; rank0 must not run an argmax or use an old `next_token` as a new result.

Outside the plan, the prepared FP32 input allocation has a source-ID/extent
cache. Invalidate both `fp32_sources` and `fp32_extents` before redo and after
lookups or any buffer-bank change. Prepared operator bindings, cached GEMV
matrices, routes and small-GEMV members contain allocation IDs, so swapping the
name-to-buffer map alone is insufficient. Rebind both inputs and outputs at the
attempt boundary. GDN and conv kernels already accept separate old/new state
pointers; no arithmetic or reduction change is needed for banking.

Scratch, controls, attention scores/probabilities, GEMV workspace, ordered
mixture output and route scratch are not temporal model state: their consumers
follow writers within the same half. Queue events, logical submission sequence,
profiling accumulators and read counters are execution bookkeeping and should
record speculative work rather than roll back. Device layer snapshots and
fixture publication require special care: do not expose speculative fixtures,
and preserve a confirmed position until its fixture receipt is written.

Rank1 needs no rollback if it only receives confirmed rank0 streams: its entire
input sequence and own temporal updates then equal the sequential target.
Prompt overlap is safe only with independently owned hand-over slots until the
receiving rank has copied the bytes into its own storage and acknowledged them.

The original two-layer mini puts only a GDN layer on rank0 and PLE/QSA on rank1.
It cannot cover rank0 PLE/hash or QSA rollback. A four-layer tiny schedule with
PLE and QSA on rank0, or direct real-path tests for those operations, is needed.
Tests must cross positions 3 modulo 4 and compare full temporal-state bytes
AFTER miss plus redo, not merely generated tokens. Append-only rows are dirty
between miss and redo, so an immediate pre-redo full-state equality claim would
be false without restoring those rows.

The host backend must stream weights per layer. Copying packet29 resident-mode
initialization unchanged into two host ranks would anonymously load roughly
54 GB and violate this packet's 10 GB total bound.

## Initial packet32 code review

Reviewed `rank.hpp` and the bank-related changes in `main.cpp`. The current
implementation uses separate output banks for GDN/conv, prebuilds both resident
operator binding maps, swaps those maps with the bank allocation names, and
clears FP32 source/extent validity on swaps. Matrix caches do not reference the
banked state/history, so they remain valid. Streamed operators rebind directly
on each launch. Rank0 snapshots 16 device token-history bytes before every half;
rollback restores those bytes, host history and the four-byte position counter.
Sticky error is checked before banking or undo and aborts rather than clears.
No blocking bank or temporal-state omission was identified in this review.

A four-layer pipeline mini now puts PLE and QSA on rank0. Requested an additional
full-state dump of inactive `state_spares` as well as active plan buffers so the
post-redo byte-equality gate covers all persistent physical banks. Canonical
names must be compared, since allocation IDs are process-specific.

Copies attributable to rollback in the current code are: 16 device-to-host
bytes before every rank0 half; on a miss, 16 host-to-device token-history bytes
and four host-to-device position bytes; plus 16 bytes of host scalar history
save/restore. Banked GDN and convolution histories have zero hot-path copy bytes.
QSA redo overwrites the same row/pool; no old cache rows are copied. Standard
embedding/PLE lookups, 20,480-byte production streams hand-over, and requested
fixture copies must be separately accounted for in the runtime receipt.

## Final independent plan and gate review

`launch-plan-rank0.json` contains 1,015 allocations and 890 launch sites, with
exactly layers 0–23. Rank1 contains exactly layers 24–47 and 885 launch sites.
The independent `audit_rollback.py` enumerates each allocation exactly once:
37 banked GDN/conv allocations (29,601,792 additional bytes), 24 append-only QSA
allocations, three temporal controls (`token_history`, `position`, `error`),
four externally initialized allocations, and 947 overwrite-only allocations.
All 947 have a reviewed full writer before their first plan read. The audit
fails on an unknown operation contract, an unclassified allocation or an
unclassified read-before-write. QSA partial rows and implicit error writes are
handled explicitly from the kernels, avoiding the launch-metadata blind spot.
See `rollback-inventory.json` for every name, byte extent, first writer and the
hashes of reviewed source files. Re-run the inventory after source edits.

The requested inactive-bank dumps are now present. `state_dump` writes every
active plan allocation plus all alternate banks and canonical host-history /
FP32-cache metadata. The four-layer mini includes all three banked categories:
GDN state, GDN conv history and PLE conv history; it also includes QSA keys,
values, raw index rows and pooled rows on rank0.

Reviewed `gates.py` and `mini-host.json`: 130 passing cases comprise the control,
ngram, prompt-overlap-off, every hit/miss pattern of lengths 1–6, and one
63-position random hit/miss/no-guess script. Each short variant matches 8 tokens,
32 layer fixtures, 1,188 full rank0 buffer files across 11 committed positions,
and all canonical host-state JSON records. The long script matches 64 tokens
and all 32 retained fixtures; it exercises 18 hits, 24 misses and 21 no-guesses.
As an independent spot check, all 1,188 buffer files in the first forced-miss
case were directly byte-compared with the control and matched. Both sets
contain three alternate banks in every dump and invalid FP32 cache metadata.

No unresolved rollback-completeness finding remains for the reviewed code and
CPU tests. This is not a device-concurrency, real-model speed, or coordinator
window qualification. The real-model oracle and remaining compiler/sanitizer
gates are separate receipts owned by the packet runner.
