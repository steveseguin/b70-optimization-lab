# Independent QSA selection review

Reviewed source before receiving the implementer's proposed selection changes. No device API, discovery, model library import, or device binary was used. Source bytes are bound in [selection-source-identities.json](selection-source-identities.json). The official-model wiring sources are the same locally retained sources identified in packet31's `wiring-review.md`; they establish model structure, not equivalence between CPU and vendor-kernel floating-point arithmetic.

## Reference arithmetic identity

The suite oracle includes packet13 `main.cpp` (oracle.cpp:7), which includes packet3 `kernels/mock.hpp` (main.cpp:2). Its QSA equations are mock.hpp:364–431. Packet38's independent arena-based arithmetic-v2 core implements the same selection contract in core_v2.hpp:392–435, with the deterministic math implementation used by this lane.

For a request with **n valid positions**, current position is n−1. Let b=floor(n/4). Pool only complete chronological groups of four, accumulating the four raw BF16 rows in order in FP32, dividing by four and rounding BF16. Normalize that rounded row and rotate at the group's first position (4j). Original reference may recompute old pools; retaining their identical bytes is valid. Current incomplete tail is never pooled (core_v2.hpp:399–409; official ops/qsa.py:509–543; indexer_qsa.py:294–322).

Score each of b pools with four 128-element adjacent-tree dots, clamp each head's dot to nonnegative, add the four head contributions in head order, then divide by deterministic sqrt(128). Reject nonfinite scores. The lab reference initializes IDs in ascending order then stably sorts by descending FP32 score: equal scores, including signed zero, choose the lower block index first. Keep min(b,512) groups; expand each chosen group to four ascending token IDs **in score-ranked group order**. Append the unpooled tail in chronological order and fill the remainder of the fixed 2,051-ID list with −1. Attention consumes this order, so sorting selected token IDs chronologically would change the reduction identity.

The ng implementation (kernels.hpp:177–189), specialised implementation (specialised.hpp:161–173), and round2 implementation (round2.hpp:10–27) implement this stable rank by counting strictly greater scores plus equal-score lower IDs. No beyond-budget algorithm replacement is required to obtain the lab reference's selected set and order.

## Official implementation distinction

The official-model QSA wrapper structurally agrees: compressed groups, 512 selected groups, expansion, and always-retained incomplete tail (indexer_qsa.py:342–351; ops/qsa.py:122–191, 744–808). However, its GPU top-k does **not** promise the lab's stable score order. The persistent implementation explicitly emits chronological IDs when the visible block count is at most top-k (persistent_topk.cuh:933–939). Above that, histogram selection writes admitted IDs via warp-aggregated atomic scatter (lines248–295), and refinement handles the threshold separately. The cooperative implementation also scatters IDs and performs threshold refinement (cooperative_topk.cuh:435–473). Neither establishes lower-index tie admission or globally score-sorted output. Thus this packet preserves the lab's already-certified arithmetic-v2 ordering; it cannot claim the official GPU implementation's bit-level ordering. Replacing the lab order with that implementation's order would be an arithmetic-identity change, including at short context.

## Boundary findings and fixtures

The first actual eviction is **n=2,052**, not 2,049: n=2,049 has 512 complete groups plus one retained tail position. n=2,051 fills all 2,051 admitted slots. These two extra boundaries supplement the seven required lengths. At n=4,096, there are 1,024 scored groups and 2,048 admitted tokens; at n=32,767, there are 8,191 scored groups and 2,051 admitted tokens. Capacity edge n=C uses position C−1; passing position C is invalid.

The old full-capacity round2 stage-1 selection launches scan all live scores for finiteness **before** checking b>=n (round2.hpp:16–24), so padded workgroups are not free and can perform real work. The packet44 launch-extent change must bound those groups. Scratch stride may remain capacity-based, but no score computation or reduction may include an unwritten score. Existing p38_qsa_cpu.cpp gates manually assigned selected IDs and never called selection; therefore it was not beyond-budget evidence.

[capacity_selection_gate.cpp](capacity_selection_gate.cpp) invokes the actual arithmetic-v2 Core::run, ng::cpu, round2 stage bodies, and specialised body. It compares every selection slot for varied scores, all ties, and repeated tied scores; tests unique, causal, complete-group and tail bounds; compares complete attention outputs and candidate score/probability scratch; and checks nonfinite rejection. The runner compiles and runs both host compilers without any accelerator-linked library and writes [capacity-selection-gates.json](capacity-selection-gates.json). Selection order and output fixtures are deterministic; timings in that receipt are CPU gate duration only.

## Gate result and limitation

Both GNU and icpx host builds passed 427,082 checks each: 48 selection fixtures (three score patterns at 16 capacity/length pairs), 16 full-attention fixtures, and 48 nonfinite backend fixtures. All three selection backends matched every arithmetic-v2 oracle ID; p30's two attention variants and round2 matched every output, score, probability, and status byte. The diagnostic output hash matched across compilers. This is synthetic CPU evidence; real long-context model quality and device behavior still require coordinator windows.

The first attempt exhausted the test oracle's 512 MiB monotonic scratch arena at capacity 32,768 and n=2,049; it did not expose a kernel mismatch. Increasing this **CPU fixture arena only** to 768 MiB let the complete gate pass. Runtime device scratch/cache sizes are unaffected. The script removes both standalone test binaries after recording their hashes and compresses the small raw JSON outputs.
