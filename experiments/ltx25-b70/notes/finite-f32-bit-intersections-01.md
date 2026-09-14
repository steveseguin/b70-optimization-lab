# Exact finite-check acceleration — provisional CPU result

The continuation byte-verification path spent time testing every float sample
in Python. This change replaces that loop with exact integer bit intersections,
while retaining every validation gate and leaving all sample bytes untouched.
It is an optimization of the new CPU verification path, **not a model-generation
speed result**. The current kernel fault and halt on GPU requests remain in force.

## Change and proof

[finite_f32_bits.py](../scripts/finite_f32_bits.py) reads at most65536 bytes per
block, interprets those original bytes as one unsigned little-endian integer,
and applies:

```python
bits &= bits >> 4
bits &= bits >> 2
bits &= bits >> 1
hits = bits & EXPONENT_STARTS
```

After the first intersection, bit `i` represents original bits `i,i+4`; after
the second, `i,i+2,i+4,i+6`; after the third, all eight original bits `i..i+7`.
The constant mask selects bit23 of every32-bit word. A selected bit therefore
survives exactly when that sample's exponent bits23..30 are all ones, the
infinity/NaN condition. Neither the sign bit31 nor mantissa bits0..22 nor an
adjacent word can affect it. An independent source/math review confirmed this
argument and the alignment/tail requirements.

The first masked set bit identifies the same invalid sample as the scalar
loop, including block offsets. Complete aligned short blocks safely use the
same full mask. Incomplete samples retain a `struct.error`; noncontiguous
buffers are rejected. Signed zeros, subnormals, extreme finite values and NaN
payloads are never converted to floating-point numbers. Allocation/read errors
propagate; they cannot imply successful finite verification.

Both [anchor I/O](../scripts/continuation_anchor_io.py) and
[four-tensor delivery verification](../scripts/continuation_delivery.py) use
the helper. Their existing rejection messages and anchor sample index remain.
The graph envelope now hashes the new dependency, and the stream coordinator's
binder pin is updated. No live or prepared runtime packet is modified.

The [exact patch](../patches/finite-f32-bit-intersections-01.patch) applies to
the four preserved parent sources from commit `4807ca934` and adds the helper.
[Parent hashes/source copies](../data/finite-f32-candidate-01/parent.json) and
[patch-application verification](../data/finite-f32-candidate-01/patch-verification.json)
preserve the complete tested delta. Older receipts remain historical under
their old hashes; they are not silently relabeled as tests of these new bytes.

## Correctness evidence

[65 checks passed](../data/finite-f32-checks-01.json), with a
[complete log](../data/finite-f32-checks-01.log). These comprise10 direct bit-rule
tests and the existing13 anchor-reader,15 delivery,12 provider and15 coordinator
checks. Coverage includes all finite exponent values with both signs and
mantissa boundaries, infinities and individual NaN payload bits, each missing
exponent bit, adjacent-word boundaries, integer-limb alignments, multiple
64KiB blocks, first-invalid indices, random bit patterns, typed contiguous
buffers, malformed tails and bounded integer input size.

The paired measurement also ran both scalar and candidate full verification
on the original boat, marble and bird captures. Every four-output hash matched
the tracked originals, and each complete candidate verification receipt equaled
its scalar counterpart. This checks actual stored samples as well as artificial
bit patterns. No new inference, native Torch execution or media write occurred.

## Bounded measurement

The [measurement script](../scripts/measure-finite-f32-candidate.py) extracts
the exact former scalar function from the preserved, hash-checked source. It
uses scalar/candidate/candidate/scalar order: three groups for one actual frame,
and one group for each of the three actual capture files. Each arm has six
observations per row below. Full-capture verification includes all four tensors,
file reads, hashes and finite checks. All24 recorded operations succeeded.

| CPU operation | Scalar median | Bit-intersection median |
| --- | ---: | ---: |
| One786432-byte frame's finite check | 11.04 ms | 0.85 ms |
| Full four-tensor capture verification | 304.38 ms | 44.04 ms |

These are wall-time medians; process-CPU medians were nearly identical.
The observed full-verification reduction is approximately260 ms, or6.9x for
that operation. The [raw rows and identities](../data/finite-f32-measurement-01.json)
retain every timing, source hash, boot ID and active fault-latch hash.

**The host was faulted throughout this CPU observation.** The measurement used
no GPU, Torch import, subprocess, affinity setting, host-setting change, server
action or automatic retry. Its timings are provisional and require healthy-host
confirmation. They cannot establish full-clip throughput, p95 latency or the
faster-than24-new-frames/sec objective. The measured operation is part of the
new verifier; subtracting260 ms from an older generation benchmark would mix
different timing scopes.

## Next action

Keep the exact helper with the inactive continuation implementation, qualify
the complete native/client path after host recovery, and measure end-to-end
latency separately. A source review of `compare-clip.py` also confirms that the
current legacy comparison client imports Torch and loads both full archives.
A separately qualified streaming exact comparator could reduce those client
allocations while preserving its execution-identity and original-output gates.
That remains a candidate, not an explanation or fix for the recorded kernel
fault. Model compilation and the actual short-chain generation/replay tests
remain blocked by host health.
