# Exact draft lever ranking, before fresh device times

All repository DO-NOT-REPEAT files were searched before source changes.
The packet77 buckets precede packet101/114 and only guide this bounded choice.
Packet108 gives D≈1.78ms before both target halves on hits. Draft cuts transfer
to that hit path; they do not remove the target-correction wait on misses.

| Rank | Distinct mechanism | Reason and bound | Decision |
| --- | --- | --- | --- |
| 1 | Draft fused HC gate: one subgroup per column, four eight-lane streams; parallel sigmoid products and no workgroup barrier | Three gate/mix sites inside the old 0.25 ms HC bucket. The six-GEMV weight read floor remains. Potential is tens of microseconds; source alone cannot establish the exposed fraction. | Implement one design. Require every gate class and their sum <=0.8 in both contexts, both orders, two fresh processes, all bytes exact. |
| 2 | Merge hidden/embedding normalization and projection epilogues | Old embedding bucket 0.06 ms is an upper bound before a fresh budget. Projection traffic dominates; existing p59 normalization/fusions and p94 norm work warn against assuming launches are the cost. | Defer unless the fresh table shows a materially larger norm/merge kernel bottleneck. |
| 3 | Draft route/mixture consumer scheduling | Draft route remains original, unlike target route-fast. Packet109/112 show exact ties, rounded probabilities and kernel latency need independent proof. Old expert bucket 0.25 ms includes big INT8 kernels, not just routing. | Defer until fresh route/gather/combine events justify a larger lever. |
| 4 | Prefix GEMV plus argmax schedule | Old prefix 0.52 ms, argmax 0.02 ms; fixed 80,128 rows now read 256.4 MB useful weights. Reduction/group changes risk a new arithmetic tree or another losing wide-head arm. | No geometry sweep or benchmark-tuned N. Revisit only with a concrete byte-preserving mechanism after timing. |

The selected change is draft BF16 HC, not packet117's target Q8 paired-row
epilogue. It preserves p59's eight physical-lane chains, eight-lane adjacent
tree, intermediate BF16 gate bytes, sigmoid/product expression and stream-order
sum. Packet117's exceptional-value lesson is credited in the candidate's
fallback. No target arithmetic, quantization, KV precision, prefix selection,
draft placement or accepted-token verification changes.

Closed mechanisms stay closed: packet108 INT8 load8, packet106 split prefix,
packet79 rank0 draft, packet104 draft transposition, old packet59 geometry
bundles, compressed/Q4 heads, and repetition of already-selected HC fusions.
Micro improvement alone cannot establish whole-model transfer. The separate
conditional v5 bracket retains cold requests and every-token target checks.
