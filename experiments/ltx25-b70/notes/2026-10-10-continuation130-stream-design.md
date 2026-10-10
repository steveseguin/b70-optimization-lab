# Packet130: release unused allocator reservation before display admission

The 169-frame display replica refused during packet127 qualification with
7.884018 GiB free on xpu:2. Its stated6.5 GiB transient plus2 GiB floor requires
8.5 GiB, leaving0.615982 GiB short. Source inspection also finds an unchanged
0.75 GiB screening requirement: the true admission target is9.25 GiB and the
shortfall is **1.365982 GiB**. The0.5 GiB near-floor band is a separate safety
trigger; adding it gives1.115982 GiB. Recovering only0.8 GiB cannot pass.

The [residency inventory](2026-10-10-xpu2-residency-169.md) binds the saved run,
model-header census, placement source and historical replica records. Card2
holds the first text-encoder shard, not a sampler shard. Its last adjacent
snapshot has2.993282 GiB reserved but unused; other saved refusal snapshots
span2.400–3.856 GiB. Some of that can be trapped in active allocator segments
or private pools, so it is an upper bound, not proven recoverable memory.

## Selected exact remedy

Parent129 is pinned to manifest
`42e6a7452e11873f33c78a953105754605121f2a96dfca1954b1d55966a4886c`.
The default `LTX_DISPLAY_ALLOCATOR_RELEASE=off` preserves its execution and
budget. New mode `before-admission` checks free bytes, makes at most one
`torch.xpu.empty_cache()` call if they are insufficient, then feeds a fresh
physical-free reading to the original budget. The same path covers before/after
replica installation and each decode. It never credits reserved-byte deltas.
The mode is limited to the fixed169 parallel-display2 legacy geometry.

The installed PyTorch Python API has no device parameter. This is explicitly a
**process-wide XPU allocator release**, potentially synchronizing/releasing
unused blocks on other cards too. There is no claim that a device context
restricts it to2. Before/after four-card allocated/reserved/peak/free readings,
phase, duration and physical delta are saved with admission evidence. These sequential counters are observed net changes during concurrent work, not an isolated measurement of the release. Any
refusal includes that evidence in its existing latch/failure diagnostic.

No live tensor is moved, freed, quantized or recomputed; decoder arithmetic,
seed, precision and output normalization are unchanged. The packet does not
collect Python objects, drop host caches, destroy graphs, reset peaks or retry
decoding. Replica facts are rechecked, and every inherited native byte gate
remains mandatory. Early dead-tensor release needs a separate lifetime audit;
naive temporal halves are inexact because of temporal dependencies and changed
kernel shapes. Moving text layers does not fit both cards' screening margins.

## Admission, identity and expectations

The6.5 GiB transient reserve,2 GiB floor and0.75 GiB screen are untouched.
A1.5 GiB physical reclaim would leave0.884018 GiB above reserve+floor;
other-card saved margins remain1.231304 /1.772644 /1.554504 GiB on0/1/3.
These values do not prove a native130 peak or a guaranteed allocator release.
Verified freed memory during this CPU-only preparation is **0 GiB** because
no allocator operation was executed on a device. The candidate pool is large
enough to justify the gated qualification; that qualification remains open.

The new mode is bound through the launch environment, run suffix,
server_options, status, receipts, decode records, qualification verdict and
client expectations. Enabled-mode decode and qualification validation requires the release audit record and checks its phase, threshold, physical-free accounting and the unchanged screening margin. The inner plan_sha256 is pinned everywhere; the plan
JSON file's envelope hash is never used as a client plan identity. Recursive
source closure preserves129 and every predecessor. Packet129's atomic evidence
publication and unchanged strict reader guard remain in force.

[Future launch](../recovery/20261010-continuation130-stream/LAUNCH.md) uses169,
frame/cone/dg0/bo1/pa1, two-way20-28, fingerprint/full snapshots, read-ahead0,
legacy auxiliaries, parallel eager display2, GC10, digest0, idle maintenance,
background storage and16 GiB run allowance. Both wrappers call pinned
bin/python -B. Client folder defaults to s130-live01. No wrapper was executed.

Forecast:124's6.20–6.65 s per7 s new video (0.886–0.950 s/s), plus unknown
allocator-release overhead. A conservative contention case is6.65–7.20 s.
There is no new measured throughput claim or completed169 stream in130.

## CPU validation and unresolved native work

The [build receipt](../data/resume-20261008/continuation130-build.json) records
exact final counts and log/source hashes. The [stdlib census verifier](../data/resume-20261008/continuation130-verify-residency.py) rehashes all36 inputs (five model headers only), rechecks40 snapshots, and recomputes the shortfall and reclaim scenarios. Recovery tests include the actual
admission helper with fake allocator readings: defaultoff, every scope field,
no-release success, insufficient release, physical-versus-reserved distinction,
exact screening boundary, install-weight charge, failed release, unchanged
facts and bounded call count. Existing tiny native CPU decoder tests cover
copy and exact postprocessing. Full runtime cases use real qualification and
receipt paths with fake device/decoder components; they are not native proof.
All historical client suites, new client expectations, all-pins and mocked
preflight checks are retained. Tests block device opens, signals and live
sockets; fake HTTP uses loopback test ports only, never8188.

Native gates still needed: actual reclaim>=the unchanged admission deficit,
nine full-image comparisons and three chains, fresh-text interaction,
reservation plateau, per-card floors and matched speed on two fresh qualified
servers. Those are coordinator operations. Preparation performed no GPU work,
server/model launch/check-only, xpu-smi, systemd/unit or port8188 operation,
process signal, host setting change, existing-run write or ltx-stream write.
Python ran nice19, OMP/MKL2 and pinned bin/python -B. Own test scratch is
removed after validation and sealed trees must contain zero Python caches.

## Sealed identity and completed checks

Manifest: `14aa145e6ad814eb600ceca75286742a08898ae5bb704d270dfada69420980ed`.
INNER plan: `0d24d0ff5446de8445d9774dd20057aaa284e34c2bedba0baba186b3b8af82ba`.
Recursive verification covers 2,219 bound files and 2,221 total files, with
zero Python caches and all authored components equal to the sealed copies.

Client validation passes **4,419/4,419 checks in 35 suites**: 3,850 historical
checks, 465 new contract checks and 104 new integration checks. This includes
all **24 inner-plan pin assertions**. Mocked preflight passes **10/10**.
The two final CPU runtime cases each complete nine qualification decodes and
two stream decodes; all eleven output-tensor and last-frame hashes agree
between off and enabled modes. XPU was never initialized.

The enabled fake-client case also qualifies and streams three chunks, binding
allocator evidence through its receipt, decode and preview checks. All 35
owned client scratch roots under `/tmp` are verified deleted. The census
verifier passes all 36 source hashes, five headers and 40 phase snapshots.

Development recovery validation found three fixture failures in 823 tests:
two copied fixtures still named parent128, and one deployed-checker fixture
omitted the new helper. Those fixtures were corrected before final validation.
The initial runtime cases were also rerun after the final audit-evidence gate
and plan were frozen; both final cases passed. Development logs are retained.

Final full recovery validation passes **842/842 tests in 1,013.481 seconds**
(796 inherited plus 22 allocator mechanism, 19 evidence validation and five
option-scope tests). Recovery scratch is removed. Both new wrappers pass shell
syntax checks, and all 99 authored/client Python files parse with zero caches.

Repository integrity: 215 general documents plus four focused documents have
zero broken links; 6,148 paths in 51 manifests have zero missing targets.
The broad literal-pin audit reports 87 matches, 231 drifts and zero absent
targets, the same existing Flash-Next frozen-client drifts recorded for129.
They are preserved as unrelated audit findings, not reported as a passing
broad pin audit or changed to make this packet appear clean.
