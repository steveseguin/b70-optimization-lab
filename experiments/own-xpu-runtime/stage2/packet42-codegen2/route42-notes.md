# Production route: five launches to four

Prepared, compiled and CPU-gated; no device executed and no speed claimed.
This is the actual packet29 `packet18::submit_parallel` specialised route,
`SimpleNew<Op::route,Phase,512,10>`, including the two descriptor outputs.
It is separate from the `ng::route_gather` diagnostic in the parallel family.

Historical stage medians below come from the 200 specialised/packet18 samples
in `parallel-route-events.json`, hash-bound to the requested packet29 event
receipt. They are not new measurements. The 48 groups per token make this
68.770 us sum worth measuring; summing stage medians is not the median of a sum.

| Stage | Existing median us | Existing plain GEN instructions/messages | Candidate plain GEN instructions/messages |
|---|---:|---:|---:|
| 0: maxima across each aligned 16-input block | 3.333 | 298 / 26 | 133 / 11 |
| 1: deterministic exp and aligned 16-input partial sums | 20.312 | 873 / 32 | 705 / 16 |
| 2: divide every exponential by the same partial-sum tree | 2.604 | 270 / 25 | merged below |
| 3: stable rank, select and descriptors | 37.500 | 1779 / 132 | 926 / 55 (stages 2+3) |
| 4: selected top-10 sum and normalization | 3.021 | 1529 / 169 | 1363 / 154 |

These are **whole static GEN** counts including every scalar-type branch and
exceptional conversion path, not dynamic counts or a fitted timing model.
`route42-codegen.json` also records every rounded-range wrapper: incumbent
stages 0..4 are 544/59, 1249/116, 544/63, 2160/166 and 3071/204;
candidate stages 0,1,4 are 169/10, 761/15 and 1418/154. All report 128 GRFs.
Both implementations keep run-time scalar enums in their captured arguments;
these totals therefore include branches not taken by the production fixture
(BF16 logits, u32 IDs/descriptors, FP32 probabilities). Smaller stage 0/1/4
code also reflects the compact argument capture, not changed arithmetic.
The retained asm and zeinfo are compressed under `route42-assembly/`.
The candidate SPIR-V bytes occur exactly in the linked native binary at the
offsets in `route42-offline.json`; GEN bytes match the offline ELF text prefix
with zero padding, as asserted by `route42_analyze.py`.

The rank changes its **dynamic work mapping** from one element per work-item
with 512 sequential comparisons to one element per subgroup with 16
comparisons per lane. Each of 512 subgroups has 32 lanes. It still performs
512 x 512 comparisons, with exact integer sums reduced through five adjacent
subgroup tree levels. Source uses stride 32; GEN confirms the main loop
unrolled four times (index increment 128), with stride-32 remainder code.
There is no 512-element serial loop in a lane, local memory or barrier.
Stages 0 and 1 remain 32 parallel aligned blocks; stage 4 remains the existing
top-10 operation. Removing stage 2 trades its launch and probability store
for repeated precise divisions within rank; that extra arithmetic can lose.
The timing window decides. No source/assembly count implies a speedup.

The exponentials and their partial sum remain FP32. Rank recomputes precisely
the same division before comparing, including equal-probability ties; lower
original index wins. The selected probability undergoes the unchanged
top-10 adjacent sum, including the odd-tail +0 rule, then the final division.
Input NaN/Inf sets the same error and leaves outputs untouched. Active/error
guards and descriptor order are unchanged. The captured argument is <=128
bytes. Binding checks reject undersized, non-device, misaligned or forbidden
aliased output/scratch/control allocations before submission.

`route42-gates.json`: GNU and Intel host compilers, two fresh processes each,
120 cases per process. N=1,3,17,255,512; varied values, ties, NaN, Inf,
inactive and preexisting error; both input and output ABI variants. Each
process passes 16,800 byte checks against the extracted incumbent and 16,800
against the reference core. The reference core supplies selected IDs and
probabilities; its unchanged descriptor formula is then applied explicitly,
because the core route operation itself does not write descriptor outputs.
Reference scratch is a bounded 1 MiB; the native candidate scratch is 4352 B.
Native `route42_timing.cpp` builds the existing adapter fixture with the
production folded route ABI, submits the incumbent through its runtime path,
and requires byte equality with this oracle on every one of 200 repetitions.
Both host wall and each GPU event duration are emitted. These buffers are
below 8 MiB and therefore need no payload rotation.

The native binary is `build/route42/p42-route`, SHA256
`62ebd4c8b76b3dfd02e968d2e0cb5724931e707f50352c309ca23b85ad24571e`.
Build flags and immutable linked object hashes are in `route42-build.json`.
Only the coordinator may execute it: use the packet window's route component
with `--card N`; K0 passes `--compile-smoke` before K2's 200 repetitions.
