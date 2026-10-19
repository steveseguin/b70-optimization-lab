# Packet152 — five exact follow-ups to the rank0 split

Prepared October 19, 2026, on steve-b70s. **Design only:** no packet153 copy,
build, model payload read, device job, service or queue change. Reference:
packet136 bundle8, **58.798108759182306 tok/s**, `iq3-p49-split32-v1`,
full BF16 state/KV, 24/24 layers, rank1 draft, fixed 80,128-row draft prefix.

**First prepared build briefs: [capture_snapshot](briefs/capture_snapshot.md)
and [merge_handoff_waits](briefs/merge_handoff_waits.md).** Every segment has
a concrete design and launch entry below. These are conditional engineering
plans, not five admitted speed claims.

## What the evidence actually says

The brief calls ≥0.4 ms segments “removable.” The actual
[packet150 analyzer](../packet150-rank0-split/v5/analyze.py), lines 86–117,
sets `removable=false` for every segment and returns an empty
`removable_segments`. Dispatch on `at_least_0_4_ms_in_every_control`:
**large boundary, removal unproved**. Do not wait for a nonempty removable list
or delete required work because the boundary is large.

The [CPU split proof](evidence/packet150-split-cpu.json) records four
seven-token byte/poison-restore passes, no timings, and suffix device equality
pending. It cannot rank segment costs.

| Evidence | What it supports |
| --- | --- |
| [Packet147](../packet147-lever-synthesis/PLAN.md), lines 45–73 | Current 1,188-interval replay, 932 hits/256 misses, 17.007350 ms reciprocal interval. Draft-only +2% needs 0.423078 ms/hit; correction-only needs 1.573805 ms/miss. No unbuilt two-card mechanism already supports +2%. |
| [Packet140](../packet140-body-lever/ANALYSIS.md), lines 20–60 | Body attribution failed its timing-overhead gate. Ordinary record token preparation is about 0.102 ms, not traced 1.5–1.9 ms. |
| [Packet135](../packet135-critical-path/ANALYSIS.md), lines 145–165 | Older suffix compute ≈0.294 ms; explicit draft publication wait ≈0.007–0.008 ms; pre-bank capture compute ≈0.522 ms; before-accept gap ≈0.598 ms includes suffix/verification. None is current removable host time. |
| Packet150 completed C/X/C/X/C | All three control medians must meet 0.4. Preserve per-prompt rows, range, boundary exclusions and duplicate costs. Replay measures added service, not safe removal. Snapshot scope measures host capture/submission, not asynchronous device copying. |

Capture setup and the broad merge/waits bucket are the **two most useful briefs
to prepare**, with low confidence about either clearing the bar. The older
suffix, token and explicit draft-wait proxies are smaller. This preparation
order does not assert two qualifying segments exist. The full draft command
is not `draft_wait`: its earlier `b.wait(1)` falls in `remote_reply_wait`
and can therefore appear under merge/waits.

## Completed packet150 verdict, received during this preparation

The [retained completed report](evidence/packet150-completed-summary.json) passes
its exactness gates, with control drift **0.135715%**. A read-only replay of
the original analyzer against all 60 request timing files reproduces
`rank0_split` exactly; [replay/pins](evidence/packet150-verdict-replay.json)
bind the input bytes. Request metadata comes from the bracket input objects,
the analyzer's supported fallback, because per-request native-result files
are absent. This replay launched no model.

| Segment | Median control ms/cycle | Control range ms | ≥0.4 in every control |
| --- | ---: | ---: | --- |
| token_prep | 0.122935 | 0.004938 | no |
| capture_snapshot | 0.743247 | 0.018248 | **yes** |
| suffix_head | 0.310820 | 0.000324 | no |
| merge_handoff_waits | 1.852065 | 0.020706 | **yes** |
| draft_wait | 0.006097 | 0.000113 | no |

**Dispatch: capture_snapshot first.** Its snapshot sub-scope is about
0.632–0.646 ms/cycle, with rollback about 0.110–0.113 and accept about 0.00027.
The duplicate snapshot service is 0.33455/0.33622 ms/cycle, not proof that all
of it is removable or a bound on every other host setup cost. Descriptor
removal remains conditional on ordinary-run exposure and exactness.

The merge/waits headline is mostly `remote_reply_wait` (1.538–1.563 ms/cycle).
Hidden readiness is about 0.181–0.182; head import/export about 0.025 each;
stream export about 0.065–0.068; host handover about 0.00057.
These are medians of subscopes, **not additive components of the segment
median**. Import/export alone cannot support a 0.4 ms transfer-chain saving.
The prepared merge brief is therefore **not currently admitted for a
transport-only build**. Command-correlated draft work uses the draft brief
only if its own hidden-branch/slack bound passes; deleting a reply wait is
never an implementation.

A separately coordinated **packet153-snapshot-host** CPU task was already
active when these results were read. Its
[read-only design](../packet153-snapshot-host/README.md) takes the same
host-descriptor direction, with an immutable table and device-calculated QSA
offsets. **Do not start a duplicate packet153-capture_snapshot build while
that task is active.** This packet's template design and brief remain the
reviewable contingency, not an instruction to interfere with that packet.
Its byte gates must also prove dynamic QSA pointer arithmetic and immutable
table preservation at reset. This note does not certify that implementation
or change its separate preregistration/resource limits.

## Verdict-to-build dispatch

Require complete device report, five views × twelve prompts, exact tokens,
proposals/acceptance, successful reset/drain, and source/selection identity.
Bind the report and raw inputs in packet153. Partial views do not select a
winner. Never modify/reseal packet150.

| Packet150 outcome | Launch entry |
| --- | --- |
| Only capture_snapshot large | [Full capture brief](briefs/capture_snapshot.md) → packet153-capture_snapshot. |
| Only merge_handoff_waits large | [Full transfer brief](briefs/merge_handoff_waits.md) → packet153-merge_handoff_waits; inspect subcause first. |
| Only token_prep large | [Token brief](briefs/token_prep.md) → packet153-token_prep. |
| Only suffix_head large | [Suffix brief](briefs/suffix_head.md) → packet153-suffix_head; first bound its removable tail. |
| Only draft_wait large | [Draft brief](briefs/draft_wait.md) → packet153-draft_wait. |
| Several large | Largest conservative **exposed saving bound**, not largest wait; ties: capture, merge/waits, draft, token, suffix. Start one build, retain other briefs. Never sum overlap twice. |
| Merge/waits mostly pending draft | Use [draft brief](briefs/draft_wait.md), retaining the observed classification and reason. |
| Large boundary, but candidate subwork too small or wholly dependent | Record failed mechanism bound; move to next qualifying design without a futile device screen. |
| All below 0.4 / unstable / missing scopes / failed or partial report / only remainder large | No device candidate admitted. Preserve exact missing attribution and residual source map for coordinator; do not rerun packet150 here. |

Launch means **start CPU implementation**, not enqueue GPU work. Every brief
inherits [BUILD-CONTRACT.md](BUILD-CONTRACT.md). The coordinator admits smoke
and one-load v5. Freeze CPU work from packet58ah WS through chain completion;
do not evade the reservation with another unit/compiler. Resume the same task.

## Bounds, sizes and arithmetic

Let H be the minimum of the three segment control medians, E the smaller
nonoverlapping cost of the specific removed work, O a proved independent
overlap window, and N the added exposed cost. Removal ceiling:
`max(0,E-N)`; overlap ceiling: `max(0,min(E,O)-N)`. Lower bound is zero;
regression remains possible. No design has measured positive savings yet.

Uniform exposed 0.4 ms off 17.007350 ms is about +2.41% by reciprocal arithmetic,
not a forecast or class-balanced measurement. Reaggregate actual intervals
with packet147's `max(D,R+C)+max(B,A+offset)+G` model. Faster rank0 helps
only where it advances suffix/target completion; draft savings mostly help hits.
Never count one saving in A and again in B.

Build planning sizes: S ≤500 changed lines/≤150 MB products; M ≤1,500/≤250 MB;
L ≤4,000/≤300 MB. Actual CPU/device memory admission is separate. Every segment
has zero as its defensible lower saving bound.

## Exact packet136 source map and designs

Ranges below name packet136 **input source** files; hashes and symlink status
are in [source-pins.json](evidence/source-pins.json). Future generated native
sources may shift lines: vendor the actual compile closure and record that
mapping. Preserve literal packet49 oracle-authority links.

### token_prep

**Source:** `rank.hpp:114–138`, `main.cpp:1110–1157`,
`strict_snapshot.hpp:282–345`. Each speculation saves history, writes token,
reads/dequantizes one embedding plus sixteen PLE rows, uploads lookup outputs,
and advances host history. Correction repeats preparation. No detokenization.

**Exact design — pure current-token ticket:** after request validation, capture
token, old history and immutable descriptors. One bounded CPU helper runs the
unchanged signed PLE hash and scalar decode into private buffers while rank0
runs `image.begin`. Use a private reader handle, not concurrent mutation of
Weights streams/caches. Join before canonical uploads; publish lookup IDs and
advance history at the original point. Correction uses the same synchronous
function. Keep one ticket; reuse storage, never prior prompt results or cached
lookup values. No canonical write before snapshot completes.

**Bound / size:** M; ≤min(H_token, snapshot host window) minus ticket/join cost,
on speculative halves only. Ordinary historical entire prep ≈0.102 ms: normally
below target. A new ≥0.4 observation needs an overhead check and a CPU-work
subcause. Private output is about 10,240 bytes plus bounded packed rows;
no vocabulary table.

**Risks/proofs:** signed remainder/EOS history, duplicate advancement, late
helper writes on miss/end/reset, thread safety and NaN call-site changes.
Compare IDs and every byte under GNU/Intel with all scale patterns/history
edges, delayed helper, forced cancellation, redo/terminal rollback and all six
bank states. Require unchanged canonical state, target tokens, draft proposals
and acceptance. A cancelled ticket must never publish.

**Exclude:** p137's block decoder/fixed target buffers/draft table is deferred
until another measured ≥1.5% gain; p58t's 29.3 GB lookup table was null.
This reorders unchanged scalar work; it does not reopen those mechanisms.
See [137 note](../../../../notes/2026-10-18-own-runtime-packet137.md).

### capture_snapshot

**Source:** `rank.hpp:123–125`; `strict_snapshot.hpp:141–160,171–204,
248–280,282–345`; `owner.cpp:305–321`;
`owner_api.hpp:83–92,184–188`. Each speculation drains/checks error/position,
saves host/shared state, derives extents, rebuilds captured copy descriptors and
flat table, uploads it, copies bytes and rotates banks. Bundle8 already removes
29,601,792 capture bytes via banks; the historical residual is 19,025,640 bytes.
Accept and rollback retain their semantics.

**Exact design — validated descriptor templates:** at quiescent setup, build
direction-specific metadata using the original CopyEngine checker. Separate
fixed extents from dynamic QSA rows. Each cycle validates source IDs/liveness,
roles, position and bounds, patches only dynamic pointers/lengths/tile endpoints,
uploads the table and runs unchanged SnapshotFlat. Eliminate repeated backend
copy capture, fixed vector/set construction and allocation, not any saved byte.
Key cache by owner generation, IDs/sizes, bank roles, context bucket, selection
and restore mode. Mismatch takes original checked path and rebuilds only while
drained. Keep distinct capture/full-restore/redo/deferred templates, all six bank
capture combinations, and previous-consumer completion before table reuse.
Unqualified variable-tail layouts retain original algorithm.

**Bound / size:** M; ≤E_descriptor_host minus cache validation/patch cost,
strictly inside H_capture. Target ≤2 MB additional host metadata, measure actual
geometry; no extra device snapshot or 4096×all-extents table. Old 0.522 ms
**device copy** is not host savings. A large boundary does not prove a large
descriptor cost.

**Risks/proofs:** QSA pooled offsets, backup packing, stale generations/roles,
deferred restore omissions, old-spare corruption, protected-prefix writes,
sticky error erasure. Compare complete legacy/new descriptors and arguments at
all 4096 positions, six bank pairs, context transitions and four restore modes.
Use bounded synthetic buffers for raw-byte poisoned capture/restore/accept/
cancel/end/reset tests under both compilers; protected corruption must remain
detectable. Preserve production memory and all oracle/state gates.

**Exclude:** p131b banks and two-submission batching already selected; p121
restore-only budget; p88's restore/draft overlap (already 0.569325 of 0.569390 ms);
p134 generic enqueue/graph rewrite (internal gaps ~0.085 ms). No BCS snapshot
arm: SnapshotFlat is compute, and a second queue does not establish legal
overlap. B70 has one CCS; only independently ordered copies could overlap it.

### suffix_head

**Source:** `p105_runtime.hpp:14–23,55–66`;
`p33_submit.cpp:65–112`, `p33_candidates.hpp:75–103`;
`round2_submit.cpp:99–128`; `p105_submit.cpp:14–31`;
`rank.hpp:340`. After rank0 speculation, run the private 46,080-row suffix,
two-stage BF16 argmax, pack Best, and publish to rank1.

**Exact design — final argmax/pack epilogue:** leave GEMV, every BF16 logit and
argmax stage0 untouched. Execute stage1's original ties and nonfinite fallback
verbatim; after establishing index/error, its designated lane writes the same
16-byte Best structure. Remove only the separate Pack submission. Preserve
all original index/error/scratch outputs and export ordering. No global barrier
or floating reduction rewrite; no early suffix service.

**Bound / size:** S/M; one Pack submission plus its exposed dispatch gap,
not H_suffix. Older entire suffix compute was ≈0.294 ms, so no supported
≥0.4 saving. If a large scope is drain/transport overhead, use the transfer
brief. Close a tiny upper bound quickly.

**Risks/proofs:** lower-ID ties across partitions, signed zero, sticky error
order, nonfinite diagnostic indices/NaNs and compiler call-site effects.
GNU/Intel fresh repeats compare logits, scratch/index/error and all Best bytes,
including nonfinite fallback and odd tails; native smoke checks full target/
draft state and proposals. Private suffix must not inherit target cancellation.

**Exclude:** p93 transpose (−2.8% lane A), p127 larger suffix (−1.95%), p130
interleave (−1.61%, exact complete bracket). No partition/placement change.

### merge_handoff_waits

**Source:** `p105_runtime.hpp:29–79`; `rank.hpp:175–182,255–258,340`;
`native_controller.hpp:31–41,70–84`; `mtp.hpp:281–287`;
`main.cpp:682–706,803–812`. Includes hidden readiness, 5,120-byte suffix
import, 16-byte result export, 20,480-byte stream export, host handover and
remote replies (also pending draft). Required work is not removable idle.

**Exact design — transfer chain with one terminal host wait:** keep
`head-split-compute`, same queue, same head arithmetic. Allocate separate
persistent pinned buffers for suffix hidden, control words and Best readback.
Validate identity; enqueue hidden copy and private error/active initialization
without intermediate host waits, then existing suffix commands, then Best
export. Wait for the final export and perform every drain/error/safety check
before reading host bytes or publishing. Apply the same pack→copy→terminal-wait
pattern to prefix export. Never pretend Engine's reusable synchronous upload
slab has asynchronous lifetime. Keep rank1 hidden-export/prefix ordering.

This removes host wait/return/next-submit bubbles and transient readback
allocation, not copies, head work or peer dependencies. Stream export can use
the same proven slab pattern later, only if separately budgeted; first arm
changes head transport only. No early target sends or second compute queue.

**Bound / size:** M; ≤E_transport_submit minus new slab/event costs, measured
inside import/export and prefix legs, never all H_merge. Historical ≈0.598 ms
before-accept gap includes ≈0.294 ms suffix compute and verification; it is
not a forecast. Record G≈0.02 ms alone cannot pass. Target <64 KiB extra pinned
bytes/rank, measured and admitted. Pending draft redirects to draft design;
target/prefix compute cannot be erased by this transport change.

**Risks/proofs:** premature read/publication, slab overwrite, stale sequence,
failure between copy and publish, incomplete drain/retirement. Fake event
scheduler delays each copy and refuses reuse/publication; inject sticky errors,
bad extents, dead/foreign allocations, peer abort and delayed terminal events.
Keep owner checks and 4-second submission safety. Compare hidden/streams,
prefix/suffix Best, merged index and all target/draft canonical state under both
compilers, then fresh smoke/v5. No device-compute-on-host-pointer shortcut:
`owner_api.hpp:153` and `owner.cpp:153–193` deliberately reject it.

**Exclude:** p92 report deferral (no gain), p130 early suffix, p126 guessed draft,
already-selected spin policy and p149 shared correction (~7.69 ms/miss added).

### draft_wait

**Source:** `native_controller.hpp:69–76,90–95`; `rank.hpp:275–295`;
`mtp.hpp:190–195,225–279`; `p105_runtime.hpp:68–78`.
The explicit publication scope is distinct from the earlier remote DRAFT reply.
Draft consumes confirmed token and prior target hidden; its cache advances once.

**Exact design — token-independent hidden branch in rank1 suffix slack:**
after prefix completion, while rank1 waits for suffix, compute only current
target-stream copy → original hidden normalization → original hidden projection.
Use new private staging outputs; never mutate canonical draft KV, position,
publication or async state. On confirmed-token DRAFT, adopt/copy the exact
intermediates and skip precisely that branch; embedding, merge_add and remaining
draft dependency order stay unchanged. Bind ticket to request epoch, position,
stream version. EOS/error/no-DRAFT/reset drains and discards staging, leaving
canonical draft bytes unchanged. No guessed token or extra target speculation.

One CCS permits this only after prefix finishes, not concurrent prefix/draft
compute. Initial design assumes compute in a measured idle window; any BCS
claim requires a separately proved independent copy channel.

**Bound / size:** M/L; ≤min(hidden-branch service, suffix-wait slack) minus
adoption/dispatch cost. Both current costs are unmeasured. Needs ≥0.423078 ms
net per exposed hit for packet147's +2% sensitivity. Full D≈1.6 ms and traced
1.62 ms suffix wait do not price this small branch. Count staging from exact
plan shapes, no duplicated weights/KV. Close immediately if complete branch
ceiling is below threshold.

**Risks/proofs:** wrong hidden version, target failure, canonical bytes changed
on EOS, NaN call-site changes, orphan ticket at teardown. Compare branch bytes
under GNU/Intel; force hit/miss, delayed suffix, every cancel/reset/error edge,
no-DRAFT terminal paths and full draft final state. Require identical proposals/
acceptance and unchanged verified target output.

**Exclude:** p126 full guessed-draft transaction; p79 relocation; p108 loads;
p122 HC fusion; p129 precision; p132 second candidate; p146 history lookup.
Only already-known hidden work moves, with no wrong-token draft or cache update.

## Prior-attempt audit

Before writing designs, searched every rg-visible repository DO-NOT-REPEAT.md
and Markdown note: **212 negative indexes, 3,580 notes, 3,792 regular files**.
[Audit](evidence/prior-audit.json) binds every path/hash/size/match count,
including other lanes; [own-runtime matches](evidence/prior-matches.txt)
retains 379 lines. [Closure snapshot](evidence/closed-at-entry.json) supersedes
stale “pending” in older indexes.

Relevant exclusions:
[131b](../packet131b-snapshot-banks/DO-NOT-REPEAT.md),
[88](../packet88-miss-path/DO-NOT-REPEAT.md),
[134](../packet134-submission-stalls/DO-NOT-REPEAT.md),
[92](../packet92-rank1-reply-first/DO-NOT-REPEAT.md),
[126](../packet126-early-draft/DO-NOT-REPEAT.md),
[127](../packet127-head-retune/DO-NOT-REPEAT.md),
[130](../packet130-suffix-interleave/DO-NOT-REPEAT.md),
[137 note](../../../../notes/2026-10-18-own-runtime-packet137.md),
[147 inventory](../packet147-lever-synthesis/PLAN.md).

No READY marker belongs to this design packet. Each future build needs fresh
proofs and its own READY written last. No copied readiness or measured gain.
