# DeepSeek V4 K160 combined MTP1 record

Date: 2026-07-15

## Outcome

The current nonspeculative base, wide-epoch oneCCL repair, and proven exact
MTP1 verifier compose into a new four-B70 single-session record:

- strict headline: **55.703731 tok/s**, p10 52.205941;
- independent matching support: **55.668081 tok/s**, p10 52.202551;
- previous MTP1 record: 55.524496 tok/s;
- sustained exact qualification: 70/70 captures, including 50 after both
  strict suites and former rollover failure positions 28 and 58;
- every realistic and exact request reports `cached_tokens=0`;
- LocalMaxxing: `cmrmoyenp1no3mj01fz2gjzo6` (`APPROVED`).

Evidence is under
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-direct-moe-wideepoch-candidate-20260715T2315Z`.

## Composition and why the gain is small

No source merge was needed. The batched row-exact compressor commit is already
an ancestor of vLLM `a681dbb2b`; the direct routed-MoE record is already in the
XPU-kernel tree; and wide-epoch oneCCL `48fda4f0e` descends from the prior MTP
runtime. The combined service enables exact M=1 router normalization/direct
routed MoE, row-exact batched M=2 compressors, and selective W8A16 through M=2.

The direct routed-MoE path is deliberately guarded to M=1. The M=2 target
verifier therefore retains its proven generic routed-MoE path; only the single
attached MTP draft layer receives the direct-M1 saving. The expected speed
change was noise-scale, and the measured improvement is correspondingly small
but repeatable. The important carry-forward is a unified, rollover-safe base
for future MTP work, not a claim that the full 43-layer target gained the
nonspeculative direct-MoE saving.

## Identity and qualification

- vLLM: `a681dbb2b4b19c2c5a964817095b5f8c1f27ff48`;
- XPU source HEAD: `46bdf3437918e6040f593db8ee7f98f1e8e4a641`, whose
  tree is the record source `6522849b02894273b1e779b3c115527b5cdf3756`
  after a preserved prefetch experiment/revert pair;
- exact loaded XPU binary SHA-256:
  `3d07d85ce15a418d4355b0eaf5686c9cf6c7af92c9d5bf15b3884e9758161bf2`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- selected libccl SHA-256:
  `53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9`.

All four worker maps contain the selected wide-epoch libccl. The benchmark is
the fixed 12-prompt realistic suite, one cold response per prompt, target-
verified MTP1, no prefix/history/response reuse, and tokens 1-100 after TTFT.
A separate 10-prompt quality-suite screen reached 57.56 tok/s but two prompts
ended before 100 tokens; it is retained as invalid/incomplete diagnostic
evidence and is not part of the record claim.

## Next action

Keep this service live for the next bounded candidate. Direct-M1 tuning cannot
materially move MTP1 because the 43-layer target verifies at M=2. The next
credible implementation pool is exact M=2 shared-expert activation/quant
fusion or a new small-M target-verifier kernel that first proves at least 0.50
ms per speculative cycle on real shapes.
