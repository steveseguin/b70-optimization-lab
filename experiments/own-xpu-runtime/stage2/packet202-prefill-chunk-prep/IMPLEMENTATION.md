# Packet202 synthetic two-row branch-core proof

## Question and identity

Can the current layer0 Q6 projections share a weight read across two known
prompt rows while ordered convolution/GDN state remains byte-exact? This is a
HOST_ONLY synthetic proof of **qkv/z projections plus convolution and GDN**, not
full layer0 or the complete attention branch. Alpha/beta, bias, convolution
weights and initial BF16 state are synthetic inputs; their upstream projections,
HC, gated normalization, output projection, stream injection, FFN, QSA, cache
maintenance and runtime ownership are outside this executable.

## Outcome

The [differential receipt](evidence/host-differential.json) reports five successful
cases and ten full-byte comparisons each: qkv, z, convolution output, row0/final
convolution history, GDN output, row0/final recurrent state, plus independent
round2 output/state. Cases use distinct, identical and swapped rows, BF16
rounding-sensitive inputs, and a larger nonzero initial state. Every active case
changes state and produces distinct recurrent row outputs. Treating row1 as an
independent sequence deliberately produces a different state in all five cases.

This establishes CPU arithmetic and scheduling agreement for these synthetic
fixtures. It measures no device speed, cache reuse or kernel savings. The new
pair function shares each decoded weight between two independent ordered
accumulators; it is not a prepared SYCL/device kernel.

## What worked

The [production binding](production-binding.json) matches the actual p201
resident tensor census: Q6_K, K2560, variant6 `expanded_sg32_v1`, split1, SG32;
10240 qkv and6144 z output rows. Each expanded row is3380B:2560 signed codes,
640B scales and180B original scale metadata. Stored totals34,611,200B and
20,766,720B match the census. The fixture generates valid synthetic packed
Q6 rows, calls the pinned expansion transform, and hashes both packed and
resident images. It never reads model shards.

Serial dense evaluation calls pinned `p33::dense_lane` and the original tree
independently of the new pair function. Serial convolution uses pinned `ng::cpu`;
the two-row channel schedule preserves every accumulation and BF16 write and
records the row0 history. Recurrence uses the selected `rows4-shared` **production
CPU mirror**, extracted byte-for-byte except for an optional row0 snapshot
store, with one shared BF16 state. The serial path runs M1 then M1; the candidate
runs M2. A separate pinned `round2::gdn_host` reference also agrees. CPU mirror
agreement does not establish the selected SYCL branch's code generation.

The planner excludes the final prompt token, supports width1 reference and
width2, and splits at32-position extent boundaries. Its standalone Region gate
rejects short, null, overflow and overlapping writable spans while allowing
shared readonly/adjacent spans. This validates the **planner's range policy**;
it is not integrated into the production allocation arena or runtime bindings.
Inactive/sticky-error/invalid-position fixtures retain output/state bytes;
invalid position sets sticky error, and all retain position/active controls.

## What failed or remains uncertain

No numerical or compiler failure occurred in these first two build attempts.
The first successful attempt reported state-change/control booleans; review
strengthened the executable to require non-vacuity and exact preserved control
values. Both attempt directories retain exact code and raw differential output.
Historical p151 wrappers reference pruned build paths, so they were not imported
as a runnable dependency. The new pair preserves the current frozen p33 lane
arithmetic instead. Its production mirror extraction and source pins are explicit.

Remaining gates include full gated normalization/output/injection, causal QSA
and PLE, actual prepared device argument binding, complete workspace admission,
cache cadence, all-layer state/outputs and eventual device qualification.
No generic full-runtime HOST_ONLY fallback is being presented as those gates.

## Evidence and reproduction

From the repository root:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet202-prefill-chunk-prep/build_engine.py --run
```

This compiles only the new synthetic CPU executable with `/usr/bin/g++`,
`OWN_RT_HOST_ONLY`, no fast math and contraction disabled. It uses the existing
compiler-turn lock, helper affinity, nice19 and a4GiB address-space ceiling.
No device runtime is linked or started. The checked-in authority bridge has
repository-relative top-level includes; inherited sealed headers retain their
historical absolute paths, so reproduction currently requires the documented
`/home/steve/llm-optimizations` workspace rather than claiming portability.

[Build receipt](evidence/build.json) records command, compiler, binary SHA and
compiler-discovered repository source dependencies. Pins are rechecked after
compilation and numerical execution; inherited dependencies must match p201.
Every attempt preserves its source snapshot, compile log and raw differential
stdout/stderr under `evidence/build-*`. `build/` is ignored. Repeat qualification
uses the tests agent's `tests/test_chunk_plan.py`, which validates the current
binary/receipt/source closure and invokes only planner/control modes; it does
not repeat the costly numerical cases merely to recheck their receipt.

## When to revisit

Complete the missing GDN branch operations in a separate additive packet after
independent review of this proof. Keep packet202 immutable as its regression
baseline. Only after wider exact CPU coverage and separately reviewed resource
and selected-device-kernel gates should a new device experiment be considered.
