# SPEED6 closeout: bounded scratch and pre-launch arena admission

2026-10-15. Applied `patches/packet45-speed6-memory.patch` from design
`e108f96f1` on the SPEED5 runtime (`887a0bbbe`), preserving the coordinator's
later ledger commits. The queue was stopped before edits. This is CPU-qualified
and sealed for the coordinator's device chain; no SPEED6 device result is claimed.

The SPEED5 failure had 32,382,937,248 device-owned bytes on rank 1, exceeding
its 30 GiB arena by **170,682,528 bytes (162.78 MiB)** despite passing the card
reserve. Admission now derives arena usage from the same device allocations as
`Engine::allocate`, excluding pinned staging and the separate accounting reserve.
It checks both ranks before creating the window output or entering the device
environment. A stored passed boolean or enlarged ledger cap cannot override it.
The live-census check also retains the hard 30 GiB limit.

For parallel **23/25 dr1 at 4K only**, target operator scratch becomes 8 MiB
instead of 256 MiB. Rank 0's private snapshot allocation shrinks by the same
248 MiB. Total device-owned savings are 496 MiB on rank 0 and 248 MiB on rank 1.
Rank 1 now owns **32,122,890,400 bytes**, leaving **89,364,320 bytes (85.22 MiB)**
in the arena. Its card free space is 2,118,178,656 bytes, or **589.54 MiB above
the unchanged 1.5 GB reserve**. This is allocation headroom, not measured driver
residency. No weight, KV precision, arithmetic, output, dispatch or kernel changes.

## Bounds and unchanged configurations

The runtime derives the scratch bound from the actual plan before constructing
its backend. Unknown writers, excess bounds and unproved geometry fail closed.
The reference interpreter retains its advertised 256 MiB pool. All other
production placements retain their prior allocation sizes. The mini variant
exercises the 8 MiB allocation under both Python and native controllers.

The production-size sparse proof builds every target, KD and draft plan under
both measured K2 dispatches and the forced fusion dispatch at 4K and 32K, with
five placement/split families. It checks writer unions against the kernels' full
scratch read/write requirements, including route, argmax, gather, specialised
and round2 paths. Maximum target scratch is **1,597,440 bytes**, below 8 MiB.
The GEMV workspace union reaches **7,946,240 bytes**; its existing 8 MiB size is
retained. Shrinking that workspace further would sacrifice the verified bound.
The 128 MiB CopyEngine guard and allocation/lifetime guards are unchanged.

Arena headroom is shown per rank in MiB; a negative value refuses admission.
No previously feasible configuration is newly refused. The two 32K explicit
placements shown as refused already failed card-reserve admission in SPEED5.

| Target split | Draft rank | Context | Rank 0 arena MiB | Rank 1 arena MiB | Admission |
|---|---:|---:|---:|---:|---|
| 22/26 | 0 | 4096 | 2459.03 | 1971.93 | Admit |
| 22/26 | 0 | 32768 | 1746.78 | 1518.68 | Admit |
| 24/24 | 1 | 4096 | 4317.18 | 901.31 | Admit |
| 24/24 | 1 | 32768 | 3540.18 | 448.06 | Admit |
| 24/24 | 0 | 4096 | 317.77 | 4100.28 | Admit |
| 24/24 | 0 | 32768 | -523.98 | 3711.78 | Refuse |
| 23/25 | 0 | 4096 | 1391.37 | 3036.20 | Admit |
| 23/25 | 0 | 32768 | 679.12 | 2582.95 | Admit |
| 23/25 | 1 | 4096 | 5886.78 | 85.22 | Admit |
| 23/25 | 1 | 32768 | 4743.28 | -680.78 | Refuse |

23/25 dr1 at 32K remains refused. Even hypothetically extending the scratch
saving to 32K would leave rank 1 **453,798,048 bytes over** the arena; this repair
does not admit it. Split25 remains unsupported.

## Gates and seal amendment

- **120/120 plan/dispatch rows** passed. **109,060** sparse-backend copies went
  through the real owner/CopyEngine guards without allocating weight contents;
  all **360** short-allocation or oversized-copy negative controls were rejected.
  Per-site writer evidence is in `evidence/speed6/plan-writer-sites.json.gz`.
- **62/62 mini cases**, **52/52 full-state checks**, **4/4 omitted-extent negative
  controls**: both split23 placements and both controllers; hit, miss, MTP,
  wrong guess, partial cancellation/redo, terminal/request boundary and abandoned
  redo. Production geometry is checked by the sparse plan gate, not mini shapes.
- **23/23 admission tests**, including 42 combinations of every window and
  qualifying/diagnostic mode refusing the original incident allocation before
  output creation, environment admission or child launch. The exact arena
  boundary passes; one byte over fails. Old admitted configurations remain valid.
- Binding tests: fixture delta **9/9**, amendment **18/18**, audit mutations
  **8/8**, seal bindings **45/45**. Final detached window admission is recorded
  below. No device binary was executed and no fault latch was cleared.

The named extension is
`packet45.speed6.arena-admission-and-bounded-scratch.2026-10-15`, under the
owner's seal-6 device-oracle amendment. It accepts only the exact pinned source
set and fresh sparse/mini/admission receipts. Historical memory proofs use their
hash-bound historical ledger; the new gate independently proves the current
stricter admission. The initial binding failure exposed an old comparison that
expected ledger rows to lack the added arena fields; its log is retained at
`evidence/speed6/initial-finalize.log`. No runtime check was relaxed to resolve it.

No real-model CPU suite or compiler matrix was run. W2m, WS, WSs and WS128x,
against the immutable arithmetic-v2-detmath oracle, remain the real-model
exactness authority. A speed publication must cite passing current-identity
device suite receipts. The seal binds **52 gate receipts and 41 artifacts**;
historical counts remain explicitly historical, not new SPEED6 executions.

GNU, device and ASAN rebuilds relinked only the changed main-entry targets,
using two jobs, nice 19, ionice 3, cores 4–15,20–31, OMP_NUM_THREADS=2.
ASAN provenance was required by `seal_context.py:83`; the Intel-host build was
reused under the pinned amendment. All 15 changed binaries were linked after
the final compiled-source edit. Device binary hashes changed; ABI did not.
`evidence/speed6/artifact-identity.json` records every before/after hash.

The chain helper now explicitly carries OMP_NUM_THREADS=2 through `env -i`,
matching the standalone commands and avoiding prerequisite identity mismatch.
Every runtime safety and exactness check stays in place.

## Storage and retention

Initial root free space was 25,293,262,848 bytes. Final free space and net growth
are in `evidence/speed6/storage-closeout.json`; free space remains above 22 GB
and growth is below the 1.5 GB budget. Each mini case's raw scratch was archived
and removed, then its empty parent removed. The metadata proof executable and
source remain as seal inputs. The duplicate plan row output was gzip-compressed
with a verified exact round trip. The large gate JSONs retain complete per-case
state and production plan bounds; regenerate with `speed6_snapshot_gate.py` and
`speed6_plan_gate.py` only when performing a new qualification and reseal.

No `build/results-*` symlink or target, `build/incident-*`, `build/speed3-*`,
`build/speed4-*` or `build/speed5-*` path was modified.

## Coordinator commands

Run from the repository root, in the coordinator's admitted nice-0 systemd
unit on device cores 0–3,16–19 with the approved LD_LIBRARY_PATH. These commands
are supplied, not executed here. Run each WS128x/WS128 pair only after its own
chain succeeds. Both card pairs use the same 23/25 dr1 4K configuration.

```bash
P=experiments/own-xpu-runtime/stage2/packet45-merged3
SUITE=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
A="$P/build/speed6-c4096-dr1-s23-cards01-gpu"
B="$P/build/speed6-c4096-dr1-s23-cards23-gpu"
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 0 4096 1 "$SUITE" "$A" 23
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 2 4096 1 "$SUITE" "$B" 23

speed6_suite_pair() {
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
speed6_suite_pair "$A" 0
speed6_suite_pair "$B" 2
```

The split design's speed forecast remains a hypothesis. Device exactness and
matched pair results decide adoption; no SPEED5 parity result is replaced.

## Final seal identity

Detached no-launch admission: **156/156** (152 window branches, three suite
input checks and the seal contract). Every simulated window remained failed and
unexecuted. The binding verifies the exact final seal without a circular hash.

| Seal artifact | SHA256 |
|---|---|
| build-receipt.json | `9b6fa7f397151c380a25f79dc3cf08abca1c70853300d7159febbf9456b35fbf` |
| cpu-tests.json | `ba1cb1e6b32be46aee32f799956ef4c4231eb55db74b490c6c6b3933d283c298` |
| seal6-amendment.json | `91133935cd90405b288174a93eb7b2a897dc6b72ddfa36f6ac499b9cb0ea4010` |
| window-seal-admission-gates.json | `491bfa53a39f83ac0b9348f871b75960d0f8602ebd693c76fbbe6db6947163ed` |
| window-seal-binding.json | `26d026311e82adc8b2f5ad2808b90bf6a09d455ea1c1438f7bda4c58fde0db12` |

Device `own-rt-iq3`: `a68963d2e207ee6ad1aee0d0311bc319b2b2368f02132f48d67410951f12182b`.
