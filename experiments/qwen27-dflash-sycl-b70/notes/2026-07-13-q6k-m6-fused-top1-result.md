# Q6_K M=6 fused top-1 microbenchmark result

Date: 2026-07-13

## Outcome

An experiment-only SYCL kernel crossed the pre-integration latency gate for the
real DFlash M=6 LM-head shape (`K=5120`, `N=248320`) on B70 GPU 2. It fuses the
five useful Q6_K x Q8 projection rows (rows 1 through 5) with top-1 reduction and
does not materialize the five full logit rows.

Across three deterministic activation tensors, all 15 selected token IDs and
their logits exactly matched the independent reference path. Median candidate
boundaries were `2.47864 ms`, `2.48261 ms`, and `2.45417 ms`; all three pass the
`<2.5 ms` candidate boundary gate. The matching reference boundaries were
`2.65563 ms`, `2.63167 ms`, and `2.55364 ms`.

This is a microbenchmark win, not an end-to-end throughput claim. The reference
implements the same Q6_K decode, Q8 activation quantization, accumulation order,
full-logit materialization, and top-1 semantics over the real tensor. It does
not call a protected llama.cpp production-kernel export because no Q6_K M=6
benchmark export exists. Production integration therefore still requires a
separate comparator and realistic-suite gate.

## Why the first versions failed

The first expanded-weight implementation used eight subgroups per workgroup and
scalar eight-byte dot loops. It was exact but took `2.92698 ms`, so it missed
the boundary and achieved only `1.11698x` against its reference.

Moving back to the runtime's native reordered Q6_K representation was worse:
on-kernel bit unpacking took `4.94 ms` initially and `3.83-3.87 ms` after
hoisting unpack work and using packed four-byte dots. The smaller 1.043 GB
representation saved memory traffic on paper but exposed enough integer unpack
and addressing work to lose badly on BMG.

The passing version instead:

- expands Q6_K offline into signed int8 quants, int8 16-value subscales, and
  fp16 256-value superblock scales;
- uses 32 subgroups per workgroup, matching the production MMVQ launch shape;
- loads each eight-weight slice as two 32-bit words;
- hoists both weight loads outside the five-row loop;
- computes packed four-byte integer dots;
- skips DFlash row 0, which is not sampled at `p_min=0`;
- performs a local top-1 over 32 vocabulary rows and writes only partial maxima.

The offline representation is `1,355,847,680` bytes versus `1,042,944,000`
bytes for raw Q6_K: about 313 MB extra. This is a deliberate speed-for-memory
trade and should be generated once, cached on disk or host RAM, and loaded
directly rather than rebuilt for every process. A production implementation
should replace the runtime LM-head allocation with the packed artifact where
possible, not keep both copies resident.

## Why it matters

The measured production DFlash draft timeline put the M=6 Q6_K LM head at about
`3.18 ms`, the largest single logical operation in the roughly `10.11 ms` draft
queue. This candidate demonstrates that exact DFlash top-1 semantics can fit
below `2.5 ms` at the true vocabulary size while eliminating five 248,320-float
logit writes plus the separate top-1 scans. The likely end-to-end saving is
bounded by integration and queue effects; the microbenchmark alone does not
prove a 0.7 ms cycle win.

## Artifacts

- Source: `experiments/qwen27-dflash-sycl-b70/xe2-verifier/q6k-m6-top1.cpp`
- Build helper: `experiments/qwen27-dflash-sycl-b70/xe2-verifier/build-q6k-m6-top1.sh`
- Complete retained result: `data/qwen27-q6k-m6-top1-gpu2-20260713T125334Z.txt`
- AOT binary: `/mnt/fast-ai/bench-results/qwen27-q6k-m6-top1/q6k-m6-top1`
- Model cache identity: `20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a`
- llama.cpp source HEAD at test time: `e3546c7948e3af463d0b401e6421d5a4c2faf565`
- Compiler: Intel oneAPI DPC++ 2026.0.0, AOT target `bmg-g31`

## Integration gate

Do not edit or promote the protected runtime from this result alone. The next
step is an experiment-only production comparator that consumes captured DFlash
M=6 activations, checks row 1 through 5 token IDs against the real runtime path,
and measures both boundaries under the same queue conditions. Integrate only
if that comparator remains exact and either stays below `2.5 ms` or beats the
real production boundary by at least `1.25x`. Then run the fixed realistic cold
suite and report draft queue time, acceptance, and end-to-end tok/s separately.
