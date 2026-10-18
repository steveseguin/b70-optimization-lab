# Packet101: re-test the remaining draft attention choice

Packet97 already enables all fourteen settings from packet69's `draft-hc`
view. Its draft HC kernels are byte-identical to packet69's. There is no new
HC candidate to measure. The split32 attention path is compiled into packet97,
but its draft defaults to score/softmax attention. Packet101 adds bundle views
for that existing switch, using copies of packet97's sources and its two
unchanged, hash-checked binaries. No runtime source or target arithmetic changed.

| Named view | Draft attention | Draft HC | Meaning |
| --- | --- | --- | --- |
| `control` | Existing implementation 5 | Existing packet59 HC | Packet97 baseline |
| `draft_attention` | Split32, implementation 12 | Same | Only distinct candidate |
| `draft_hc` | Existing implementation 5 | Same | Byte-identical control alias |
| `combined` | Split32, implementation 12 | Same | Byte-identical attention alias |

The proposed bracket is **control / draft_attention / control**, first on B,
with an A mirror. Do not spend GPU windows on the aliases. A single completed
lane qualifies this source for composition only when all thirteen exact checks
pass, per-prompt hits and guesses stay identical, and the candidate is faster
than **both** controls. There is no 1.5% source threshold. This packet makes no
speed claim and does not authorize a record. Records run on **lane A**, after
the applicable composed-runtime and full-chain gates.

Packet69's +0.82% `combined` row also enabled **target and draft wide64 heads**;
it was not an isolated attention-plus-HC measurement. Those head changes are
not imported. Packet97's unchanged expanded draft head uses the correct
**3,380-byte storage stride**, including when a packed target head needs a
separate 91,392-row draft prefix. Useful code/scale reads of 3,200 bytes are not
the storage stride. The current draft-HC timing cannot be priced from packet69's
old baseline. [Source and selection audit](evidence/source-audit.json),
[source diff](evidence/packet69-to-packet97.patch).

CPU evidence is complete:

- GNU and Intel each pass two fresh linked split32 runs, **88 cases per run**,
  against its fixed arithmetic reference, plus two fresh HC fixture runs.
  Both compilers' raw bytes agree. This is deterministic candidate arithmetic,
  not a claim of equality to the old draft's reduction order.
- All **256 selections / 512 rank startups** pass real full-size allocation,
  capture, dispatch and memory admission. This is packet97's 128 compositions
  crossed with the two attention choices. Only weight payloads and the backend
  are mocked. The test distinguishes draft operations from target operations,
  checks all three HC mixtures, and verifies the selected expanded/packed head
  layout. Minimum arena headroom is 630,519,094 bytes; reserves are unchanged.
- Four short/misaligned-head refusals pass. Eight Python tests include all 256
  composition cases, aliases, small wins, wins over the mean only, equal rates,
  changed acceptance counts, inexact results, wrong lanes/boots and overlap.
- Four view seals pass. All six proposed jobs pass the real queue planner on
  temporary queue copies. No live queue, GPU or service was used.

Evidence: [draft bytes](evidence/cpu-gates.json),
[startup matrix](evidence/full-shape.json),
[memory refusals](evidence/startup-refusals.json),
[Python checks](evidence/python-tests.log),
[queue plans](evidence/queue-plans.json), [storage cleanup](evidence/storage-cleanup.json).

The coordinator may use the new proposals:

- [B grid](../../ops/lane-queue/proposed-p101-B-grid.txt)
- [A mirror](../../ops/lane-queue/proposed-p101-A-grid.txt)

After a completed bracket, run `compare.py --lane B` (or `--lane A`) under the
CPU command prefix below. `composition_qualified` uses the first-lane rule;
`record_ready` and `submission_eligible` remain false. The worker still uses
the frozen v4 lifecycle, admission, oracle, fault review and graceful teardown.
The two proposals are alternatives for coordinator scheduling, not a request
to run both lanes concurrently.

For local CPU reproduction, first restore packet97's hash-bound builds and
the inherited lab inputs; this is not a public standalone deployment recipe.
Use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin `/dev/null`, for each
script, in this order: `audit.py`, `build_engine.py`, `cpu_gate.py`,
`full_shape.py`, `negative_gate.py`, the unittest command, `prepare_packet.py`,
then `queue_plan.py`. Seals are immutable: creation expects new selection
directories. `compile_turn.py` is copied verbatim from packet94; only one
compiler runs at once. Builds reuse existing runtime binaries; only CPU test
executables are compiled. Generated build caches remain ignored.

The two Intel fixture link failures were build-driver issues: PIE flags and
linking Intel objects through GNU without Intel's runtime libraries. The final
fixture uses `-fPIE`, the matching compiler driver, and the inherited GNU OpenMP
library. An overbroad negative test incorrectly expected the serial runtime
to reject startup; the test detected its own generic fallback and failed. Only
the real short/misaligned allocation refusals are reported as passes. These
preparation failures and logs are retained; no runtime workaround was added.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md),
[do not repeat](DO-NOT-REPEAT.md), [retention](RETENTION.md),
[task note](../../../../notes/2026-10-18-own-runtime-packet101.md).
