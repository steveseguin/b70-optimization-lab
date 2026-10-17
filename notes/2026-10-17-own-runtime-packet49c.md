# Packet49c: packet49b plus packet51's exact winning kernels

CPU preparation is in progress on steve-b70s. This is a separate packet at
`experiments/own-xpu-runtime/stage2/packet49c-round2/`, derived from packet49b
at `192ee28f2` and the packet51 winners recorded at `c1ce0db7d`.
Neither predecessor is edited. The coordinator owns all GPU windows.
The packet49 oracle and waiting packet49b model units remain untouched.

## Registered scope

Keep split32 QSA, the p48b expert gate/up and down paths, SPEED6 dispatch,
23/25 target split, draft rank 1, capacity 4096, BF16 KV and existing memory
limits. Add only packet51 routing, HC attention/FFN gate and low projections,
and attention output/combine. Apply them at every matching production call,
including M=1 and both separately scheduled M=2 rows. Leave expsgate,
GDN QKV and HC injection otherwise unchanged.

Arithmetic remains `iq3-p49-split32-v1`. Reuse the existing packet49 CPU oracle
through a read-only symlink and hash binding; model-window receipts must bind
its completed manifest, determinism result, KD capture and completion receipt.
No new oracle is launched. Full-model agreement remains a coordinator gate.

## CPU preparation and storage plan

Build GNU host, Intel device code (compile only) and ASAN/UBSAN serially, with
`nice -n 19`, `taskset -c 4-15,20-31`, `OMP_NUM_THREADS=2`, and `python3 -B`.
Run fresh fixture, ownership, plan, snapshot, sanitizer and admission gates.
An independent reviewer checks integration, STOP behavior and the final seal.
No GPU, service, sudo, host setting or model payload operation is authorized
for this preparation.

The initial check found 20,984,156,160 root bytes free. The copied 2.5GB build
budget plus both chains would require 22,765,608,960 bytes: a 1,781,452,800-byte
shortfall. The new packet preserves the 8GB free floor, all 5,818,804,480 bytes
of packet49b's pending model writes, and 500MB oracle growth. Its own chain
has a 5,946,804,480-byte peak allowance, including128MB early receipts.
Preparation will reduce only its own regenerable compiler scratch and
sanitizer binary duplication. The proposed retained build cap is650MB;
actual final fit must pass a fresh check. CPU preparation may temporarily
use up to2.5GB while preserving the other chain and free floor. No unrelated
scratch is deleted.

## Coordinator handoff plan

Use a new `packet49c-round2/build/device-cards01-a` chain for
K0 → K1a → K1b → K2 → W0p. The model sequence is
KD → W2m → WS → WSs → WS128x → WS128, with `--wait-oracle`.
Both fresh K1 windows must include the new kernels' byte fixture.

Packet49b holds only its chain-local flock while waiting for the oracle.
The coordinator may write its chain's `STOP`, then verify the queue has exited
without starting KD before queueing packet49c's model phase. STOP releases
no storage reserve by itself. The old chain and its historical files remain.
Exact commands and checked switch tests will be included in the final runbook.

No integrated device speed is claimed. Packet51's operator gains do not prove
an end-to-end gain. The 39.422 tok/s record is unchanged; WS128 is the matching
128-token comparison, not the separate 512-token publication gate.

## Integration checkpoint

The corrected GNU build and 41 Python admission/storage/switch tests pass.
Independent kernel review found two issues before qualification: a duplicated
HC dispatch hook in command preparation, and attention scratch included in a
cross-backend hash despite being device-only. Both are corrected. The direct
HC gate fixture was also expanded from four rows to its production 10,240 rows.
The initial failed build's raw log was overwritten after an evidence-copy
path error; the reconstructed rejected block and explicit retention limitation
are in `evidence/preparation-corrections/`. No failed run is counted as passing.

The full-layer CPU adapter uses actual `execute_site` dispatch with legacy
execution enabled; it does not qualify prepared replay or full-model MTP.
Those remain device/model gates. Compilation and remaining CPU tests continue
serially. The independent reviews and exact coordinator runbook are included
in the new packet. No predecessor, oracle unit or queued model unit changed.

The full-layer CPU adapter passed two fresh processes, each36 cases and5,472
byte comparisons. Intel compilation then exposed a prepared-wrapper scope
issue: its range capture moved a reference to block-local `wg=256` out of
scope. The final kernel uses literal256 in that unchanged launch range.
Its failed source, transformed mirror and compiler log are preserved under
`evidence/device-compile-refusal/`; the pre-fix passing CPU receipts stay
historical. Independent review confirms identical geometry and arithmetic.
The device build now passes without execution. GNU and CPU evidence are
being refreshed against this final source identity before sanitizers and seal.

## Final CPU preparation, 06:42 UTC

GNU, device compilation and ASAN/UBSAN builds now pass on the same final
159-source identity. All ten fresh GNU fixture runs and six ownership suites
pass. New route/HC/attention fixtures pass 384 checks across two GNU and two
sanitizer processes. The two fresh actual-engine CPU runs each pass 36 cases
and 5,472 comparisons. The unchanged expert fixtures pass 192 GNU/sanitizer
checks; split32 sanitizer fixtures pass 176. Both state gates pass 31 cases
and 26 checks. All 56 Python tests pass, including waiting-queue STOP,
cross-chain admission and exact sanitizer archive restoration tests.
The final seal and verification pass: 39 live artifacts and 451 source pins.

The retained build is 539,704,546 bytes. The final storage receipt records
20,465,577,984 root bytes free and 20,375,904,414 required: 89,673,570 bytes
above the combined budget. Both requested chains fit, preserving the 8 GB
free floor, the entire 5,818,804,480-byte pending packet49b model reserve,
500 MB oracle growth, and a 650 MB retained-build cap. The small margin
requires a fresh live check before every queue launch.

Cleanup removed only our 350,250,872 regenerable object bytes after hashing.
The 848,599,576 sanitizer executable bytes are retained exactly as
100,224,902 gzip bytes, verified against original build hashes before source
removal; GNU and device binaries remain directly runnable. Restore is
documented. All observed preparation sizes stayed below 2.5 GB. No existing
packet scratch was removed. If later unrelated writes consume the margin,
the exact closed-object fallback lists 477 objects totaling 210,435,768 bytes
in packets 40/37/35/36; the coordinator must recheck and hash selected files,
never delete whole trees or retained packet17 numerical evidence.

The waiting packet49b queue releases its only chain-local flock on STOP exit.
Historical lock/state files do not block packet49c. The tested switch requires
49c's own early passes, packet49b still waiting with no KD child, STOP, exit
and lock-release verification, then a new 49c model queue with `--wait-oracle`.
There is no shared atomic launch lock: oracle readiness during early 49c is
a scheduling risk that the coordinator must control. STOP never frees the
protected packet49b disk reserve or cancels an already-running GPU window.

See [the exact early and switch commands](../experiments/own-xpu-runtime/stage2/packet49c-round2/WINDOW.md)
and [the preparation closeout](../experiments/own-xpu-runtime/stage2/packet49c-round2/CPU-PREPARATION-CLOSEOUT.md).
No device execution or full-model gate was performed here; no speed claim
or record update follows from these CPU results. The oracle and packet49b
units, all predecessor packets and host settings remain untouched.

Pushed checkpoints: `70acc005b` preregistration, `8a9f609f3` integration,
`81d055cba` prepared-range compile correction. The final commit adds these
CPU receipts, archive retention, seal and handoff; each carries the requested
Codex co-author trailer.
