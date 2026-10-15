# SPEED7 closeout: size-aware snapshot batching

Owner directive: 2026-10-15. Baseline: SPEED6 `34c62b433`, build receipt
`9b6fa7f397151c380a25f79dc3cf08abca1c70853300d7159febbf9456b35fbf`.
This implements lever 1 of [the retained analysis](../../../../notes/2026-10-15-p45-after-speed6-levers.md).

## Change and contract

`SnapshotBatch::accepts` in `strict_snapshot.hpp` caps the largest extent in
an ascending batch at eight times its smallest. The existing 32-descriptor
and 128 MiB aggregate limits remain. Every component still passes the original
`CopyEngine::copy` guard, including nonzero length, live owners and both bounds.
The kernel, descriptors, byte offsets, byte lengths, snapshot write set, redo
proof, arithmetic, selected dispatch, lifetime tracking and exactness checks
are unchanged. A singleton still uses the existing native-copy path.

Capture and each restore mode copy exactly their own SPEED6 byte sets. Full
terminal restore equals capture; the retained SPEED4 confirmed-redo rule omits
only proved overwritten spare banks, and restores those on abandonment.
This change neither broadens that rule nor introduces caching or BCS overlap.

There are **zero new owned device allocations**. The memory ledger is verified
byte-for-byte against SPEED6. Split23/dr1 rank1 remains at 32,122,890,400 owned
bytes, leaving **89,364,320 bytes = 85.224 MiB** below the 30 GiB arena cap.
Every admission/refusal is unchanged, including 32K split23/dr1 refusal.
No protocol, kernel argument layout or other ABI changes.

## Production-size copy evidence

Numbers below describe one snapshot, using retained production allocation
metadata and freshly constructed plans. No model weights were read. All cases
were checked at contexts 4096 and 32768, positions 100, 128 and 214. Unadmitted
configurations at 32K are geometric tests only and remain refused by admission.

“Grid slots” are padded 16-byte work-item capacity, **not transferred bytes or
allocated memory**. “Padding” subtracts payload bytes from those slots; singleton
native copies use a conservative equivalent slot count. Both are reported to
avoid presenting padding reduction as memory-traffic reduction.

| Split / draft rank | Phase | Payload bytes, unchanged | Batches before → after | Grid slots before → after | Padding bytes before → after |
|---|---|---:|---:|---:|---:|
| 22/26 dr0 | capture | 46,415,032 | 30 → 31 | 116,355,584 → 51,185,216 | 69,940,552 → 4,770,184 |
| 22/26 dr0 | full restore | 46,415,032 | 30 → 31 | 116,355,584 → 51,185,216 | 69,940,552 → 4,770,184 |
| 22/26 dr0 | redo restore | 18,447,544 | 29 → 30 | 45,192,704 → 27,582,976 | 26,745,160 → 9,135,432 |
| 22/26 dr0 | deferred restore | 27,967,488 | 2 → 2 | 55,050,240 → 30,056,448 | 27,082,752 → 2,088,960 |
| 24/24 dr0 | capture | 48,614,936 | 32 → 34 | 252,381,184 → 52,424,672 | 203,766,248 → 3,809,736 |
| 24/24 dr0 | full restore | 48,614,936 | 32 → 34 | 252,381,184 → 52,424,672 | 203,766,248 → 3,809,736 |
| 24/24 dr0 | redo restore | 19,013,144 | 31 → 33 | 208,472,064 → 24,264,320 | 189,458,920 → 5,251,176 |
| 24/24 dr0 | deferred restore | 29,601,792 | 2 → 2 | 58,195,968 → 31,813,632 | 28,594,176 → 2,211,840 |
| 24/24 dr1 | capture | 48,614,936 | 32 → 34 | 252,381,184 → 52,424,672 | 203,766,248 → 3,809,736 |
| 24/24 dr1 | full restore | 48,614,936 | 32 → 34 | 252,381,184 → 52,424,672 | 203,766,248 → 3,809,736 |
| 24/24 dr1 | redo restore | 19,013,144 | 31 → 33 | 208,472,064 → 24,264,320 | 189,458,920 → 5,251,176 |
| 24/24 dr1 | deferred restore | 29,601,792 | 2 → 2 | 58,195,968 → 31,813,632 | 28,594,176 → 2,211,840 |
| 23/25 dr1 | capture | 48,332,354 | 31 → 32 | 183,303,680 → 54,000,160 | 134,971,326 → 5,667,806 |
| 23/25 dr1 | full restore | 48,332,354 | 31 → 32 | 183,303,680 → 54,000,160 | 134,971,326 → 5,667,806 |
| 23/25 dr1 | redo restore | 18,730,562 | 30 → 32 | 91,028,992 → 21,505,216 | 72,298,430 → 2,774,654 |
| 23/25 dr1 | deferred restore | 29,601,792 | 2 → 2 | 58,195,968 → 31,813,632 | 28,594,176 → 2,211,840 |

For the coordinator's 23/25 dr1 case, padded grid slots fall **70.54%** for
capture/full restore and **76.38%** for redo restore. The one/two extra
submissions avoid rectangular grids dominated by the largest descriptor.
This is a CPU-verified work-size reduction, not a measured GPU speedup.
The prior central hypothesis remains about 0.225 ms/hit and 0.810 ms/miss;
the device chain and a matched repeat decide the actual benefit.

## Qualification and retention

- Production plan/dispatch sweep: **144 rows**, all passing; both device-measured
  dispatches plus forced fusion selection, two contexts, all six split/placement
  representations, target ranks, KD and draft plans. The small-FFN repair still
  removes its 192 commands. Sparse production workspace guards also run here: **130,744 owner checks**
  and **432 deliberate refusal controls**.
- Production snapshot copies: **24 configurations/positions × four phases = 96**
  passing copy phases; **120 negative controls** and **72 policy-boundary checks**.
  The probe extracts the actual `SnapshotBatch` and runtime batching loop, uses
  the real owner/CopyEngine implementation with sparse mmap-backed allocations,
  compares every payload byte, checks untouched neighbouring bytes, and requires
  each descriptor exactly once. It checks zero length, over-128-MiB, both bounds
  and a deliberately dropped written byte. It reads metadata, never weights.
- The plan and copy probe sources/binaries are hash-bound; temporary build
  directories are removed after archiving. Retained archives and writer lists
  reproduce the checks without accessing model weight bytes.
- Two early copy-harness attempts correctly failed owner admission (scratch
  lifetime category and duplicate allocation labels). Their logs are retained;
  fixing the harness did not change runtime code or owner guards.

- Miniature full-state gate: **93 cases**, **78 checks**, including **six**
  required-extent exclusion negative controls. The three configurations are
  split23/dr1, split24/dr0 and split24/dr1, each with native and Python
  controllers: hit, miss, real mini MTP, wrong MTP guess, partial cancellation,
  terminal/request-boundary rollback and abandoned redo. All passed.
- Admission: **23/23** unchanged tests; source/reuse tests **9/9**, named
  amendment tests **23/23**, audit mutation checks **8/8**, seal bindings **45/45**.
- Final CPU seal: **56 gate receipts / 41 artifact hashes**. Legacy execution
  counts remain labelled historical; the fresh SPEED7 counts above are separate.

Reproduce the fresh gates with `python3 -B speed7_plan_gate.py`,
`speed7_copy_gate.py`, `speed7_memory_gate.py` and `speed7_snapshot_gate.py`,
under nice 19, ionice 3, cores 4–15,20–31 and `OMP_NUM_THREADS=2`.
The first two compile only CPU metadata/probe programs; the miniature gate
executes only the GNU host binary. Build provenance is in
`evidence/speed7/build-{gnu-host,device,asan}.json`.
The GNU/device builds took about 33/40 seconds; the ASAN build required by
`seal_context.py:83` took about 106 seconds. Only targets including the changed
snapshot header were relinked; no device binary was executed. Fifteen artifact
hashes changed across those modes. The icpx-host historical evidence is reused
through the explicit, narrow amendment. No real-model CPU suite or compiler
matrix ran.

The named extension is
`packet45.speed7.size-aware-snapshot-batches.2026-10-15`, under the owner’s
seal-6 device-oracle amendment. Reuse accepts exactly the pinned header change
and preserves earlier receipts with their historical source/binary identities.
The unchanged model, arithmetic and dispatch are not recertified by historical
CPU runs: **W2m, WS, WSs and WS128x on the new artifacts remain the real-model
exactness authority**, and publication must cite their passing receipts.

## Coordinator commands

Run from the repository root in the coordinator's admitted nice-0 device unit
on cores 0–3,16–19, with the approved LD_LIBRARY_PATH. These are handoff commands,
not commands executed during this CPU-only repair. Each standalone suite pair
requires its own successful K0–WSs chain first.

```bash
P=experiments/own-xpu-runtime/stage2/packet45-merged3
SUITE=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
A="$P/build/speed7-c4096-dr1-s23-cards01-gpu"
B="$P/build/speed7-c4096-dr1-s23-cards23-gpu"
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 0 4096 1 "$SUITE" "$A" 23
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 2 4096 1 "$SUITE" "$B" 23

speed7_suite_pair() {
  local out=$1 card=$2
  local common=(ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" OMP_NUM_THREADS=2
    python3 -B "$P/window.py" --authorized-device-window
    --card "$card" --context 4096 --draft-rank 1 --target-split 23
    --k0 "$out/K0/window.json" --k1a "$out/K1a/window.json"
    --k1b "$out/K1b/window.json" --k2 "$out/K2/window.json"
    --w0p "$out/W0p/window.json" --kd "$out/KD/window.json"
    --dispatch "$out/K2/run0/dispatch-measured.json"
    --suite-manifest "$SUITE" --controller native --repeat 1)
  "${common[@]}" --window WS128x --output "$out/WS128x" --retain-steps 1-8,97-104 || return
  "${common[@]}" --window WS128 --output "$out/WS128" --retain-steps none \
    --exactness-window "$out/WS128x/window.json"
}
speed7_suite_pair "$A" 0
speed7_suite_pair "$B" 2
```

## Final seal identity

The CPU seal and **156/156 detached no-launch admission checks passed**.
Every simulated window remained failed/unexecuted; the real fault latch was
unchanged. The detached binding names the exact final seal without a hash cycle.
Qualifying device windows remain the coordinator's task.

| Seal artifact | SHA256 |
|---|---|
| build-receipt.json | `1a7802c35d175ec2451a0ce887e51f06f2956a898db3b07b4955ccf9b9abb72b` |
| cpu-tests.json | `25e9590d7ddffae0bb23b6dfbf63446bc157a2a2dd9d21645d889ae94f22f24c` |
| seal6-amendment.json | `07c5f253c7af28426c144c58e9b0f58d82ffd54cf81270d5dc9ea02ef37798ca` |

| window-seal-admission-gates.json | `cda5e2a9c399f0e642d8a3245488ddb5fc4ec31d4c5250375791962595edd8a1` |
| window-seal-binding.json | `cbd5ea3664335f2b93c822bc807f3d55d2513defb2f144efef937d6db61b9ab6` |

Device `own-rt-iq3`: `4ed9e6613b8d22b742079392825b1c65d9c322eed727b3ab515443bf1b885d59`. All five device binaries changed; ABI unchanged.

Final free disk before commit: **23,146,721,280 bytes (23.147 GB)**, versus 23,172,751,360 at start. Net growth is 26.0 MB, below the 1 GB bound. All own temporary probes and mini scratch directories were removed after retaining their evidence. No protected record, result symlink or incident directory was written.
