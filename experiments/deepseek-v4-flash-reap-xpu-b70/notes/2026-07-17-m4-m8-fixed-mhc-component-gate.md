# M=4/M=8 fixed-MHC component gate

Date: 2026-07-17

## Outcome

Fixed M=4 and M=8 MHC post/pre kernels clear the real component gate when the
known-exact M=2 TP collectives remain segmented. On the four-B70 fixed-address
graph worker:

- M=4 improves from `6.944914` to `5.521133 ms/cycle`, saving
  **`1.423781 ms/cycle`** (`1.258x`);
- M=8 improves from `12.350354` to `8.039061 ms/cycle`, saving
  **`4.311293 ms/cycle`** (`1.536x`).

Both controls and candidates pass 16 deterministic changed-row eager schedules,
eager collective exactness, and 70/70 fixed-address graph replays on every
card. Replay positions 28 and 58 have zero mismatches. The M=4 candidate also
repeats independently at `5.515657 ms/cycle`.

This is a major decoder-shell component result, not an endpoint decode record.
The source tensors are honest real M=2 verifier tensors row-tiled to measure
fixed-width execution economics. They do not represent a sequential M=4/M=8
draft trajectory and do not establish acceptance, emitted tokens per cycle, or
real-world throughput. There is therefore no LocalMaxxing submission.

## Implementation and identity

The isolated XPU-kernel worktree adds fixed output operators
`mhc_post_pre_m4_out` and `mhc_post_pre_m8_out` by instantiating the existing
bitwise-exact fixed-M2 template at widths 4 and 8:

- worktree: `/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc`;
- commit: `50646a2bfd3e451d77e150a9f950cc097b40bce9`;
- extension SHA-256:
  `af1760de1b18a8b107ba553352df45abcc396c4556558da07ed71c217ffb8561`;
- oneCCL runtime:
  `/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f`;
- libccl SHA-256:
  `53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9`;
- real corpus:
  `/mnt/fast-ai/deepseek-v4-corpora/mtp1-m2-cycle-20260717T0710Z`.

The reusable runner launches every path in a fresh four-rank process. It
records kernel/runtime hashes and the exact selector identity, tests changed
MHC inputs eagerly, tests collectives eagerly, then captures 87 reductions and
85 MHC consumers for 70 fixed-address replays. Raw paired evidence is:

- M=4:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m4-real-cycle-gate-20260717T123502Z`;
- M=8:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m8-real-cycle-gate-20260717T123355Z`.

## Harness corrections

Three corrections were required before accepting the result:

1. An XPU graph captures the source copies themselves. Mutating host/device
   sources after capture did not produce a valid changed-input graph test.
   Changed-input parity is now tested directly in eager MHC calls, while the
   graph gate tests static fixed-address replay stability.
2. Reusing several graph objects and collective paths in one process exposed
   stale collective state and made path comparisons ambiguous. Every candidate
   and control now runs in its own clean four-rank process.
3. Collective exactness is tested separately before graph capture. The runner
   restores the record's `B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072` selector
   and records it in `identity.txt`.

These were harness problems, not candidate wins. The corrected paired runs
above are the admission evidence.

## Wide-collective blocker

A single BF16 `[4,4096]` all-reduce is corrupt under the current Arc LL ring,
even after restoring the exact 128 KiB routing selector. Every rank reports
427,072 mismatched elements over the 87 reductions with a maximum absolute
difference of `0.5`. Identical input rows also diverge after reduction: rows
0/2 have 146,404 mismatches and rows 1/3 have 146,984. Eager and graph paths
fail identically, including positions 28 and 58. The same failure persisted
with the `twoshots` selector.

This rules out harmless reduction-order drift and points to a oneCCL
count/geometry defect above the proven `[2,4096]` BF16 size. The raw diagnostic
is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m4-real-cycle-gate-20260717T123159Z`.
Its timing is inadmissible. Until the runtime defect is repaired and separately
requalified, wider verifiers must use segmented `[2,4096]` collectives.

## Decision and next gate

Admit the fixed M=4/M=8 MHC operators for guarded integration, retaining the
segmented exact M2 collective sequence. The next experiment must capture or
produce true sequential M=4/M=8 verifier tensors, measure the whole verifier
cycle, and evaluate a frozen predictor on unrevealed realistic prompts. Only
complete wall-cycle throughput with target verification can authorize a
service promotion.

Repairing the wide oneCCL route remains a separate communication lane. It may
unlock more savings, but no wide-path number can enter verifier economics until
the eager and 70-replay exact gates pass on all four cards.
