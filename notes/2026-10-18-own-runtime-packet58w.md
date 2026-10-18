# Packet58w — one-card overlap record chain, CPU preparation

Prepared on the four-card host on October 18, ahead of packet58v's device
bracket. No GPU job, service, queue entry, public submission, host setting or
parent packet was changed by this work. The current record remains
26.22859930943809 tok/s, `cmvdukc200064rf01lqsql9x8`.

The new packet copies packet58p's seven-window chain and reuses packet58v's
five binaries by hash. The native entry accepts `--cache-maintenance overlap`
without a bracket table, so no rebuild was needed. The fixed configuration is
one B70, target-only, tile16, zero-copy misses, host-pinned experts, an 18 GB
immutable device cache and context4096 BF16 KV. Packet49's
`iq3-p49-split32-v1` oracle remains authoritative through its binding and
shared reader. The template has zero symlinks; the copy inventory confirms
that none were flattened or lost.

The exact new service is `packet58-onecard-58w-a`; its fresh output is
`evidence/card0-58w-a`. The command embeds the recorded oneAPI library path.
Only PATH, LD_LIBRARY_PATH and OMP_NUM_THREADS enter Python, which may add its
automatic C.UTF-8 locale. Every window's actual startup path was exercised on
CPU, including the real environment/unit gates, read-only topology and host
admission, parser and native argument assembly. No native device exec occurred.
All seven current host admission snapshots passed; the fixture fallback in the
CPU harness was not used. Both queue and window entries reject the wrong unit
and an extra environment variable, for 28 negative checks.

All 120 Python tests pass. Five full-shape checks exercise the reused engine's
contexts 32 and 4096 and async queue mock. Five real native parser checks and
bad-mode refusals pass. The actual host oracle consumer replays 38 historical
58p requests, including retained layer bytes; those old outputs are not new
overlap quality evidence. K1's zero-copy/mixed/streamed bytes match. The maximum
native CPU child RSS was 348,807,168 bytes, below the 4 GiB ceiling. Full-shape
mocks reserve sparse virtual space, so they use an RSS check rather than a
4 GiB virtual-address cap. All runtime imports preserve resource limits, and
actual pre-exec getrlimit checks retain unlimited address space.

The copied default memory helper still returned the historical plan even
though window admission used the measured plan. The new copy corrects that
inconsistency. Every model window now requires 95,435,761,152 bytes available,
using the frozen packet58u module plus 58v's bounded async allowance. K1 still
requires 12 GiB. The 8 GiB reserve, 4 GiB shadow stop and complete native census
checks stay in place. Initial template-test mismatches are retained in
[the initial test log](../experiments/own-xpu-runtime/ops/packet58w-orchestration/initial-tests.log).
The drain clamp and teardown-before-reporting proof remain enforced.

The preparation seals 635 source/dependency files and five copied binaries.
Build size is 72,924,200 bytes. The passive plan reserves 2,952,790,016 bytes
of chain output; root had 33,201,844,224 bytes free at that check, leaving more
than the required 25 GB after the reservation. No new tracked file reaches
1 MiB. The inherited-literal audit checks twenty live chain files; remaining
58p/58m/58n/58r/58t references are classified historical provenance, CPU
negative controls, the binary's existing parser switch, or documentation.

Readiness reads the exact 58v runner paths under
`evidence/card0-async-a/{smoke,overlap}`. It rehashes complete native closures,
requires clean completed queues and the same build, and compares every token
again with packet49. The 12 × 64 smoke is mandatory. The complete 12 × 128
five-view bracket must have both overlap views at least 0.5% above each serial
control, with control drift at most 3%. Decimal comparisons preserve inclusive
boundaries. The queue repeats this verification at startup; saved flags cannot
bypass it. At the 17:52 UTC check, the smoke was complete and the bracket had
completed its two K1 windows but not its model window. `ready.json` correctly
remained false. The preparer did not launch those parent jobs.

The packet58s-derived submission tool is finished before the chain. It checks
all seven windows, native owners, cold requests, exact output and layer bytes,
then derives WS128's median of six class medians using 99 inter-token intervals.
It records major/minor process faults and zero new GPU fault lines only after
checking the journals. Notes state target-only, host-pinned experts, 18 GB cache,
zero-copy misses, tile16, overlap, BF16 KV and packet49. They remain below 2,000
characters and explicitly retain the 128-token scope,
`realistic_final_gate.passed=false`, and no strict512 claim. WS128x is exactness
only; a second fresh timing run is still missing. The predecessor ID comes from
the hash-pinned prepare-time ledger. Stale public-list wording comes from the
policy file. The shared submission CLI also checks the live ledger before any
later submission. Offline tests use synthetic evidence and forbid network.

Git pull refused because of unrelated dirty orchestration files. Fetch confirmed
HEAD equalled origin/main at the start. Only the new packet, its new orchestration
folder, this note and the current-state entry are included in the preparation
commit. The final readiness marker is written after that commit is pushed and
then committed separately; it binds that preparation commit and the full command
SHA-256. No device readiness or speed win is inferred from the marker.

- [Packet and reproduction](../experiments/own-xpu-runtime/stage2/packet58w-onecard-record/README.md)
- [Entry replay](../experiments/own-xpu-runtime/stage2/packet58w-onecard-record/evidence/argument-gate.json)
- [Build seal](../experiments/own-xpu-runtime/stage2/packet58w-onecard-record/build-receipt.json)
- [CPU closeout](../experiments/own-xpu-runtime/stage2/packet58w-onecard-record/CPU-PREPARATION-CLOSEOUT.md)
- [Final coordinator marker](../experiments/own-xpu-runtime/ops/packet58w-orchestration/READY-FOR-DEVICE.json)

## Packet58wb — cold first-view amendment, October 18

At the owner's request, readiness was amended after packet58v's 17:50–18:04
UTC data and before any packet58w chain. No packet58w output directory exists.
The first view of this one-card one-load bracket fills the initially empty
immutable device expert cache. Packet58t already showed the same effect at
15:21–15:35 UTC: 21.41 tok/s for the cold first control versus 26.13 warm.
Its historical loss and every other packet's evidence remain unchanged.

The original verifier was run before editing and refused the real evidence
with “controls drift by more than 3%”. Its output is retained in
[58wb-old-readiness.json](../experiments/own-xpu-runtime/ops/packet58w-orchestration/58wb-old-readiness.json).
The amendment excludes only A0 from drift and comparison. A0 is still reported
and must be exact. Smoke must pass, and all five views' 12 × 128 output tokens
are checked again against packet49's `iq3-p49-split32-v1`. Both overlap views
must beat each warm serial control by at least 0.5%, with warm-control drift
at most 3%. No other validation, chain, window, fault rule or metric changed.

The real replay passes. A0/B0/A1/B1/A2 are 22.730951 / 28.115842 / 26.053436 /
28.152570 / 26.078853 tok/s. A1/A2 drift is 0.097558%; the smallest overlap
gain against either warm control is 7.810884%. These are readiness comparisons,
not a new record. The record value must come from the chain's fresh WS128.
The record remains 26.22859930943809 tok/s until qualifying chain evidence exists.

All 124 Python tests pass, including the real old-rule refusal/new-rule pass,
each overlap view 0.1% below a warm control, 3.5% warm-control drift, and a
non-exact first view. All seven actual CPU launch paths and 28 wrong-unit/env
refusals pass again. The submission notes and ledger row template both disclose:
“readiness gate amended to exclude the cold-cache first bracket view (58t
precedent), before the chain; the record value is the chain's fresh WS128”.
Offline submission tests verify both disclosures and the existing notes limit.
No submission or live ledger update was performed.

Minimal reseal: refreshed Python, argument and literal-audit receipts, then
`seal.py`, `seal.py --verify`, `plan_gate.py`, and
`verify_ready.py --output .../ready.json`. Every command used nice19, helper
cores 8–15/24–31, `python3 -B`, and closed stdin. Python and argument test
peak child RSS were 65,515,520 and 33,157,120 bytes. Native builds and their
existing byte/startup receipts were retained unchanged; the 635-file seal
and 72,924,200-byte build verify. The seven-window passive plan passes.
The new ready.json is true and binds the rechecked parent evidence.

The service name, output folder and environment-embedded chain command are
byte-for-byte unchanged. Its existing SHA-256 is retained without recomputing:
`bb0b42ff2cec8c3e88ecc650292598416867c6ddc983ba137793da421862bd3a`.
The final marker is the last content write, after pushing the amendment commit;
it binds that commit and is committed and pushed separately. Fetch confirmed
HEAD == origin/main after the dirty-tree pull refusal. Commits use explicit
paths with `git commit --only`. No GPU, service, sudo, setting, live queue or
frozen packet was touched, and no chain was launched.

## Packet58wc — fresh final chain-b handoff, October 18

Chain a passed all seven exact windows but WS128 was 25.773 tok/s, below
26.228599, and was not submitted. The coordinator found concurrent CPU gates
reading the GGUF and preregistered exactly one quiet-host rerun in
[the chain-a result note](2026-10-18-own-runtime-packet58w-chain-a-result.md).
That explanation remains a finding, not measured proof. Chain b's WS128 is
final whichever way it lands; no third run and no selection between attempts.

The fresh output is `evidence/card0-58w-b`, owned by the exact unit
`packet58-onecard-58w-b`. The command differs only in those two names.
Selection, five native binaries, oracle, seven windows, 90-second gaps,
admission, pinned record and amended p58wb readiness policy are unchanged.
The submission tool refuses chain a before reading its evidence and always
discloses 25.773, its non-submission and the rerun reason in chain-b notes,
result and ledger template. The old chain-a seal and submission pins are
retained under `lineage/58w-chain-a-*`; its evidence and earlier marker were
not changed or reused.

Only light checks ran: 126 mocked/passive Python tests, all seven actual
queue-to-native entry probes, 28 wrong-unit/environment refusals, the literal
audit, minimal reseal and seal verification, passive seven-window plan, and
`verify_ready.py`. A stale old-unit test failed on the first pass; its
expectation was corrected and an explicit chain-a unit refusal was added.
Both the submission refusal and mandatory disclosure are tested offline.

All entry probes used the real chain-b command environment and unit gate;
native execution was intercepted. Every live host admission snapshot passed,
so no memory fixture was needed. Peak child RSS was 59,822,080 bytes for tests
and 32,997,376 bytes for probes, below 2 GB. Binaries were only hashed; no
native/full-shape gate, GGUF/model read, compilation, GPU work, service,
sudo, setting change, live queue edit or public submission occurred.
Existing native/full-shape receipts were retained unchanged.

The 637-file seal verifies. Regenerated `ready.json` is true on packet58v's
actual smoke and five-view evidence under the unchanged p58wb rule. The
pinned identity comparison and check summary are in
[58wc-light-gates.json](../experiments/own-xpu-runtime/ops/packet58w-orchestration/58wc-light-gates.json);
the readiness replay is in
[58wc-readiness.log](../experiments/own-xpu-runtime/ops/packet58w-orchestration/58wc-readiness.log).
The command SHA-256 (UTF-8, no trailing newline) is
`de786c365f2718d9b45e517700a1144fcf5ceeef5fb7027a83e6c11d412e30d0`.

Pull refused because of unrelated dirty files; fetch confirmed
HEAD == origin/main. Preparation is committed with explicit paths using
`git commit --only` and pushed immediately. The last content write is
[READY-FOR-DEVICE-b.json](../experiments/own-xpu-runtime/ops/packet58w-orchestration/READY-FOR-DEVICE-b.json),
binding that pushed preparation commit and command hash, then committed and
pushed separately. No chain-b output directory was created. The coordinator
still owns fresh fault review, lane-B drain, the whole-host hold and freezing
all Codex units from before K1a until completion; model-reading CPU work must
stay excluded throughout. This preparation does not launch anything.
