# Codex build brief: packet58am, one-card post-router demand staging

Repository `/home/steve/llm-optimizations`, main only. Prepare
`experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/` as a private,
symlink-aware copy of **packet58ah-onecard-record chain b**. The authoritative
design is [../PLAN.md](../PLAN.md); census release rules are
[../DECISION.md](../DECISION.md). This is one conditional build brief, not
permission to start a GPU job. Do not create the packet or build anything
until the release rule below passes.

## First decision, without asking

Read CURRENT, the parent result and full argv, packet58ai's complete report,
and all DNR/closure links in packet58al. Verify source/report hashes and
complete native evidence. Apply every row of DECISION.md:

- Valid bound ≥1.000 ms/token with useful sparse resident windows: prepare
  **`bcs-demand-retained32x2` only**.
- Valid bound <0.670: close without build and add the evidence-linked DNR row.
- Middle, invalid, failed or pending evidence: no transfer build. Write the
  exact blocker/next evidence in a new note; do not invent a positive verdict.

58ai originally measures **58ad**, not the 31.66271941826957 tok/s full
composition. A predecessor pass releases only conditional CPU preparation.
Its numbers remain labeled predecessor. Before v5, a new smoke must show
same-parent exact outputs and useful eligible overlap. Its 2..64 intervals
are screening, never the census's 2..100 primary bound.
Do not rewrite a frozen census or quietly drop HC-wide/E1/p109/retirement.

## Work boundary and copying

CPU preparation only; no GPU enumeration, model/GGUF read, services, sudo,
settings changes or live queue writes. Honor any active whole-host freeze.
Use `nice -n 19`, `taskset -c 8-15,24-31`, `python3 -B`, closed stdin, ≤2 GB
RAM and one compiler process at a time. Device jobs later must not inherit
CPU preparation resource caps. CPU preparation stops below **27 GB disk free**.
No network credential reads or printing secrets. No external source base.

Read the first-read lane/operations documents before runtime edits. Work on
main; pull first. If unrelated dirty files prevent pull, fetch and confirm
HEAD equals origin/main (resolve legitimate incoming commits without staging
or stashing others' files). Existing packets, `stage2/screen/*`, `ops/*` and
all live queue files remain frozen. New proposals live **inside packet58am**.
Commit with `git commit --only -- <your paths>` and push immediately after
each focused commit; final trailer `Co-Authored-By: Codex <noreply@openai.com>`.

Copy the full source closure from the hashes retained inside packet58ah, not
only its template `sources/main.cpp` or its copied binaries. Verify all
generated-source hashes before changing include paths. Vendor dependencies
into the new packet, preserve source attribution and a before/after manifest.
No imports or includes may resolve to mutable sibling code. Do not copy old
evidence/READY as the new identity. Retain parent evidence as explicit lineage.

## Implement exactly one candidate

Keep p60fusion, hc-wide, wide64+halfcache, other-fusion, ordered-foreground,
tile16, unchanged route/recurrence, target-only greedy, max cache
21,552,729,600, context4096 and full BF16 KV. Preserve the packet49 oracle
`iq3-p49-split32-v1` without repinning.

After each real router, identify actual published misses. Resident gate/up
can run while the host receives the small route descriptor. Enqueue demand
gate/up and down copies on a dedicated copy-only BCS list; insert completion
barriers only at their missing-slot consumers. Compute resident gate/up,
missing gate/up, unchanged activation, resident down, missing down, then
unchanged ordered combination. Store every intermediate/status in its
original slot; retain the parent's per-expert arithmetic. Charge the new
descriptor-producing kernel and readback. Use a separate original-slot stage
map; do not feed a 32-entry table to the expert-ID-indexed 512-entry resolver,
renumber routes, or infer residency from generation alone. Keep subgroup
collectives convergent under every partition mask. Do not invent
zero-copy-on-BCS or simultaneous expert compute on the single CCS.

Use fixed **2 ×32 ×1,971,200 =126,156,800 bytes** of packed staging,
within the existing 256 MiB transfer category after full simultaneous-lifetime
proof. Metadata maps ≤1 MiB device, new host metadata/event storage ≤2 MiB.
No resizing, cache shrink or reserve borrowing. Stage only misses with useful
resident neighbors, free entries and no planned/in-flight maintenance fill;
otherwise use unchanged zero-copy. Use deterministic route order, never a
prompt-specific gate. Every fallback and unused stage counts in performance.

Retain each stage through its actual route-snapshot disposition. Substitute
D2D for the same policy-selected later H2D fill, after revocation; keep the
source leased until real fill completion. Record staged-unused and repeated
demand bytes; no global once-per-expert traffic promise. Do not resolve
later-position compute from retained stages. Preserve one outstanding
maintenance transaction and its original publish/commit protocol.

Demand events have separate ownership from foreground and maintenance events.
Extend complete/drain/retire/reset/cancel/error/teardown proofs for every
queue. The parent `copy()` puts an immediate barrier on compute: using it
unchanged for early demand fails the mechanism. The default backend's
dependency shortcut assumes one in-order compute stream; explicitly prove
all new cross-queue edges, including prepared submissions. No raw unowned
pointer or fake maintenance ticket. One BCS is shared by all copy lists;
measure queueing and contention rather than assuming immediate DMA service.

## Mandatory CPU evidence before a device handoff

1. **GNU + Intel exact-byte proofs at real shapes**, at least two fresh
   executions per compiler. Use synthetic packed values, no model payload:
   gate/up IQ2_S 640×2560, wide64+halfcache; down IQ4_NL tile16 2560×640;
   ten slots, 512 IDs, all 48 layer bindings. Compare every gate/up,
   activation, down, status, sticky error and final-combination byte against
   original unpartitioned arithmetic. Exhaust masks 0..1023 for slot/address
   and lease bookkeeping; use all-resident, all-miss, every single-miss slot,
   alternating and pool-exhaustion masks for full real-shape arithmetic.
   Exercise original slot order, invalid routes, bounds, sentinel untouched slots, BF16/signed-zero,
   exceptional/subnormal values, all half-table encodings, delayed copy and
   D2D completion, pool exhaustion and reset. Batch fixtures to stay ≤2 GB;
   do not materialize a full 512-expert weight bank. Reuse accepted arithmetic
   proofs by hash where unchanged; new scheduling and pointers need new proof.
2. **CPU preparation-path probe through the device binary with the real
   argv.** Add an explicit CPU-only preparation probe that returns before
   GPU enumeration/context creation/model open. It must execute the exact
   device-build parser, option normalization, plan/binding preparation,
   capture and demand dependency construction used by smoke and v5, including
   every view/dispatch mode. Use synthetic sparse/mock ownership and real
   shape metadata for preparation. Invoke `build/device/own-rt-iq3` itself
   with each actual launch argv plus the probe switch; save argv and binary
   hash, prepared-site census and a trace proving no GPU/model access. Mock
   only backend/storage boundaries, not the parser or new prepare code.
   `--help`, host-only fullshape, intercepted subprocess or a miniature
   argument substitute is insufficient. If the device binary cannot safely
   traverse that path, fix the probe; no WARN-as-pass like 58ai's limitation.
3. Prove original-slot capture parity, both parity banks, request/view reset,
   empty-cache policy, all live allocation extents, buffer/route generations,
   skipped route snapshots, no stale stage after reset, one actual owner per
   event and bounded event retirement. Fullshape mock must drive every one
   of 48 router hooks through the real prepared path, not just a new helper.
4. **Analyzer rehearsal on real device parent evidence.** Consume pinned
   58ah chain-b WS128 `result.json`, `timings.jsonl`, `prefill-timings.jsonl`
   and receipt/argv, plus completed 58ai event/census evidence when available.
   Include the real first request `incident-retrospective`, first prefill
   row and generated token 1; do not crop slow cold rows. Packet58al's audit
   locates them and records hashes, but is not a substitute for this analyzer
   replay. The first parent prefill row is about **23,457.6 ms**, and the
   first request's prefill total about **28,124.118 ms**. They are valid data,
   not timeout failures. A matching data adapter must not fabricate missing
   demand-event fields in the older source schema. Test the new demand schema
   separately with labeled synthetic evidence, then require actual new device
   streams in smoke. Missing, truncated, duplicate, wrong-identity and edited
   token/byte/event fixtures must fail. No measurement is relabeled as 58am.
5. **In-run data proofs check stream presence/format and exactness only.**
   Do not stop a valid run because milliseconds exceed a guess or two timing
   fields differ numerically. Enforce ordinary memory, storage, device-fault
   and ownership safety separately. After graceful completion, check numeric
   consistency with preregistered **relative tolerances**: for the same
   semantic duration use `abs(a-b) <= max(0.001 ms, 0.02*max(abs(a),abs(b)))`;
   use exact IDs/counts/token hashes and integer event ordering where required.
   Round-trip printed timings have limited precision. Do not equate different
   clocks/scopes or sum overlapping events. Broader tolerance needs a recorded
   rationale before the run, not a post-result loosening. Preserve numerical
   failures as offline invalid evidence; never cycle a server to hide them.
6. **No wall-clock limits in data proofs.** Per-operation cooperative wait
   limits are at least **4× the largest measured corresponding cold phase**,
   with **300 seconds minimum** for this first prepared candidate. Use the
   maximum cold evidence across 58ah and any completed 58ai/58aj relevant
   phase. If only an enclosing cold phase is measured, conservatively use it
   as the bound; do not pretend it is a measured single operation. Record
   source rows, conversion and chosen limits in `wait-budget.json` and the
   exact argv. Unknown extra phase needs explicit diagnosis/evidence, not a
   small default timeout. First-data proof has no elapsed-time verdict.
   Runtime watchdogs remain separate, cooperative and based on measured full
   stages; never hard-kill a busy GPU at a data-check deadline.

## Admission and artifact budget

Retain packet58u simultaneous host accounting via the private parent policy,
full file allowance, 4 GiB shadow stop and **8 GiB reserve**. Conservatively
charge the planned additions as PLAN specifies: host bound 90,529,619,968,
required MemAvailable **99,119,554,560 bytes**, subject to a measured allocation
census and any further explicitly charged bytes. Device categories remain
within 29,963,128,848 plus 536,870,912 driver allowance and 1,500,000,000 reserve.
No spare top-level device capacity is assumed. Pin the max-lifetime allocation
plan and check admission before/after drains and after native load. Failure
means no device readiness, not a smaller hidden reserve.

Storage admission: **free bytes ≥25,000,000,000 + planned outstanding writes**.
Measure sizes from actual 58ah smoke/K1/WS128 output and available 58ai logs;
measure baseline bytes/row on retained real rows. For fields absent from
the parent (new demand events/leases), measure serialized bytes using labeled
synthetic new-schema records; never call those device evidence. Replace that
incremental storage estimate with actual smoke volume before v5 admission.
Scale only artifact storage counts to the preregistered request/position/event
counts (never extrapolate performance). Document each base and multiplier.
The **planned-write reservation must be ≤3× the matched measured-volume
estimate**. Also prove it covers projected actual writes including logs,
temporary files and analyzer output. Do not copy the inherited 1 GiB census
or 32 MiB/K1 placeholders blindly; they exceed actual K1 size by >3×.
No missing measurement represented as zero or an arbitrary large allowance.
Compact/stream output if necessary, retaining required evidence; no deleting
old evidence to get admission. Account build scratch separately while preparing;
stop CPU preparation below **27,000,000,000** free bytes.

## Fresh smoke, then one-load v5; READY last

Prepare in-packet proposals with fresh names, e.g.
`packet58am-demand-a-smoke-A` → `evidence/card0-demand-a/smoke`, then
`packet58am-demand-a-v5-A` → `evidence/card0-demand-a/v5`. Refuse any existing
job/output path; a subsequent revision gets a new suffix and keeps failures.
No live enqueue, systemd start or GPU call in this build task. The coordinator
alone admits the later whole-host card0 hold with both other lanes drained.

Smoke: K1a/K1b proofs and one model load, all 12 exact 64-token requests, with
early first-completed-request stream checks and retained cold rows. Use
distinct diagnostic views in that load for the full-composition parent
census and candidate; preregister their order. Do not label their timing a
speed result. Confirm eligible staged demand, actual copy-only engine,
cross-queue completion, byte/oracle identity and clean teardown. The matched
parent screening must show actual eligible BCS overlap before the v5 proposal
becomes admissible. It does not revalidate the ≥1 ms primary ceiling from
64 outputs. Check dormant-hook overhead against real parent evidence and
report the identity/drift limitations; no tiny synthetic-only smoke waiver.

V5 is **one load, A0/B0/A1/B1/A2**, all 12 prompts ×128 tokens/view.
A is full-composition 58ah with demand disabled, B is the single candidate.
**A0 is warm-up**, retained and exact but excluded from speed/drift.
All controls allocate the same maximum memory; no weight reload or uploads
on view switch. Reset request/KV state and start each view's expert cache
empty; cached_tokens=0. Freeze other CPU work for the quiet bracket. Preserve
the parent 90-second stage gaps, fault polling, admission and graceful drain.

After completion, both B views must beat **both** A1/A2 controls by ≥0.5%,
warm control drift ≤3%, and strict `min(B0,B1)/max(A1,A2)-1` ≥2% for a
performance candidate. Also report per-class/pooled intervals, TTFT, cold
first request, prefill and lightweight byte/lease counters, including losing
cases. **Disable event profiling and detailed per-layer census in both v5
A and B**; actual overlap diagnostics come from the separately labeled smoke.
No candidate passes on one lucky view. An exact slow/no-overlap arm
closes with DNR and evidence; a fault is diagnosed without automatic retries.
This repeated bracket is diagnostic; a record still requires the inherited
fresh chain(s), determinism, quality, attestation and honest 128/512 scope.
No publishing or external submission is part of this brief.

Finish all source/byte/preparation/analyzer/failure/admission/entry checks,
save exact command arrays and hashes, and verify no frozen file changed.
Write build receipt, evidence inventory, in-packet proposals and note. Commit
and push those first. **Write READY last**, binding the committed source,
binary hashes, real evidence replay, all proof results, wait/storage budgets
and proposal hashes. Distinguish `cpu_prepared`, conditional smoke readiness,
`v5_ready` (false until the same-parent smoke passes), and device-executed
status. Missing gates mean READY false; no stale copied marker. Commit and
push the final marker immediately. Report what passed and the remaining
coordinator gate in plain words; do not ask whether to continue.
