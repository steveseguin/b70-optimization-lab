# Packet 127: reuse a proven signature digest, keep every inspection

The [budget](2026-10-10-continuation-budget-145.md) finds a narrower opportunity
than another decoder scheduling change. The late 125 trace directly attributes
all 19 long handoffs to recorded maintenance; GC 60 removes the recurring handoff
cycle. Fresh text every fourth chunk still takes longer. Six snapshots spend
about 0.18–0.21 seconds checking live state and 0.15–0.17 seconds reading tensor facts.
Those checks cannot be cached wholesale without missing mutations.

Packet 127 inherits sealed 126, manifest
`fe5ce9e09b7e8c86ac659c20430f85b3c83cb35bf5e8476f740610da82b60aa4`.
It adds one exact candidate: `LTX_SNAPSHOT_DIGEST_CACHE=1`. The default 0 keeps
the parent route-digest path. The existing background accounting and GC 60 are
independent options; their combination with this candidate is the first forecast.
See the [contract](../recovery/20261010-continuation127-stream/CONTRACT.md) and
[future launch reference](../recovery/20261010-continuation127-stream/LAUNCH.md).

## What changes and why it is exact

`candidate_safety.snapshot_routes` already reads all 48 route registrations and
their current per-thread signature keys. It formerly serializes every key with
`repr`, sorts, joins and hashes them again every snapshot. A bounded 48-group
memo now retains the result only for roots recursively proven to contain exact
immutable builtin tuple/str/bytes/int/bool/None objects. Every hit requires
freshly enumerated roots to be the identical strongly held objects and the
identical parent digest callable. Strong references prevent object-id reuse.
Unsupported types, custom mutable hashable objects, tuple subclasses, floats,
new or reordered keys execute the original digest. No tensor values are cached.
Changed signatures still fail the unchanged frozen-inventory gate.

The cache never skips `_state`, route ownership, thread membership, placement,
text guards, phase/identity/fault checks, fresh tensor/storage/shape/dtype/device
facts, free/allocator readings or barriers. It does not change periodic/near-floor
dual walks. Dual snapshots may share this pure memo because an immutable key's
representation cannot change; no admission verdict or mutable observation is
reused. Qualification remains byte gated as before. Lifetime cumulative cache
counters are recorded in receipts; they are not per-chunk durations.

The new option is parsed strictly and has a limited first scope: 145 frames,
two-way20-28/frame/dg0/cone/bo1/pa1, fingerprint/full, legacy auxiliaries,
serial display3 released at samplerA, read-ahead0. Status, launch identity,
receipt/decode/preview server options, verdict and client expectation bind it.
Off 0 leaves parent 126 forms available. No extra XPU allocation or model copy
is introduced; the bounded host cache holds existing immutable key references.

## Budget and expected result

The [CPU mechanism replay](../data/resume-20261008/continuation127-signature-cpu.json)
uses the actual parent digest function with source-shaped immutable keys and
recorded 48-route/four-key census. Raw runtime keys were not logged; this is a
synthetic CPU mechanism test, not a reconstruction of measured snapshot time.
Fifty alternating paired batches of 288 digests save about 0.051 seconds. A
provisional native saving of 0.03–0.07 seconds needs live verification.

The first combined forecast is 5.45–5.70 seconds per 6.0 seconds of new video,
0.908–0.950s/s, central 5.55 seconds/0.925s/s. This range does not reach
0.90s/s; another saving is needed. No measured speed, native exactness or adoption is claimed. Compare
cache 0/cache 1 with identical background/GC 60 settings on two fresh qualified
servers, fixed windows and both parities; retain fresh-text and maintenance
chunks in all speed summaries. The later packet 126 capture includes 127 interior periods: median 5.702 seconds,
and the fixed first 40 periods give 5.722 seconds, matching the coordinator.
All 64 long handoffs overlap recorded GC10 maintenance. Replacing that
handoff gap with 40 ms is only an illustrative schedule calculation; it gives
5.594 seconds before the memo estimate. The revised forecast above includes
uncertainty because GC60 did not improve the earlier whole-window median.
The original earlier forecast is superseded by this measured-parent estimate.

The sampler is already 48 individual whole-block graphs, all 48/chain 1,
192 captured graphs at four signatures per block, 528 replays across 8+3 steps.
The older 75% CPU-dispatch estimate predates these graphs; the later 81.5% block
profile also predates this 145-frame workload. Eager remainder includes signature
and registry dispatch, slot copies, card transfers, sampling and input/output
work. The 20/28 split executes dependent layer groups sequentially; receipts
cannot establish an idle-time saving from balancing them. GEMM roofline claims
need a current profile before attaching a fraction to the145-frame sampler.

A positive decoder cap cannot prevent the first capture because it checks prior
growth, initially zero. The 121-frame first capture reserved ~3.43GB, exceeding
145 legacy's 1.85GiB margin. The display 2 replica leaves only ~2.538GiB beyond
its conservative reserve/screen, also below that old capture. No safe 145
cone-graph cap or cross-card graph route is established. 169 with 124's display
worker after 126 remains a larger separate opportunity, unmeasured as a pair.

## Preparation and validation

All author/build/test work is CPU-only at nice 19, OMP/MKL 2, using
`/home/steve/.venvs/ltx25-baseline/bin/python -B`. The inherited audit harness
refuses render-device opens, live network access and process signals. Tests use
new scratch paths only. No GPU, server, launch, check-only, port 8188, systemd,
existing-run/client-tree write, host-setting change or reboot was performed.
The source assembly preserves every changed 126 predecessor under provenance
and recursively verifies the complete parent chain. No Python caches are allowed.

Final seal and exact test counts are recorded in the
[build receipt](../data/resume-20261008/continuation127-build.json).


Final packet:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-127`.
Manifest `c2564507a9bb88a948bc726d079d8b5a981b3834ad54801be47d0d0c81dc359e`.
Inner plan `554c80518ab28dbdecd502bb942d28850e70bbd24a75b4521be0c5c9d2abcc01`.

Two CPU development seals are retained at the same packet path with suffixes
`-preseal1` and `-preseal2`. Neither was launched. The first exposed a stale
conditioning-guard source pin. Full tests then caught an overly broad scaffold
rename that changed the 121-frame audio dimension from 126 to 127. That value and
its descriptions/fixtures were restored; a direct comparison of all five
geometries to sealed 126 now passes, as do all 3,960 qualification graphs after
namespace normalization. The final plan was regenerated and client inner pins
were refreshed. Development failures are preserved; the complete rerun after these corrections passed 718 of 720 cases.
Its two remaining failures were inherited test fixtures naming parent 125 and
listing the deliberately changed candidate-safety module as unchanged. Those
fixtures now name parent 126 and explicitly check that the original digest
function is byte-for-byte unchanged. The entire affected module passes 16/16.
This validates 720 unique recovery cases without counting rechecks twice;
it is not represented as a single clean 720/720 run. Sealed code did not change.
No numerical change remains.

The complete client run passes **2,807/2,807 checks in 29 suites**, including
362 packet127 contract checks and 86 integration checks. Mocked preflight
passes 10/10. The candidate CPU simulation completes nine qualification and
three streaming chunks with XPU uninitialized. Recursive verification covers
2,151 files; no `__pycache__` or `.pyc` exists in author, packet or test trees.
Repository links and manifest paths pass. The broad literal-pin audit reports
231 pre-existing drifts across two untouched Flash-Next scripts; no packet127
pin drift is present. Full logs, fixture failures and rechecks remain linked
from the build receipt.
