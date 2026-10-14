# Packet45 storage admission repair — closeout

<!-- campaign-closeout -->

## Question and identity

October 14, 2026, CPU-only follow-up to `fd650dd1c`. The owner reports that
K0 and K1a passed both card pairs under boot `13858eef`, then the next chain
stage refused storage admission before device contact. The reported state was
31,558,537,216 free bytes, 1,552,906,002 build bytes, and a 2,500,000,000-byte
reservation against the inherited 3,000,000,000-byte build limit.

The checked-in projection assigns 1.1 GB to K1a/K1b and 2.5 GB to K2; the
reported K1b label is preserved as the owner's observation, without relabeling
any receipt. Both cases and the later windows are covered by this repair.
Official/quantized model bytes, all C++ runtime/kernel sources, device artifacts,
coordinator commands, context capacities and rank placements remain unchanged.

## Outcome

The selected design keeps the aggregate build limit, but derives its ceiling
from the merged retention plan and current disk headroom. It does not delete
seal-bound files, move coordinator output, or grant unlimited build growth.
The original 3 GB becomes the base artifact allowance; one worst-context
nine-window chain adds 11,486,186,752 bytes. The structural ceiling is therefore
14,486,186,752 bytes. Each admission also reserves another complete chain on
disk, above the unchanged 8,000,000,000-byte free-space floor.

For free space F, current aggregate build size U and next write E, the effective
cap is `min(14486186752, U + F - 8000000000 - 11486186752)`.
Require `F - E >= 8000000000 + 11486186752` and
`U + projected_build_write < effective_cap`. At the reported failure, the
effective cap is 13,625,256,466 bytes and the projected build is 4,052,906,002.
Repeated or extra windows consume this finite allowance; they cannot enlarge
it. See [CAPACITY.md](CAPACITY.md) for scope and derivation.

The complete serial CPU campaign passed and the final independent verification
passed. The seal binds 24 gate receipts and 41 build artifacts. No device
qualification is claimed here.

| Fresh gate | Passed counts |
|---|---:|
| HC compiler matrix | 6 arms, 4,752 checks |
| Capacity fixture matrix | 12 arms, 22,326 arithmetic + 6,899 validation checks |
| Capacity selection | 854,164 checks |
| ASAN/UBSAN fixtures | 3,657 checks |
| Merged p39 fixtures / owner gates | 56 checks / 18 suites |
| Memory-plan / kernel tests | 65 / 72 |
| Wrapper, including new storage boundary tests | 124, including 9 new storage tests |
| Full coordinator rehearsals | 27 windows: 9/9 at each requested capacity/placement |
| Native controller / mailbox | 3,369 / 15 |
| Fresh miniature-model cases | 79 |
| Real-model cases | 6, with 48 token + 2,304 layer matches |
| Draft capture | 6 arms, 378 valid fixture matches |
| Real cross-placement checks | 3 pairs, 17 semantic buffers; 11 harness tests |
| Seal-binding / blocked-launch admission | 45 / 88 |

The six real-model cases took 8,940.08 seconds; the measured aggregate anonymous
memory peak was 7,942,639,616 bytes against a 9,000,000,000-byte guard. These are
CPU correctness checks, not a model speed result. The runner stayed serial,
with `nice -n 19 ionice -c 3`, `OMP_NUM_THREADS=2`, `python3 -B`, and at most
two compile jobs. It performed no device discovery, device execution or sudo.

| Final identity | SHA256 |
|---|---|
| `build-receipt.json` | `f2ceb7902d2246728dd3a365350beeed2e4eb4fc587b695141ffc7dbbd696db4` |
| `cpu-tests.json` | `108897646f769bd7148ed08965f25b166830a9ced2222077f0ecaa79eab1f3aa` |
| `window-seal-binding.json` | `10eb22c7515c8565fd10f46543c9b6dfaa769e2e2e729c5681e1f530c711982f` |
| Unchanged device runtime | `50381aa1220a6c6e30a597e3c0fa72d93a97453cacd96fdd833d925ac703943e` |

All 41 compiled artifact hashes, including all five device artifacts, are
unchanged. The `artifacts_sha256` map therefore stays unchanged: it describes
compiled files, not host Python sources. The source bindings, build receipt
and window identity change, so old partial chains cannot qualify the new seal.
The [final verification](evidence/storage-admission-fix/qualification-summary.json)
also rehashed all 123 protected incident/fault/device-window files and verified
the archive members and each retained rehearsal window receipt. All matched.

## What worked

The rehearsal now uses the same full-scale projections as device admission at
the window, fixture stage, fixture child, suite RESET and request boundaries.
No 64 MB substitution remains. All three unchanged nine-window coordinator
chains passed: 4096/dr0, 4096/dr1 and 32768/dr0. Suites use twelve miniature
prompts and reserve all thirteen requests including warm-up. The
[audit table](ADMISSION-AUDIT.md#complete-coordinator-cpu-rehearsal-exact-admission-receipts)
records each of the 27 projections, measured build sizes and effective caps.
The lowest observed cap was 13,561,929,199 bytes.

The audit also corrected context-dependent state storage for KD and suites,
and retained-step storage for WS128x. The old 550 MB state allowance omitted
growth of thirteen full-precision caches. The shared projection now adds
`13 * 2368 * (context - 256)` bytes and charges layer output plus checker
hardlinks. KD reserves the three captures that coexist during comparison.
No KV precision or retained quality gate was reduced.

The [complete admission audit](ADMISSION-AUDIT.md) covers every consumer and
budget constant, 63 window/context combinations, twenty packet44 receipts and
all six merged memory plans. The unchanged 97 GiB MemAvailable threshold has
at least 13,774,577,010 bytes of planned margin after the host table and
pinned/IPC allowances. Numerical inventories and source hashes are in the
[machine-readable audit](evidence/storage-admission-fix/admission-audit.json),
bound by the wrapper gate and final seal.

## What failed or remains uncertain

The old cap is reproduced by an admission regression that refuses before
host inspection or subprocess launch. Initial CPU wrapper attempts exposed a
mock signature mismatch and a temporary syntax error; their logs are retained
as `wrapper-first.log` and `wrapper-second.log` in the evidence directory.
Neither produced accepted qualification evidence.

The projection was refined while the first fixture matrix was running. Those
twelve intermediate rows were preserved together with the twelve final rows
in `intermediate-fixture-matrices.json`; the current gate contains only the
twelve fresh rows matching the final source identity. No intermediate result
is used by the seal. Running the final source campaign reproduces that final
matrix directly.

Packet44's admitted-write field is a reservation, not measured I/O. Retained
file sizes and authenticated state/archive sizes provide the comparison;
aggregate build deltas are not relabeled as isolated window writes. Packet44
32768 W2m raw states were previously removed, so its retained tree cannot
establish the original full peak. This limitation is explicit in the audit.

CPU rehearsal proves admission and orchestration, not device residency,
timing or execution. Disk changes by other processes can still cause a real
admission refusal. Existing device chains remain untouched and cannot qualify
the new host seal; the coordinator must start fresh chains.

## Evidence and patches

- [Storage policy](storage.py), [window admission](window.py), and
  [suite producers](suite.py).
- [Admission regression tests](test_admission_budget.py),
  [audit generator](admission_audit.py), and
  [coordinator CPU gate](coordinator_cpu_gate.py).
- [Serial campaign](storage_admission_campaign.py) and
  [final independent verification](storage_admission_summary.py).
- [Evidence directory](evidence/storage-admission-fix/), including original
  seals, protected-file hashes, stage logs and the exact retained chain archive.
- [CPU reproduction instructions](CPU-REPRO.md) and
  [large-artifact retention/restoration](ARTIFACT-RETENTION.md).

## When to revisit

The coordinator's next device attempt must use the new host seal and fresh
chains under existing host safety rules. Any increase in contexts, default
suite size, retention steps, state format or simultaneous raw snapshots must
update the structural plan and repeat this admission audit. This repair grants
no authority to delete device evidence or lower the free-space floor.
