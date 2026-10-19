# Packet58al: demand-transfer build preparation

October 19, 2026; bounded CPU-only preparation during the one-card timing
session. Started at 03:09 UTC on `steve-b70s`. No build, GPU/native execution,
model/GGUF read, service, sudo, setting change or queue edit. Existing packets,
screen evidence and ops were read-only. Helper work used nice19, cores
8–15/24–31, Python `-B`, closed command stdin and a 2 GiB audit address-space
cap. No GPU recovery or inspection was attempted by this task.

The [design packet](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/README.md)
and [ready build brief](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/briefs/build.md)
specify one candidate for packet58am: copy known misses on BCS while resident
expert slots compute, then consume missing slots and combine in the original
order. Two banks hold at most 64 packed experts (126,156,800 bytes). Each entry
stays owned until its consumers finish; retained bytes can replace a later
policy-selected host transfer with a device copy. Full banks fall back to the
original zero-copy path. No cache-size, arithmetic or precision change.

The parent has an important trap: its ordinary copy call immediately inserts
a compute barrier. The new mechanism needs separate owned demand events and
a barrier only before the missing-slot consumer. Direct zero-copy reads run
on CCS, not BCS. Copies and maintenance share the copy engine; a new queue
does not create another engine. Original slot-indexed outputs and the p109
ordered combination must stay unchanged.

Packet125's tile16 arm already beat its transfer pipeline (187.0/185.8 versus
192.2/194.9 µs). Its masks were simulated, although router IDs were real. This
proposal instead requires actual published misses, resident neighbors and
the full packet58ah composition. All requested one-card closures are mapped
in [DO-NOT-REPEAT](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/DO-NOT-REPEAT.md).
A parallel read-only review checked those closures and the stage lifetimes;
it made no edits.

There is also an identity mismatch in the starting brief: packet58ai's
retained source, README and readiness measure packet58ad's 30.396 line, not
packet58ah's full 31.663 composition. Its result can justify a bounded CPU
build hypothesis, but cannot be relabeled a current-parent measurement. The
[decision table](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/DECISION.md)
covers ≥1 ms, <0.670 ms, the middle region, unstable, failed and pending
evidence. The same-parent 64-token smoke is explicitly screening; only a
matched unprofiled v5 can decide speed. It cannot reconstruct a 99-interval
census from 64 outputs.

The [real parent audit](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/evidence/parent-audit.json)
reconstructs **31.66271941826957 tok/s** from all twelve chain-b WS128
requests. It binds source/result/native argv and retains cold first-request
rows. The first prefill token took **23,457.6 ms**, and that request's
prefill total was **28,124.118482 ms**. A short time ceiling in a data proof
would reject valid parent evidence. The build brief requires no such ceiling,
a real device-binary CPU preparation probe, offline relative-tolerance
checks, and per-op waits at least four times the measured cold phase with
a 300-second minimum initially.

Measured parent output sizes (file metadata only): K1a **4,046,707 bytes**,
K1b **4,046,714**, KD **22,321,118**, WS128 **16,843,381**. The new build must
measure its added schema/storage and keep planned writes no more than three
times the matched measured-volume estimate, above the unchanged **25 GB**
device-job disk floor. CPU preparation stops below **27 GB**. Staging stays
inside the existing device transfer allowance and adds explicit conservative
host backing while preserving the **8 GiB host reserve**.

Validation command:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/audit.py </dev/null
```

The audit passes all pinned source hashes/ranges and the twelve real requests;
it is not a new model-quality proof or a future demand analyzer. The brief
requires GNU/Intel real-shape bytes, real cold-evidence analyzer replay,
smoke plus one-load v5 with first view warm-up, fresh identities and READY
written last. No READY-for-device marker is issued by this design packet.

At the 03:38 UTC observation, no completed packet58ai `census-analysis.json`
was present. No miss-cost or overlap number is invented. Latest poll and
build-release status are retained in
[evidence/poll.json](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/evidence/poll.json).
The prep keeps build release withheld until a qualified verdict arrives.

The later 03:42 UTC poll still has no completed census. The owning note records
that the b-smoke attempt refused **before device work** at 03:34:35 because
its coordinator gate used an old job name. The c-smoke identity repair is
committed, with fresh proposal checks passing; that preparation is not a
device verdict. Its readiness hash, repair receipt and the failed attempt's
exit receipt are now pinned in the poll. No partial/missing number is used
to build or close rank 4. The initial design commit `2952181a5` was pushed
immediately; the final update retains this newer observation. Preparation
finished inside the 60-minute limit.

Final audit peak RSS was approximately **18 MiB**. It also checks the proposed
staging/host arithmetic against the parent admission metadata, explicitly
leaving real simultaneous-lifetime and live admission gates pending. Document
links and Git whitespace checks pass. Review clarified that exhaustive masks
apply to ownership/address bookkeeping, with representative full-shape
arithmetic cases, and that v5 disables event profiling in both arms. New-schema
storage sizes measured from synthetic serialization stay labeled as such
until the actual smoke replaces that estimate.

Git: initial `git pull --rebase` refused unrelated dirty files. Fetch showed
the coordinator's local review commit ahead of origin; a later fetch confirmed
HEAD == origin/main at `ca9822f755899d9b0aec1b96ed8298fe1d8f4202`.
Only this packet and this note belong to the prep commit. No live state was
changed, so CURRENT's running-lane authority is left to the coordinator.

## Packet58an — resident record parent and real queue rows

October 19, CPU-only release work began at 05:07 UTC. The stopped packet58amc
work was reviewed in its owned packet58am tree. Its useful direct-screen,
harness and proposal changes were retained. The old blocked handoff, failed
probes and original decision remain preserved.

The candidate now has packet58aj's exact resident lookup copies and lookup
read path, pinned by source hash. Both controls and candidate use that
**31.966820 tok/s record line**, `cmveqsmsl00ebrf014yvrsosx`. The same-parent
mapped fallback was not needed. The coordinator's 04:40 census override is
recorded in `RELEASE-AMENDMENT.md`; `DECISION.md` is unchanged. This is CPU
qualification, not a new measured speed or device-quality pass.

GNU and Intel pass the resident packed/BF16 row byte fixtures and the real
production-shape demand partition fixtures, twice each. The ownership tests
cover all 1,024 masks across 48 layers and delayed leases. Miniature lookup
and request-reset outputs match. An attempted miniature demand bracket
correctly lacked the demand transport backend; that diagnostic is retained,
not presented as a pass. Actual smoke/v5 argv instead exercise the real device
binary parser, prepared hooks, both parity banks and first decode through
explicit CPU storage/transport mocks. Strace shows no model or device opens.

The private queue harness vendors all 43 packet58aj originals by hash,
including sensors, fault review, admission, drain and teardown. Active
admission inputs have private exact copies. Unused inherited vendor manifests
remain byte-identical `.snapshot` records with a relocation inventory; no
shared pin guard or sibling packet was changed. The K1 help adapter execs the
unchanged pinned fixture in the same PID. Every proposed model/K1/queue flag
is checked against executable help.

The fresh inert rows are `packet58an-demand-smoke-A` and
`packet58an-demand-v5-A`, in the two requested `proposed-p58am-*-A.txt` files.
Both are lane A, card 0, `screen-<job>`, K1a/K1b/WSCREEN, one model load,
879-second operation waits and a 25 GB device floor plus reserved writes.
Smoke executes 24 requests across S0/S1. Its legacy report count describes
12 distinct prompts; a separate total and both complete view reports retain
all 24. V5 executes 60 requests, A0/B0/A1/B1/A2, with A0 excluded only from
speed and drift. Both isolated plans and both shared entry/report rehearsals
pass. The generic missing-rank preparation adapter and identity classifications
remain WARNs, supplemented by the real one-card preparation and environment
probes; no warning is relabeled a shared preparation pass.

In-run analysis now checks stream presence/format and exact oracle tokens.
Inherited duplicate-event, byte accounting, timestamp ordering and timing
consistency checks run after native exit. Native completion markers follow
stream flushes. Safety, cooperative waits and drain guards remain. Real
packet58ah and packet58aj complete 12-request device streams pass offline
replay; synthetic demand schema tests are labeled separately. A read-only
parallel audit verified resident source parity, all harness snapshots,
routing and deferred analysis and found no further concrete blocker.

The final marker is written after proof verification and immutable pin checks.
It makes the smoke CPU-ready for fresh coordinator admission. **V5 still needs
a successful same-parent smoke and actual measured storage refresh/reseal**;
there is no fabricated smoke result. Device overlap, overhead, oracle quality,
actual memory peaks and speed remain pending.

Work used nice 19, helper cores 8–15/24–31, Python -B and closed stdin.
Every compile went through `ops/compile_turn.py`; peak compiler RAM was
758,566,912 bytes, and build plus source closure was about 250 MB. The 300 MB
build limit counts retained proof logs separately; an earlier overly broad
whole-packet limit refused an ownership rerun as new evidence accumulated.
Its refusal is retained, and the rerun passed under the brief's build limit.
Root remained above the 27 GB CPU stop floor. No GPU, service, sudo, setting,
GGUF read or live queue edit was performed. CURRENT remains the coordinator's
live-state authority. Details and all receipts are in the
[packet README](../experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/README.md).

## Packet58amd — token-zero device-flag localization

The failed packet58an smoke retains all original evidence under
`screen/evidence/card0-demand-n/smoke`. S0 passed all twelve prompts. S1 has
empty progress/site streams and 48 demand rows for its first token: every
layer reports zero resident slots and zero staged entries. The first failure
is therefore in the candidate partition/fallback path before any expert
staging copy; the old streams cannot identify which layer set the flag.
This is an engine flag, not a new kernel driver fault.

A separate inert `proposed-p58am-checked-A.txt` row names
`packet58amd-demand-checked-A`: the unchanged native binary, `--checked`,
one candidate model load, first prompt only, and inherited K1a/K1b and
whole-host safety gates. Every native/K1/queue flag passes executable help;
temporary lanequeue planning and shared report rehearsal pass. The shared
report adapter covers the inherited smoke/bracket reports, not a synthetic
claim of a successful checked device run. `checked-READY.json` authorizes
only this diagnostic row; the main READY is false during repair. The
coordinator observed the marker and began the row; this CPU task launched
no device or service and changed no live queue. Native sources/binaries
are unchanged pending localized evidence.

The first checked attempt stopped gracefully before localization: its
non-suite request reset reopened the root load-progress stream, and the
pinned-memory sensor correctly refused the truncated stream. This was a
harness error, not a new sticky-device result. `packet58amd-demand-checked2-A`
uses a two-field, one-row suite file instead, preserving the load-progress
stream and placing request logs in their own folder. Native bytes are still
unchanged. Fresh temporary planning, executable-help flags, and shared report
rehearsal pass; the separate checked marker is written last again. The failed
attempt and its old launch identities are retained.

The offline event audit then narrowed the failure: layers 0–2 perform expert
work, while layer 3 onward skip almost immediately. The manifest explains a
concrete bug at that boundary. Layer 2 uses IQ3_XXS gate/up weights, with
704,000 bytes per expert; the candidate forced the IQ2_S kernel and its
524,800-byte layout onto that layer. The earlier CPU byte fixtures used only
IQ2_S gate/up banks, so they did not cover this dispatch mistake. Recorded
copy edges are ordered, and no packed expert copy occurred in the failed
token. The checked2 marker was retired before launch once this was found.

The repair keeps layer 2 on the unchanged parent commands, uses actual bank
extents in the descriptor, and permits fixed-layout staging only on matching
banks. A direct partition type check also rejects a wrong quantization.
The real-plan CPU preparation regression checks that layer 2 has no captured
demand partitions. The old 240-command census is its negative control; the
corrected census has 236 commands. New device exactness is still required;
the original failure, stopped localization attempt, and old seals remain.

The rebuilt GNU and Intel byte gates pass, as do lookup/reset and delayed-lease
tests. Both real-argv CPU preparation runs report 236 commands and pass the
layer-2 exclusion check. The old 240-command census is rejected. Compiler peak
RAM was 757,436,416 bytes. The fresh `packet58amd-demand-smoke-A` and
`packet58amd-demand-v5-A` rows pass temporary lanequeue plans, report rehearsal,
and binary-help flag checks. READY grants CPU-qualified smoke admission only;
the repaired binary has not run on a GPU. V5 still needs the successful smoke
and actual storage refresh. See the
[repair closeout](../experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/p58amd-closeout.md).

## Packet58ame — recover the completed smoke report offline

The amd smoke completed its device work and both exact oracle comparisons.
Its outer report failed because the copied harness lacked the 58c supervisor
fixture manifest. Seven fixture files now match packet58aj and packet58ah by
hash. The regression test calls the real report functions on the saved smoke;
it fails on the old tree and passes after the fix. The complete report-path
open audit found no remaining missing lineage inputs.

Offline recovery preserves every original receipt and records hashes of all
inputs and new reports. **S0 and S1 are each 12/12 exact** against the unchanged
`iq3-p49-split32-v1` oracle. The old cross-session overhead check still fails;
it has not been relabeled. The owner's packet58ame instruction explicitly
accepts recovered exact S0/S1 for the v5 smoke precondition, as recorded in the
packet's recovery policy.

The fresh inert row is `packet58ame-demand-v5-A`. It may run directly after
fresh coordinator admission, with no smoke rerun. Its storage reservation now
uses the measured 179,061,955-byte smoke output. CPU real-arm sequencing,
17 Python tests, real native preparation, parent replay, executable-help checks,
entry/report rehearsal and isolated lanequeue planning pass. READY is written
last. No GPU, service, sudo, settings, model read or live queue change occurred.
See the [recovery closeout](../experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/p58ame-closeout.md)
for evidence paths, preserved failure, overhead caveat and exact next action.

## Packet58am result (coordinator, 06:55 UTC): demand transfer halves one-card decode; closed

One-load v5 `packet58ame-demand-v5-A`, card 0 whole-host, 06:35–06:52 UTC, run in v5-only mode because the recovered smoke report was exact.

| View | Choice | tok/s |
| --- | --- | ---: |
| A0 | parent | 31.649 (warm-up, excluded) |
| B0 | demand | **15.255** |
| A1 | parent | 31.886 |
| B1 | demand | **15.194** |
| A2 | parent | 32.033 |

- 60/60 exact, drift 0.46%; the candidate is **−52.6%** vs the best warm control.
- The parent views confirm the 31.97 record line (31.89/32.03).
- **Closed**, with a DO-NOT-REPEAT row in packet58am. The pre-sealed record chain (packet58ap) is not run.
- With packet58ao's audit (no other one-card lever ≥ 2%), the one-card single-stream decode line has no open lever above the bar. Next widened target: batched prefill (packet165).
