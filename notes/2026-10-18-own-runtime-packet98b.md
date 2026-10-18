# Packet98b: five-view proposal and readiness tooling

**CPU tooling is prepared, but the requested screens cannot run on the frozen
v5 engine.** All requested proposal files exist and retain the exact requested
selections. Their real queue plans refuse before device admission. They are
blocked proposals, not runnable jobs or successful queue plans. No compiler,
GPU, service, sudo, live queue, host setting, or existing packet source changed.

The supplied packet98 smoke result is supported by the saved
`stage2/screen/v5-bracket/evidence/p98-smoke-B` receipts. The new independent
reader rechecked both views, 13/13 exact, one lifetime and one teardown on CPU.
The owner's 274-second two-view observation is not a five-view measurement or
a new packet98b speed result. No performance result was generated here.

## Why a general v5 default is blocked

V5 is not a generic wrapper around arbitrary packet binaries. Its sealed native
engine descends from packet82b. Both `bracket.compatible` and the compiled
`Engine::bracket_select` permit changes only to route and recurrence. The Python
wrapper additionally requires its private, registered selection bytes and
lineage. Changing a Python allow-list cannot add native support or qualify a
different engine. Packet97 and the newer source packets have different binaries,
selection schemas, seals, and sometimes load-time layouts.

| Requested comparison | Frozen v5 refusal | Next applicable path |
| --- | --- | --- |
| f1e5 exact composite | `wide64` to `wide64+halfcache` changes the loaded layout | V4 with separate loads |
| f1e5 without packet91 | Still changes the half-cache layout | V4 with separate loads |
| f1e5 without packet90 | Route/recurrence change is supported in principle, but these exact packet97 selection bytes/binary are outside the sealed v5 lineage | V4; a new qualified v5 lineage would be needed |
| Packet92 reply-first | `host_retire` cannot switch in this native engine | V4; a new native switch needs qualification |
| Packet94 HC norm fusion | `hc_norm` cannot switch | V4; a new native switch needs qualification |
| Packet94 fusion plus weightcache | Also changes loaded HC weights | V4 only; included as a refusal, not a reopened qualified arm |
| Packet100 interleave | Workgroup order changes, not stored bytes, but `experts` cannot switch | V4 after the existing micro gate; new native support needed for v5 |
| Packet100 tile16 | Transposes packed code/scale bytes at load | V4 after the existing micro gate |
| Packet101 draft attention, including A mirror | Changes the draft selection; native v5 requires identical draft settings | V4; a new draft capture switch needs qualification |

Packet100 still requires its original real-route microbenchmark and >=15%
kernel-time reduction. These proposals do not waive that gate or recover its
missing raw route inputs. Records remain on lane A.

## Generator and proposals

`ops/packet97-orchestration/composite_jobs.py --wrapper v5 --decision PATH`
is the default CLI choice; add `--leave-one-out` for the separate removals.
Fresh automatic proposal preparation also requests v5. The legacy Python
`generate` API retains its v4 default for existing consumers, and explicit
`--wrapper v4` retains the old separate-load generator. Started v4 brackets
remain readable without replanning their occupied output directories.

`ops/packet97-orchestration/v5_jobs.py --sources` prepares the source intents.
Every intent contains five views in control/candidate/control/candidate/control
order, exact selection and seal hashes, wrapper pins, lane, and record lane A.
The runner checks the manifest hash and refuses unsupported choices before
calling any wrapper or opening an output directory. It never silently substitutes
packet91's registered candidate for a packet97 or source-packet selection.

Proposals under `experiments/own-xpu-runtime/ops/lane-queue/`:

- `proposed-p97-v5-f1e5-{A,B}.txt` — exact frozen decision `f1e5d7f47fc0fe54`.
- `proposed-p97-v5-leave-one-out-f1e5-{A,B}.txt` — both selected source removals.
- `proposed-p92-v5-{A,B}.txt` and `proposed-p94-v5-{A,B}.txt`.
- `proposed-p100-v5-{A,B}.txt` — separate interleave and tile16 intents.
- `proposed-p101-v5-{A,B}.txt` — attention-only comparison and A mirror.

All **18 intents** were planned separately through the real lane queue planner
in a temporary directory. All **18 refused**, as required by the frozen engine's
limits. The live queue was not changed. Small manifests, refusal reasons, queue
logs and receipts live in
[`v5-plans`](../experiments/own-xpu-runtime/ops/packet97-orchestration/v5-plans/).
The manifests and proposed job files are immutable; rerunning the generator
checks them rather than rewriting their decisions.

## Readiness and packet97d

The five-view evaluator uses the stricter comparison: **each candidate must
beat the maximum of all three controls**. The bracket ratio is the slower
candidate divided by that maximum; neither averaging candidates nor choosing
favorable adjacent controls can pass. Packet97d's +0.5% qualification threshold
still applies to that ratio. All five views must pass 13/13 exact, cold requests,
unchanged per-prompt acceptance, current boot, same lane, and chronological
nonoverlap. Acceptance is also compared across brackets and lanes.

Packet97d's identical-selection policy remains: every completed matching A
bracket must qualify; B needs a qualifying bracket and no quality failure or
candidate below both of its adjacent controls in any matching bracket. Old B non-wins remain
visible. Both lanes are required, and A remains the record lane. The chain
still needs >=1.5% on both lanes or two qualified selected sources. Every CPU
readiness check remains: full rehearsal, seal, inputs, storage, queue plan,
fresh chain, boot, and all pinned preparation bytes.

The v5 reader checks original oracle tokens, summary and boundary hashes,
incident64, resets, immutable loaded allocations, wrapper/native/config identity,
lane release and the single teardown. It labels the shared lifetime explicitly.
Matching selection bytes from a different native binary, seal, dispatch,
placement, or memory plan are **excluded**, not pooled with packet97 v4 evidence.
Consequently the current packet98 smoke is not packet97 composite evidence,
and this change does not manufacture a record-ready v5 result.

The old `composite_jobs.py` is retained byte-for-byte under `frozen98b/`.
Historical decision pin checks resolve only the explicit archived CPU tools;
all runtime, source, receipt and seal pins stay strict. The existing review15
historical test now checks those preserved bytes and reconstructs a decision
using its frozen provenance instead of today's growing helper file list.
No frozen decision was rewritten. Packet97d's in-flight reader changes were
composed with narrow edits; its new diagnostic failure reporting is retained.

## Validation and handoff

The complete orchestration directory passes **144 tests**. The frozen v5 wrapper
passes **119 tests and 21 subtests**. The new cases cover both candidate repeats,
the fastest nonadjacent control, all five exactness/acceptance/boot checks,
missing views, overlap, mixed v4/v5 history, lane-B veto, chain thresholds,
native layout refusal, selection substitution, and refusal before launch.
The real saved smoke was also re-read without starting a model.
As a positive control, the already registered packet91 pair passes the real v5
CPU plan on both lanes. It is not substituted for any requested selection.

Commands used `nice -n 19 taskset -c 8-15,24-31`, `python3 -B` or
`/home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest`, stdin `/dev/null`,
and no pytest cache. Logs are `python-tests-98b.log` and `wrapper-tests-98b.log`
in the packet97 helper. No compilation was needed for this CPU tooling.

The required first `git pull --rebase` refused pre-existing shared edits.
Fetch confirmed main equaled origin/main, so no shared files were stashed,
reset, or replaced. Existing packet97d work and unrelated generated evidence
were preserved. Only explicit packet98b paths are selected for its commit.
The shared generator, historical-pin resolver, v5 readers, readiness integration
and tests landed with packet97d in `b05a92756`, so that commit contains its
required helper dependencies. The packet98b follow-up carries the proposal
files, refusal receipts, test logs and this handoff.
The concurrent packet101 seal refresh at `3c200cec6` is included in the new,
unstarted packet101 proposal pins; no previous device evidence was rewritten.

The remaining work is a separately qualified native v5 family for the compatible
execution-only switches. Layout-changing comparisons continue to require v4.
The request to make all these screens runnable under v5 is **not complete** under
the frozen-source constraint; the refusal receipts specify exactly why.
