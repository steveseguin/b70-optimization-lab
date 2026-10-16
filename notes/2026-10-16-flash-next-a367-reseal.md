# Flash-Next A367 reseal — October 16, 2026

Coordinator-approved preparation items 1–4 are applied. The zero-generation
calibration is resealed. No calibration, device window, health probe or service
change ran. Model/stage/source bytes, MTP1, graph and compute selectors stay
unchanged. CPU work used nice 19, ionice idle, cores 4–15,20–31, at most two jobs
and Python `-B`. Protected old source, rescue archive and repaired-by-owner RAID
were not accessed. Root stayed near 24.09 GB free; this task's small artifacts
are far below the 2 GB growth budget. No binaries or models were built/copied.

## Decisions and evidence

- [Dependency decisions](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/RESEAL-REVIEW.md): the corrected memory note is repinned as evidence without changing floors. Explicit calibration dependencies exclude unused fixture references. The original two fixture pins remain frozen and continue to block extraction; the changed sigmoid reference is not an A367 oracle.
- [Environment audit](../data/2026-10-16-flash-next-a367-reseal/environment-audit.json): 2,305 source files, 18 stage files and two collective hashes pass. The retained historical receipt comparison remains `passed=false`; a separately pinned reconciliation passes all 144 files against publisher identity and the preparation USB receipt. No new full payload read occurred here.
- [Seal audit](../data/2026-10-16-flash-next-a367-reseal/seal-audit.json): **zero active mismatches**, 16 calibration seal members, nine shared-driver seal members, 93 calibration dependency pins (including all 75 patch/bundle members). Two dormant fixture mismatches are retained separately, not approved or counted as calibration inputs.
- [Static loader/import audit](../data/2026-10-16-flash-next-a367-reseal/loader-audit.json): 51 ELF objects / 672 context edges; required selected-path dependencies resolve, clean source precedence passes. Optional disabled sleep allocator's `.9` library is unavailable on this search path; the pinned source catches its import failure and never instantiates it. No library substitution, loader execution, ABI or device success claim. [Audit script](../data/2026-10-16-flash-next-a367-reseal/static-loader-audit.py).
- [CPU test receipt](../data/2026-10-16-flash-next-a367-reseal/cpu-tests.json): **132 tests pass**, zero failures/errors/skips — calibration 58, shared mocked driver 59, payload helper six, frozen tree verifier nine. These test controls and CPU mocks, not native quality. The seven runbook shell blocks pass `bash -n`; its two Python heredocs compile without execution.
- [Launch plan](../data/2026-10-16-flash-next-a367-reseal/launch-plan.json) contains an intentionally uncreated CPU-plan output name. Tests compare every launch argument and literal compute export against the frozen A367 transform. No model request is made.

## Final hashes

- `driver_preregistration`: `db83805e9a2b4099a0f6bdb005d0d08310009d474ce62546356f3c505e9f65b9`
- `driver_seal`: `d97d1ee16b76743ff1c818a1a5dc2d34cb25d7883077aa5ab25eab303f84aa93`
- `calibration_preregistration`: `0c1c5cbeda393c2d6d1f1699699d936793cd4c3449dff6eedbdfa5b60ce66c0a`
- `calibration_seal`: `69f22335288682a82a9df0c0ef6ea718cfa08cb3da6cd77b7144251cb1cb7934`

## Pending owner sentence

The proposed 114,000,000 KiB (108.72 GiB) start floor sits below the owner's
roughly 110 GiB available observation. It is a proposed numeric exception,
**not** a measured safe threshold. The 120,000,000 KiB default and 12,000,000 KiB
live reserve remain unchanged. The checked-in
[pending object](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/owner-approval.pending.json)
has `approved=false`. Only the OWNER may approve the exact post-reseal text:

> I authorize one A367 calibrate-load measurement on steve-b70s with a calibration-only MemAvailable start floor of 114000000 KiB, a 0.5-second watchdog and the 12000000 KiB live reserve, under preregistration SHA256 0c1c5cbeda393c2d6d1f1699699d936793cd4c3449dff6eedbdfa5b60ce66c0a and seal SHA256 69f22335288682a82a9df0c0ef6ea718cfa08cb3da6cd77b7144251cb1cb7934. This accepts the unmatched loading-memory risk, does not lower the packet-4 fixture floor, and does not resolve the halt or authorize another launch.

No owner authorization was created. Every old sentence/window is stale. Any
later change to the preregistration/seal requires newly hash-bound approval.

## Remaining actions

Follow the [exact future launch runbook](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/LAUNCH-RUNBOOK.md).
The owner repairs/admit RAID output storage and signs the exact exception.
The coordinator then provides fresh storage admission (60 GiB reserve plus
10 GiB planned writes), byte audit, USB payload re-hash at most one hour old,
four-card health at most ten minutes old, current boot/halt/ownership/firmware
facts and the hash-bound owner-window. The durable unit runs once and keeps
its post-exit kernel watch for 305 seconds; no automatic follow-on is allowed.
These are owner actions and fresh launch gates, not missing calibration code.
Fixture oracle review belongs to a different future window and is not waived.

## Repeat the CPU checks

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate -p test_calibrate.py -v
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=experiments/own-xpu-runtime/stage1/packet4-prep:experiments/own-xpu-runtime/stage1/packet4-prep/driver /home/steve/.venvs/vllm-xpu/bin/python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage1/packet4-prep/driver -p test_driver.py -v
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B -m unittest discover -s scripts -p 'test_verify*flash*py' -v
```
