# Xe2 M=6 down-projection DPAS semantic fix

## Scope

This remained an isolated comparator experiment. It did not edit or rebuild the
protected llama.cpp source tree. The experiment source is
`xe2-verifier/production-comparator-v3.cpp` and the tested binary is outside
Git at:

```text
/mnt/fast-ai/bench-results/qwen27-xe2-verifier/production-comparator-slm-canonical-repack
```

## Root cause

The prior M=6 `17408x5120` result differed from active reordered MMVQ by about
`0.0651`, despite the old global-partial DPAS path and the new SLM path being
bit-identical. A K=32 diagnostic separated packing, integer dot, scale/sum
metadata, and accumulation:

- masked DPAS integer dots matched the host reference exactly;
- production output matched the exact Q4_0/Q8_1 host formula within
  `2.38419e-7`;
- the independently recomputed candidate Q8 integers matched production
  exactly;
- candidate Q8 metadata did not: at full down-projection K, `d` differed by up
  to `7.62939e-6` and the half-precision sum differed by up to `0.00760651`.

Q4_0 production arithmetic subtracts eight times the Q8_1 sum. Recomputing Q8
metadata in a second activation quantizer therefore amplified a tiny reduction
and half-rounding difference. The apparent DPAS error was not a weight-pack or
integer-dot error.

## Smallest passing design

The candidate now consumes the canonical production Q8_1 result and performs a
small device reorder:

1. copy canonical row-major INT8 quants to the DPAS block-major/row-minor SoA;
2. copy the canonical half2 `(d, sum)` values exactly into contiguous DPAS
   metadata;
3. use an offline unsigned Q4 pack and Xe2 `u4 x s8` DPAS;
4. retain joint-N2, K-split-8, and the single-launch SLM reduction.

The unsigned pack stores the original Q4_0 nibble instead of flipping bit 3 for
signed DPAS. This makes the epilogue exactly the production expression
`weight_scale * (unsigned_dot * q8_scale - 8 * q8_sum)` and removes the
signed-dot correction reconstruction.

The timing charges the candidate for both canonical Q8 quantization and the SoA
repack. It is not treating the repack or quantization as free.

## Results

All three stability repetitions passed on GPU3:

| M=6 shape | Max delta vs production | Candidate total speedup |
|---|---:|---:|
| 17408x5120 | `4.57764e-5` | `1.8005x` to `1.9158x` |
| 5120x5120 | `1.52588e-5` | `1.6338x` to `1.6487x` |

The M=6 `5120x17408` check also passed at `1.6751x` total with maximum delta
`1.71661e-5`.

Full stability log:

```text
/mnt/fast-ai/bench-results/qwen27-xe2-verifier/canonical-repack-stability-20260713.log
```

Representative command:

```bash
source /opt/intel/oneapi/setvars.sh --force
ZE_AFFINITY_MASK=3 \
  /mnt/fast-ai/bench-results/qwen27-xe2-verifier/production-comparator-slm-canonical-repack \
  6 17408 5120 50
```

## Negative variants retained in the experiment history

- K-split-16 with separate DPAS half-block contributions did not reduce the
  original delta while using independently recomputed metadata.
- Exact lane-stream accumulation and a five-stage SLM reduction tree also left
  the original delta unchanged, proving accumulation order was not its source.
- After canonical metadata fixed correctness, the exact split-16/two-DPAS/tree
  variant reached only `0.660x` of production total speed. It is rejected.

## Integration guard

Do not integrate a second independent activation quantizer. A runtime kernel
must either consume canonical Q8_1 directly or fuse quantization and DPAS SoA
production in one kernel so both layouts receive the same `(d, sum)` values.
Guard M=6 dispatch by exact shape/pack identity and retain a shadow comparison
before enabling it broadly.
