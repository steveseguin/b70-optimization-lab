# Packet84 record bundle 2 — October17

Packet84 copies packet80 without editing it. The coordinator baseline is ordered
cleanup, wide HC, production route/norm, wide64 experts and rank1 at24/24.
Independent choices add packet81 expert reads, packet82 recurrence and packet83
Q4 or smaller draft prefixes. The unchanged target still verifies every token.

Milestone1: GNU-host and Intel-device builds passed. No device binary was run.
Full-size CPU allocation/dispatch checks and dual-compiler byte checks are in
progress. The build is about112MB so far, below the1.5GB limit. Work uses nice19,
CPUs8–15/24–31, python3 -B, stdin /dev/null and an8GiB process bound.

The initial git pull --rebase refused because other packets have work in progress.
A fetch showed HEAD and origin/main identical; no other work was stashed or moved.
The explicit coordinator pins override the earlier local packet80 route selection.
The new draft choices stay at production until both screen lanes confirm them.

[Bundle](../experiments/own-xpu-runtime/stage2/packet84-record-bundle/README.md)
and [orchestration](../experiments/own-xpu-runtime/ops/packet84-orchestration/README.md).

The first source/build milestone was committed and pushed as `a21cac5db`.
The largest compiler process used 731,936 KiB RSS. The authentic Q4 head CPU
check used 273,704 KiB RSS and checked all 91,392 rows under both compilers.
The cached byte proof covers every choice combination by independent operator
transcripts. Full-shape dispatch and allocation checks cover every configuration;
miniature engines separately exercise combined target and draft state. These are
CPU evidence only, not a record or a claim about GPU output or speed.

Review found an inherited KD metadata mismatch: packet56's fixed draft-prefix
identity did not describe packet83's coverage metadata and smaller row counts.
The new bundle now binds KD and submission checks to the selected prefix rows
and exact coverage hash. Tests reject changed rows, coverage and target-head
identity. The frozen source packets remain unchanged by this work.

CPU checks completed: all 768 operator combinations passed twice under GNU and
Intel; all 1,344 allowed configurations passed both ranks' actual post-load
allocation and dispatch paths using the mock backend. The 223 fresh miniature
runs cover 111 combined configurations twice plus the packet80 reference.
All target tokens and 96 intermediate fixtures per run match that reference.
The full regression run passed 1,488 tests and 776 subtests in 148.20 seconds.

Q4 adds 146,227,200 bytes (139.45 MiB) on rank 1. Its allowed placement has
798,864,694 bytes of arena headroom. Smaller prefixes and Q4 are restricted to
placement 1; all four packet80 placements remain available for production draft.
The first reseal took 2.85 seconds and the full selected dry run took 28.88
seconds. The expensive allocation/operator proof is cached; coordinator options
and helper edits do not enter its hash map. Readiness separately pins helpers.

The evidence archive roundtrip verified all 156,549 members. The archive is
42,359,071 bytes and the local build is about 831 MB. Retention details and
restoration commands are in the bundle's RETENTION.md.

All eight actual reselection rehearsals passed. They cover Q4, both smaller
prefixes, all expert/recurrence alternatives and every inherited placement,
then restore the pinned baseline. Reseals took 2.87–3.46 seconds and selected
checks took 28.74–55.48 seconds. Cached proof and both binaries stayed unchanged.
The final 12 orchestration tests also confirm that completed no-winner screens
retain the baseline, while pending screens refuse readiness.

Final orchestration prechecks passed twice, first with host/HC reverted to
production and then with the brief's pinned baseline restored. Pin reversion
left the cached proof unchanged. The saved ready.json has preparation_passed=true
and ready=false: packet81's B confirmation is missing, packet82's B confirmation
is incomplete, and packet83's completed B direction reports no winner. No
candidate was selected from partial evidence. The readiness verifier rejects
launch, and the chain output directory does not exist. No GPU, service,
submission, host setting or frozen source tree was changed by this work.

Rerun the documented CPU-only orchestration command after the screen receipts
finish; it reseals from the confirmed choices and writes the command without
launching it. Every selected change is disclosed in submission notes, including
draft-only arithmetic and prefix rows, with the 2,000-character cap tested for
fresh and resumed payloads across all 1,344 configurations.
