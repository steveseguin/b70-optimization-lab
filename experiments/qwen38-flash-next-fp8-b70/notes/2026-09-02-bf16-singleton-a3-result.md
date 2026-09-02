# Flash-Next BF16 singleton A3 result

Date: 2026-09-02
Status: complete; strong bounded component positive

## Result

The supported XPU oneDNN deterministic attribute completely removed the A2
repeatability failure for the exact real layer-0 attention HyperConnection
down/inject M=1 shape.

Both native replicas produced 100 distinct active/full hashes in 100 complete
256-row sweeps. Every comparison to the first native sweep changed 5--15
production-active BF16 elements (median 9). With
`torch.backends.mkldnn.deterministic=True`, both fresh replicas produced one
identical full and active hash across all 100 sweeps. All four targeted rows and
five recurrent coordinates were also exact across consecutive and ordinal
protocols. Synthetic columns 324:336 remained exactly zero in every arm.

The stabilized row result is not a new observed numerical branch: for each of
rows 78, 148, 205, and 221, its complete active-row hash occurred in both native
replicas under both protocols. Every stabilized recurrent BF16 coordinate was
also an existing native value. The complete deterministic 256-row hash was not
observed among the 200 native aggregates, which is expected when one fixed
combination replaces independently varying row outcomes.

This establishes a strong component-level reliability positive for the exact
provider and shape. It does not authorize a global flag, endpoint change, or
quality/performance claim until the other real BF16 dense families are tested.

## Screening latency

| Replica | Native 256-row median | Deterministic median | Reduction |
|---|---:|---:|---:|
| 1 | 11,769.784 us | 11,409.424 us | 3.061738% |
| 2 | 11,750.310 us | 11,078.626 us | 5.716309% |
| median of replica medians | 11,760.047 us | 11,244.025 us | 4.387925% |

The four focus-row pooled medians were also directionally faster by 1.45% to
17.60%, except row 78 in deterministic replica 2, which was 4.09% slower. The
arm order was fixed and one native row had a latency outlier, so A3 receives no
speed credit. It does show no systematic penalty at this shape.

## Health and evidence

The four sequential child processes completed in about 61 seconds. Peak service
memory was 477.1 MiB and swap use was zero. Input, weight, model, Torch, provider
binary, runtime, and source identities matched. The deterministic setting was
read back before the first GEMM and restored after each candidate process.
Every child/parent postflight passed with four B70s visible, no AER or new kernel
event, clean SMART, about 125 GiB available, and all swap free.

Raw evidence root:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/bf16-singleton-diagnostic-20260902-a3`

- summary SHA-256: `706f70b2565b435798bbcdc78c410b75fc331b03090f5ae12d5496f30d83e049`;
- native replicas: `f152fc2c2850344b6ee3cb91288279f227125d7d72f9916c7eca9acb4f2aa363`,
  `80aac8c298c3e1aa46296fa5e19f695910b26e40d7f9149620d3b1eb130bb3bd`;
- deterministic replicas:
  `707fe32e99a7764012403022babbc54c9024acd01185f443d3784299b46b96ac`,
  `e489acf9cf43d0fdddabd8e360f3a00ff678dcd6d605e57577d5f68e3d8e63eb`;
- service log: `139f35481aa2ff173abb824dcd8cc6c21f22dfd2ec025a3a414458790be99fb1`.

Independent post-run review passed the raw identities, recomputed stability,
health, targeted-row membership, and latency arithmetic.

## Next step

Freeze A4a as a no-server, one-B70 M=1 census over 14 real BF16 dense families
and two sentinels each. Use two native and two deterministic fresh processes per
cell for trustworthy parity and timing (112 arms), load only one weight at a
time, and weight family latency by the real 532 calls per target decode step.
Promotion requires deterministic exactness within and across processes for
every cell, an existing native outcome where native varies, exact identities,
and a preregistered non-regressive multiplicity-weighted cost. A4a can authorize
only a later endpoint candidate.
