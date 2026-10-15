# SPEED4 closeout: confirmed-redo spare-bank restore

2026-10-15. CPU-only repair after the SPEED3 record. Device speed and exactness
for this new identity remain pending with the coordinator. The record evidence
under `build/speed3-*`, `build/results-*` and `build/incident-*` was read only.
No model weights were read, no device binary ran, and no real-model CPU suite or
compiler matrix was run. GNU, device and seal-required ASAN entry-point binaries
were rebuilt with at most two jobs, nice 19 and cores 4–15,20–31.

## Attribution from the recorded requests

`speed4_attribution.py` reads the per-request controller/draft/guess rows and
rank timings without rerunning anything. [Input hashes](evidence/speed4/attribution-input-hashes.json)
and [all phase results](evidence/speed4/cycle-attribution.json) are retained.
The following are medians across twelve **per-request miss-phase means**, the
same scope used by the reported cycle metric. Medians of individual components
need not sum to the median total.

| Phase, ms per miss | p44 record | p44 same-boot control | SPEED3 24/24 dr0 | SPEED3 24/24 dr1 |
|---|---:|---:|---:|---:|
| ROLLBACK command envelope | 0.021 | 0.022 | 1.521 | 1.794 |
| Rank-0 confirmed redo envelope | 19.617 | 19.495 | 16.630 | 18.383 |
| Exposed rank-0 draft command | 0 | 0 | 2.729 | 0 |
| Controller/accept/handoff remainder before rank 1 | 0.141 | 0.126 | 0.037 | 0.030 |
| Rank-1 half command envelope | 19.506 | 19.506 | 20.372 | 18.732 |
| Completion observation lag | 0.088 | 0.068 | 0.011 | 1.537 |
| Reported miss cycle | 39.330 | 39.218 | 41.284 | 40.434 |

The +1.954 ms dr0 headline gap is **not an isolated restore measurement**.
Relative to p44, restore/ROLLBACK adds about 1.500 ms and exposed draft work
adds 2.729 ms; faster rank-0 redo saves 2.987 ms, while the rank-1 half adds
0.866 ms. Controller/handoff and observation are smaller offsets. Rank-1 draft
placement hides its draft inside other work but exposes a later completion lag.
These are observed configurations/card pairs, not a controlled causal kernel A/B.

For an exactly additive check, pooled steady-state misses (positions >=100,
255 rows per run) have mean cycles 39.349 ms p44, 41.561 ms SPEED3 dr0, and
40.604 ms SPEED3 dr1. Dr0 minus p44 decomposes as +1.498 rollback, -2.890 redo,
+2.749 draft, +0.009 controller/handoff, +0.932 rank-1 half and -0.087 observation
= +2.213 ms, modulo rounding. Full per-request and pooled results are in JSON.

The enclosing rollback spans `rank.hpp:183` (`undo`) and
`strict_snapshot.hpp:233` (`restore`): queue drain, sticky-error check, bank
selection, validated snapshot copies and their completion drain, shared-slot and
host/launch metadata restoration. Existing receipts do not timestamp the copy
separately, so assigning all 1.5–1.8 ms to device bandwidth would be false.
`native_controller.hpp:96` places rollback and confirmed redo before rank-1's
next half; `pipeline.py:124` preserves the same reference ordering. No capture,
controller, draft scheduling or kernel-selection change is included here.

## Chosen repair and proof

Only the spare recurrent/conv banks are omitted from **confirmed-redo restore**.
Their full SPEED2 write set is still captured. `RedoBankProof` in
`strict_snapshot.hpp:81` requires one writer, the exact BF16 shape, and complete
output coverage. GDN covers `vh*d*d*2` bytes; conv covers `width*3*dilation*2`.
`rank.hpp:67` allocates distinct active/spare banks; `main.cpp:1132` binds outputs
to spare banks while inputs retain the active allocation. Runtime checks assert
that binding, distinct IDs and full saved coverage. Unknown operators, duplicate
writers and shape/coverage mismatches retain full restore.

A reduced ROLLBACK requires the candidate position/fixture and the target rank's
release-published verified token. Only the immediately matching confirmed HALF
may consume it. Its successful completion overwrites every deferred byte before
bank swap/commit. A different command, dump, cancel, reset, FINISH or boundary
restores deferred bytes before observation. Sticky errors and incomplete redo
remain fatal. Ordinary ROLLBACK, end-of-request and EOS keep full restoration.
Thus the completed redo equals never-speculating **including inactive banks,
scratch, invalid tails, both launch banks, shared slots and host metadata**.

The production metadata proof is [redo-restore-proof.json.gz](evidence/speed4/redo-restore-proof.json.gz).
Every deferred allocation carries its writer, full allocation size, offset and
covered bytes. The seal binds those to the actual extracted C++ proof and all
three dispatch plans. The plan gate rejects partial coverage, duplicate writers
and unknown writers. This is a conservative subset of possible redo exclusions;
no claim is made that scratch or general intermediates have been proved safe.
No BCS overlap or new cross-queue dependency is introduced. CopyEngine's
134,217,728-byte guard remains unchanged.

| Configuration | Capture / terminal restore | Confirmed-redo restore | Omitted restore | Bounded submissions, full → redo |
|---|---:|---:|---:|---:|
| 22/26, draft rank 0 | 46,415,032 B / 44.2648 MiB | 18,447,544 B / 17.5920 MiB | 27,967,488 B | 30 → 29 |
| 24/24, draft rank 0 | 48,614,936 B / 46.3628 MiB | 19,013,144 B / 18.1323 MiB | 29,601,792 B | 32 → 31 |
| 24/24, draft rank 1 | 48,614,936 B / 46.3628 MiB | 19,013,144 B / 18.1323 MiB | 29,601,792 B | 32 → 31 |

Counts are batched submissions, not component descriptors. Capture is unchanged.
Inventory covers both contexts and positions 100,127,128 (18 rows). Production
32K admission for 24/24 dr0 remains refused; its metadata inventory is not an
admission or execution. Detailed schedules: [inventory](speed4-snapshot-inventory.json).

## Qualification and retained failures

Fresh gates passed: **72/72 plan/dispatch rows, 93/93 mini executions, 78/78 state checks including six required-extent negative controls**. The narrow amendment has 16/16 tests, fixture reuse 9/9, audit 6 mutation checks 8/8, and seal binding 45/45. The final seal binds 46 gate receipts and 41 artifacts. Historical counts in that seal are labelled reuse and are not fresh SPEED4 runs.
The plan sweep covers 72 combinations: both contexts; existing dr0/dr1 and new
24/24 dr0; both target ranks, KD and draft plans; both measured device dispatches
and a forced all-fusion dispatch. The 192-command small-FFN repair is retained.

The mini gate compares all target state, tokens and fixtures for hits, misses,
real mini draft guesses, wrong guesses, terminal cancellation at several launch
cuts, request/bucket boundaries, partial speculative prefixes followed by redo,
and abandoned redo followed by observation. Python and native controllers cover
all three admitted configuration families. Mini layers are 2/2; production
22/26 and 24/24 geometry is covered by the metadata sweep, not claimed as mini
arithmetic. Deliberately omitting required terminal `streams` bytes must fail.

The first harness attempt expected cancellation after the final launch to remain
incomplete. That assumption was wrong; its failure and logs are retained as
`evidence/speed4/initial-snapshot-*`. The corrected abandoned-redo test forces a
completed speculative half with `cancel_launch=n+1`; intermediate-prefix cases
use 0, n/2 and n. This was a test-harness correction, not a device/runtime failure.

Named seal extension:
`packet45.speed4.confirmed-redo-spare-bank-overwrite.2026-10-15`.
It accepts only the pinned strict_snapshot/rank/native_controller headers and
pipeline controller delta, plus the enumerated qualification files. Historical
real-model/ASAN execution evidence remains historical. ASAN relinking is required
by `seal_context.py:83`; its rebuild took 106.76 s. Device W2m, WS, WSs and WS128x
against the immutable arithmetic-v2-detmath oracle remain the real-model exactness
authority. A speed publication must cite their passing current-identity receipts.

## Forecast and cheapest confirming A/B

| Configuration | Predicted saving per hit | Predicted saving per miss |
|---|---:|---:|
| Cards 0–1, 24/24 dr0 | 0 ms | 0.3–0.6 ms |
| Cards 2–3, 24/24 dr1 | 0 ms | 0.3–0.7 ms |

These are forecasts, not measured speed. Removing 60.9% of restore bytes gives a
bandwidth-only upper estimate of about 0.9–1.1 ms from the rollback envelope;
31 of 32 submissions and most descriptor/host work remain, so the forecast credits
substantially less. At 21% misses, that is roughly 0.2–0.5% overall. It does not
promise to close the complete 1.95 ms gap. No hit saving is credited because
capture is unchanged. Compare the complete same-suite WS128/WS128x chain against
the frozen SPEED3 record with identical prompt/token hashes, guesses and dispatch.
Check `redo_restores == completed_redos`, restored bytes and fallback counters,
and compare per-request rollback/miss envelopes. The coordinator's A-B-A repeat
is the speed verdict if the primary metric exceeds 38.157157.

## Coordinator commands

From the repository root, in the coordinator's admitted nice-0 systemd unit on
cores 0–3,16–19. These commands are supplied only; this CPU task never runs them.

```bash
P=experiments/own-xpu-runtime/stage2/packet45-merged3
SUITE=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
A="$P/build/speed4-c4096-dr0-s24-gpu"
B="$P/build/speed4-c4096-dr1-gpu"
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 0 4096 0 "$SUITE" "$A" 24
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 2 4096 1 "$SUITE" "$B" 0

speed4_suite_pair() {
  local out=$1 card=$2 draft=$3 split=$4
  local common=(ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" OMP_NUM_THREADS=2
    python3 -B "$P/window.py" --authorized-device-window
    --card "$card" --context 4096 --draft-rank "$draft" --target-split "$split"
    --k0 "$out/K0/window.json" --k1a "$out/K1a/window.json"
    --k1b "$out/K1b/window.json" --k2 "$out/K2/window.json"
    --w0p "$out/W0p/window.json" --kd "$out/KD/window.json"
    --dispatch "$out/K2/run0/dispatch-measured.json"
    --suite-manifest "$SUITE" --controller native --repeat 1)
  "${common[@]}" --window WS128x --output "$out/WS128x" --retain-steps 1-8,97-104 || return
  "${common[@]}" --window WS128 --output "$out/WS128" --retain-steps none \
    --exactness-window "$out/WS128x/window.json"
}
speed4_suite_pair "$A" 0 0 24
speed4_suite_pair "$B" 2 1 0
```

The helper ends at WSs; run the matching standalone exactness/speed pair only
once its chain passes. New output directories preserve all prior record receipts.

## Final artifact identity and seal

Detached admission passed **108/108** checks with every device launcher blocked
and every simulated window nonpassing/unexecuted. The real fault latch remained
unchanged. All fifteen rebuilt targets were linked after the final compiled-source
edit. Five device, five GNU and five ASAN hashes changed; 26 artifacts remain
unchanged. [Artifact comparison](evidence/speed4/artifact-identity.json) and
[BINARY-HASHES.md](BINARY-HASHES.md) contain the complete identities.

`device/own-rt-iq3`: `807a29a9752dd2258fd1e73ec47905b4412d9a3863f543c6bea7ef6c4e532f40`.
Kernel arithmetic and kernel/shared-mailbox layouts are unchanged. The existing
ROLLBACK `speculative=1` flag now explicitly requests verified redo; controllers
and workers must use the same sealed identity. No structure size or opcode changes.

| Seal artifact | SHA256 |
|---|---|
| build-receipt.json | `26038284a7adc5400a0090e6a2ae9b81d5739d24d6a455d198c996d55d512538` |
| cpu-tests.json | `58f1d47311b99c109cdd640674a8d8a6107c0300e6e68669ac404d881dddd27c` |
| seal6-amendment.json | `6a6219678df8fa5852a1ac36cf93397013537d07fe58ee737c4b5bd7e7b27002` |
| window-seal-admission-gates.json | `97256c7d42bfa1f87008ec1261e2c6b16956f01dc0ef7d959455762dae35f91e` |
| window-seal-binding.json | `3593833b421bcac2c2b2e2641638dbf2c7d3256d168bd8692636e099dd0a66d4` |
