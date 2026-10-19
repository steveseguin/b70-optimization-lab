# Conditional exact router epilogue

This is a design boundary and CPU arithmetic specification, **not a qualified
device design**. The prerequisite 0.4 ms/half removable latency is unproved.

Retain the actual small.ffn tuple's four independent projections and all
`iq3-p49-split32-v1` chains, split origins, products, additions, reduction
trees, and BF16 stores. In particular, routing consumes the **stored rounded
router output**, never the unrounded GEMV accumulator. Keep shared gate/up and
scalar-gate stores and the original p109 activation expression. A per-row GEMV
epilogue cannot compute a global top10 before all 512 rows finish.

A possible separate research mechanism is **last-completing-workgroup
election**, with no device spinning: every original producer group completes
its stores, performs the required workgroup global-memory fence, and its
leader makes a device-scope acquire/release increment on an invocation-local
counter. The last group acquires the complete producer release sequence and
owns the global epilogue; other groups exit. This must cover the complete
four-projection tuple because route also owns shared activation. It must
neither replace the GEMV's inter-row parallelism with one huge serialized
group nor wait for unscheduled groups in a spinning global barrier.

The producer's actual group width is retained. If it has 128 lanes, the elected
group can own four entries per lane using 512-entry local arrays. Each bitonic
round reads the old values, then updates after a barrier, preserving all 45
rounds and the exact comparator. This is likely **more** synchronization than
p109's 512-lane implementation and may lose the saved launch. Preserve the
original 32-lane GEMV reduction independently of this epilogue mapping.
Do not count the 0.536 ms fused router itself as removable.

Required correctness sequence:

1. Validate original allocation extents, input/output/control aliases, owner,
   generations, selected shapes and argument types before submission. Reuse
   the original native admission; the small CPU API guard is not its replacement.
2. Finish and store all original rounded producer values. Refuse any NaN/Inf
   route logit before route IDs, probabilities, expert descriptors or shared
   activation are written. The original error flag may change; rejection's
   partially written maxima scratch is not published output.
3. Preserve the ordered maximum scan, `detmath::exp`, adjacent 16-leaf FP32
   sums,32-part denominator tree and **FP32 division before ranking**. Exponentials
   and logits are not interchangeable ordering keys after rounding.
4. Use the original fixed bitonic comparator: larger rounded probability,
   then smaller original expert ID. Verify all ten IDs are distinct and<512
   before publication. Retain original output descriptor layout.
5. Preserve the selected 10-value padded sum and second FP32 division. Do not
   cancel the first normalization algebraically. Keep p109 activation's
   original BF16 read/write and `ng::silu` expression after the route succeeds.
6. Publish completion only after all route/activation writes. All downstream
   expert consumers wait on that event, and the common BF16 writer invalidation
   tail still runs. Preserve zero-launch Sites for stable capture indices.

The counter must start at zero on **every** call, including every captured
bank pair, reset, failure and continuation. A reset kernel or host copy has a
cost and must be charged. A safe final-group reset must prove all prior groups
have completed their final writes, and independent/in-flight invocations cannot
share the counter. Counter wrap, stale generations, error/active exits and
concurrent request replay require explicit CPU sequence tests before building
a device program. No implementation of that synchronization exists here.

## What the CPU gate proves

[epilogue.hpp](epilogue.hpp) is an executable specification after completed
rounded logits. It uses the original bitonic network, not packet112's pruned
network. [oracle.cpp](oracle.cpp) compiles the actual p109 host route in a
separate translation unit with runtime shapes and no LTO. The exact p141 header
is copied into private build scratch; p97 supplies the complete type tree.
The relevant p97/p141 arithmetic headers must compare byte-for-byte first.
This avoids mixing duplicate owner/type trees after p141's p28 directory was
archived; frozen sources are not repaired.

GNU O3/native and Intel O3, both with fast math off and FP contraction off,
each run twice in fresh processes. Every run compares **2,304** complete
route output/scratch/error cases at 512 experts, top10,640 intermediate and 2560
hidden width, both 2/4-output ABIs and F32/BF16 input. This includes512 lower-ID
tie cases, 128 distinct-logit rounded-tie cases,256 NaN/±Inf cases, inactive
and prefailed rows. Every run additionally refuses18 malformed/aliased ABIs
and five out-of-range/duplicate/wrong-extent selected routes before output writes.
Four output hashes agree. [Receipt](evidence/cpu.json) and per-compiler source
closures/commands are retained; peak compiler RSS is below 300 MiB.

No router GEMV, device synchronization, shared-activation rewrite, real model
logit capture, full-model output or performance is certified by this gate.
The existing activation is deliberately unchanged. A future fusion needs its
own exact full producer→route→activation bytes and real-arm engine sequence
gate, including both compilers' original nonfinite behavior (packet109).
