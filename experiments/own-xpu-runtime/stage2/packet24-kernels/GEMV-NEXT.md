# Large GEMV work after packet 24

No large GEMV arithmetic or decomposition is changed by this packet. No device was run for this analysis. Proposed gains below are hypotheses to preregister and measure, not performance claims.

The first three candidates are:

1. **Routed gate/up: share decoded IQ2/IQ3 grid entries across the existing lanes and put independent output rows on otherwise idle subgroups.** This class costs 8.53 ms/token in the supplied unfused trace, but moves only 10.50–14.08 MB of packed weights per launch group. Its effective packed-weight rate is 59.5 GB/s. Preserve each lane's ordered products, tree32, split boundaries, BF16 gate/up results, and SiLU boundary. A 1.5–2x class improvement is a useful first hypothesis (2.8–4.3 ms/token saved), not a measured forecast.
2. **Routed down: coalesce IQ4_NL code loads and reuse the existing exact lookup across independent rows.** Preserve each lane's original sequence and the ordered expert mixture. At 70.8 GB/s effective packed bandwidth this has much more headroom than the dense expanded paths. Hypothesis: 1.4–1.8x in this class, saving 1.8–2.8 ms/token.
3. **Expanded GDN qkv/z and QSA qgate: reuse scales in registers and schedule independent rows across subgroups.** The R5 trace already uses expanded int8 codes and FP32 scales. It is incorrect to blame these results on packed-grid decoding. Preserve the qualified lane assignments, scalar product/add order, split tree and BF16 conversion. Hypothesis: 1.15–1.35x; prioritize qkv because it contributes 3.62 ms/token and shares a batch with z/a/b.

## Bytes and bandwidth

Sources: [exact tensor census](../../../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json), [R5 class trace](../packet18-decode-v2/evidence/20261011-host-bottleneck-location-scan/run-r5e-class-times-cards01/class-times.json), [R5 dispatch](arithmetic.hpp), [expanded representation](../packet10-kopt5/expanded.hpp). The trace contains 63 generated tokens. Divide `device_ms*1000/groups` to recover microseconds per logical launch group. Those timings are first-start to last-end spans, not the sum-of-execution metric that K2 will produce. Thus bandwidth here is effective bandwidth over the recorded span, not a hardware-counter DRAM measurement.

Each routed group reads ten experts. Gate/up reads both matrices. Dense rows include one upgraded Q8 layer among the GDN layers; the table gives per-group mean bytes and the range where types differ. Decimal MB and GB/s are used. The 590 GB/s reference is a single-card memory roofline, not an achieved rate for these kernels. Activations, output writes, cache reuse, duplicate scale fetches, and transaction amplification are excluded. The floor is only the unique weight bytes divided by 590 GB/s, so it is not an attainable end-to-end prediction.

| Class | Shape per matrix, rows × columns | Packed bytes/group (mean; range) | Unique R5 weight payload bytes/group (mean; range) | Measured span us/group | Effective GB/s on R5 payload | 590 GB/s floor us | Roofline/current ratio |
|---|---|---:|---:|---:|---:|---:|---:|
| expsgate (gate + up) | 10 × 640 × 2560, twice | 10,570,667; 10,496,000–14,080,000 | same packed bytes | 177.738 | 59.5 | 17.916 | 9.92× |
| expsdown | 10 × 2560 × 640 | 9,216,000 | same packed bytes | 130.193 | 70.8 | 15.620 | 8.33× |
| gdn.qkv | 10240 × 2560 | 21,680,356; 21,504,000–27,852,800 | 32,676,978; 29,491,200–32,768,000 | 100.573 | 324.9 | 55.385 | 1.82× |
| gdn.z | 6144 × 2560 | 13,008,213; 12,902,400–16,711,680 | 19,606,187; 17,694,720–19,660,800 | 61.908 | 316.7 | 33.231 | 1.86× |
| qsa.qgate | 12288 × 2560 | 25,804,800 | 39,321,600 | 118.161 | 332.8 | 66.647 | 1.77× |
| logits | 248320 × 2560 | 521,472,000 | 794,624,000 | 2136.794 | 371.9 | 1346.820 | 1.59× |

For Q6_K, R5 reads K int8 codes plus K/16 FP32 scales per row: `K + 4*K/16` unique bytes. Q8 reads `K + 4*K/32`. The expanded allocation also retains original metadata, which `expanded::value` does not read; counting it as bandwidth traffic would overstate the number. Packed-equivalent rates for qkv/z/qgate/logits are respectively 215.6/210.1/218.4/244.0 GB/s, but those are not actual R5 payload rates.

## Two exact candidates per class

| Class | Likely bound from this evidence (inference) | Candidate A, expected class gain hypothesis | Candidate B, expected class gain hypothesis |
|---|---|---|---|
| expsgate | IQ2/IQ3 lookup/sign/scale instructions, subgroup underuse, repeated input prologue; memory alone cannot explain 10× roofline distance | Subgroup ownership of grid decode with register broadcast; same ordered lane arithmetic, 1.3–1.7× | Several independent rows per work-group with the existing complete lane/tree assignment for each row; paired gate/up remain rounded separately, 1.2–1.5× |
| expsdown | Packed IQ4 decode/lookup and row scheduling; effective 71 GB/s is far below bandwidth ceiling | Vector loads with exact IQ4 level lookup reuse, 1.2–1.5× | Multiple independent output rows per work-group; no change to expert accumulation or per-row tree, 1.2–1.5× |
| gdn.qkv | Expanded payload bandwidth plus repeated input mix/scale loads; no packed-grid decode in R5 | Carry each FP32 scale across its existing 16-code block in registers, 1.1–1.2× | Independent rows occupy all subgroups while retaining split4 vs SG32 identity; share exact BF16 input materialization per legal batch, 1.15–1.3× |
| gdn.z | Same expanded Q6/Q8 path as qkv, fewer rows | Block-local scale reuse, 1.1–1.2× | Exact input BF16 prologue once per sibling batch with explicit producer dependency, then retain row trees, 1.1–1.25× |
| qsa.qgate | Expanded Q6 payload, output-row scheduling and HC input prologue | Keep scales live for their complete blocks and use contiguous code loads, 1.1–1.2× | Independent qgate rows and sibling k/v/iq/ik rows scheduled across available subgroups, 1.1–1.25× |
| logits | Closest of these classes to bandwidth ceiling; 0.795 GB unique expanded weights/token | Sequential code load/scale reuse without altering SG32 tree, 1.05–1.15× | Exact packed Q6 alternative preserving the existing expanded arithmetic expression and lane tree; trade lower bytes against decode cost, 1.1–1.3× only if operator gate and matched timing pass |

Do not multiply candidate gains together. An exact packed alternative to expanded weights must reconstruct the identical FP32 scale and multiplication sequence, including nonfinite signs/payloads and denormals. Keeping the same mathematical dot product is insufficient. Every candidate needs both host compilers, unchanged reference output, fresh owners, and the real-model oracle. The registered oracle stays attached to its exact arithmetic tree.
