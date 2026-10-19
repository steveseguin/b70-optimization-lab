# Codex brief: packet153-merge_handoff_waits — one completion wait for head transfers

Repo: /home/steve/llm-optimizations, main. Pull/rebase; dirty-file fallback is
fetch plus HEAD/origin reconciliation. Use explicit paths and
`git commit --only -- <your paths>`; push after each commit.

**Current verdict:** transport-only build is not admitted: completed packet150
head import/export is about 0.05 ms/cycle combined. Keep this as a prepared
contingency; see PLAN for the command-dependency selector.

## Why

Packet150's completed split has a large merge_handoff_waits boundary. It groups
transport with real peer dependencies, so a large number alone is insufficient.
Implement an exact host submission change only for exposed transport bubbles:
queue unchanged copies/head commands with persistent buffers, then wait at
the existing result-publication boundary. Packet136 bundle8 remains the base.

Read [the design](../PLAN.md#merge_handoff_waits) and the entire
[BUILD-CONTRACT.md](../BUILD-CONTRACT.md). Those define the proof, proposals,
first-minute analyzer data, resource budgets and READY sequence.

## Do

1. Bind the complete packet150 report, raw view records and analyzer hashes.
   Split H_merge into hidden-wait, hidden-import, best-export, stream-export,
   host-handover and remote-reply scopes, by command type/position. Correlate
   remote DRAFT replies with native rank trace; its time is not head transport.
   If pending draft dominates, execute [draft_wait.md](draft_wait.md) instead,
   recording why. If target/prefix compute dominates and transport ceiling is
   too small, close this arm promptly. Do not simply remove wait predicates.

2. Copy packet136 to
   `experiments/own-xpu-runtime/stage2/packet153-merge_handoff_waits/`.
   Vendor compile/import closure, retain oracle authority. Keep the original
   `head-split-compute`, 202240/46080 target rows, draft80128, banks and all
   bundle8 kernels. Add only `head_transfer=original|terminal_chain`.
   No packet150 duplicate/replay candidate or existing READY is inherited.

3. In copied `p105_runtime.hpp:10–27`, allocate persistent, separately owned
   pinned input, control and readback slabs. Derive sizes, padding/alignment,
   ownership and lifetime explicitly; target extra pinned <64 KiB/rank.
   Both selectors use the same union allocations, cleared at quiescent reset.
   Do not pass host pointers to device-only compute; keep hidden/Best on device.

4. In `p105_runtime.hpp:55–66`, after the original sequence/position/fixture
   checks and completed speculative half:
   - Fill hidden and control slabs, enqueue hidden import and the original
     private error=0/active=1 writes using CopyEngine without intervening waits.
   - Submit the unchanged suffix command sequence in the same ordered queue.
   - Enqueue Best→its own pinned readback slab immediately after Pack.
   - Wait for that terminal copy; then perform the existing required
     drain/profiling/sticky-error/abort checks, read Best and publish reply.
   Leave the entry hidden-ready predicate, speculative-half completion and
   all result safety checks intact. Record each event in the owner ledger.
   A single final event proves ordering only because the queue is unchanged
   and in-order; do not assume a cross-queue dependency was implied.

5. In `merge_target:68–78`, enqueue original prefix Pack and export before
   the one completion wait, then read and merge with suffix exactly as before.
   Preserve `p105::merge` value/tie/error semantics and device index upload.
   Leave rank1 `export_hidden/publish_hidden:35–53` ordering unchanged in this
   first arm. Do not also change stream handoff, reporting, draft scheduling,
   next-token readback or spin policy. This bounds the causal candidate.

6. Do not call synchronous `Engine::upload`/transfer helpers with an
   asynchronous expectation: their staging reuse is the reason for separate
   slabs. Write a private submit helper that validates through unchanged
   CopyEngine and returns an owned event; its caller owns the slab until
   completion. The helper must not retire unrelated events or mutate safety
   timing counters. Prepared suffix commands remain the same byte sequence.

7. CPU mock/event tests under both compilers and fresh repeats must delay each
   transfer, verify no premature host read/reply/reuse, reject bad extents,
   foreign/dead allocations, stale epoch/sequence/position and duplicate service,
   and propagate peer abort/sticky errors before publication. Include a negative
   baseline that incorrectly reuses the input slab, and prove the gate catches it.
   Compare every hidden byte, all logits/indices/errors/Best fields, target
   streams and complete canonical target/draft state across hits, misses, EOS,
   cancellation, end and request reset. Keep exact proposals and acceptance.
   Bound fixture memory at 2 GB; no real model payload in CPU preparation.

8. Native smoke receipts: record transport submit/completion timestamps and
   old/new host-wait count, request epoch/sequence, bytes, terminal event ID and
   original outer segment scopes. The first-minute real analyzer proof must
   show actual candidate terminal completion and nonempty input/output rows.
   Fail cooperatively for absent/wrong/malformed data; synthetic report tests
   do not count as this device proof. Preserve generation and completion
   checks in the ordinary timing path without full per-kernel tracing.

9. Create packet-local smoke-B and v5-B proposals. Candidate smoke 12×64 plus
   incident64/reset; v5 one load original/terminal_chain/original/terminal_chain/
   original, twelve 128-token requests and incident64 at each boundary.
   Use real `ops/launch_env.py`, both `ops/rehearse_entry.py --report --json`
   paths, loader/parser/limits, repaired report routing and current pin guard
   on temporary queues. No ops or live queue edit. Fit planned_writes ≤3×
   measured equivalent view (~250 MB → ≤750 MB/view, ≤3.75 GB/five);
   account extra smoke receipts and builds separately. READY last after the
   source commit is pushed; then commit/push marker, without a device launch.

## Bound and exclusions

Savings are ≤eligible transport host bubbles, less new event/slab overhead.
H_merge may mostly be causal waiting. Old ~0.598 ms before-accept gap includes
suffix compute and verification; G≈0.02 ms is too small alone. No measured
positive forecast. M build, ≤250 MB target /300 MB maximum products.

This is not p92 report deferral (no gain), p130 early suffix (−1.61%), p127
extra suffix rows (−1.95%), p126 guessed early draft or p149 costly shared
correction. Keep one CCS, no new BCS claim, no precision or oracle change.

Exploratory v5 gate: both candidates ≥2% above fastest control, controls within
1%, all exact tokens/proposals/state. One load is screening only; confirm
fresh-server performance before any verdict/promotion. No external submission.

## Rules

Full [build contract](../BUILD-CONTRACT.md) applies. CPU-only prep, nice19,
taskset 8–15/24–31, python3 -B, stdin /dev/null, ≤2 GB. No GPU/services/sudo/
settings/model reads. Freeze packet58ah WS→end; all existing packets, screen,
ops and queues read-only. Lossless `iq3-p49-split32-v1`. Decide, never ask.

Co-Authored-By: Codex <noreply@openai.com>
