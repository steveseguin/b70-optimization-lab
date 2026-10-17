# Packet 48: bytes and the useful bandwidth opportunity

This is a metadata and source-code census, not a new device measurement. The
inputs are the tracked GGUF tensor table at
`stage2/suite-inputs-20261012/architecture-tradeoff/plan.tsv`, the merged3
kernels, and packet46 `p46-a-t1/t2/run/iterations.jsonl`. `byte-census.json`
pins their SHA256 hashes and retains every shape, format and matching layer.
No model payload was opened. Reproduce from repository root:

```sh
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet48-gemv/census.py --output experiments/own-xpu-runtime/stage2/packet48-gemv/byte-census.json
```

The `UD-IQ3_XXS` model name is **not a tensor-format description**. In the
48 target layers, ordinary routed gate/up is **IQ2_S**, down is **IQ4_NL**.
Layer 2 alone uses IQ3_S gate/up. No target routed tensor uses IQ3_XXS.
The actual format blocks are IQ2_S 82 B/256 values; IQ3_S 110 B/256;
IQ3_XXS 98 B/256 (supported, absent here); IQ4_NL 18 B/32;
Q6_K 210 B/256; Q8_0 34 B/32; F32 4 B/value.

Dense Q6 and Q8 are expanded at load time. Their finite arithmetic reads
one signed byte/value plus an FP32 scale per 16 or 32 values: **1.25 or
1.125 useful bytes/value**. The row stride also retains 18 B/256 or 2 B/32
of original metadata, which the current dense loops do not read. Counting
packed GGUF bytes understates the working payload; counting the whole expanded
allocation overstates useful reads. Both are retained in the JSON.

All MB below are decimal. The bandwidth numerator is **unique useful weight
payload**. It is not a hardware DRAM counter. Cache hits, repeated lane loads,
activation reads, scratch, epilogues, controls and cache-line fetches prevent
an exact physical-byte count from source alone. `core_operand_accounting`
adds input/output payload and source-level repeated loads separately. The
550 GB/s comparison is a planning ceiling, not a promise for each tiny call.

| Class, ordinary layer | Packed weights MB | Useful runtime weights MB, M=1 | M=2 unique weights MB | M=2 current serial reads MB | T1 / T2 µs, M=1 | Useful GB/s | Gap to 550 GB/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| expsgate, both gate/up, 10 experts | 10.496 | 10.496 | 10.496–20.992 | 20.992 | 81.875 / 81.771 | 128.2 | 421.8 |
| expsdown, 10 experts | 9.216 | 9.216 | 9.216–18.432 | 18.432 | 91.875 / 91.875 | 100.3 | 449.7 |
| gdn.qkv | 21.504 | 32.768 | 32.768 | 65.536 | 100.105 / 100.104 | 327.3 | 222.7 |
| gdn.z | 12.902 | 19.661 | 19.661 | 39.322 | 39.740 / 39.791 | 494.7 | 55.3 |
| attention, output projection/combine | 12.902 | 19.661 | 19.661 | 39.322 | 57.605 / 57.708 | 341.3 | 208.7 |
| small.ffn.q6, router + shared gate/up + scalar gate | 7.941 | 9.349 | 9.349 | 18.698 | 27.812 / 27.604 | 336.2 | 213.8 |
| shexpdown | 1.741 | 1.843 | 1.843 | 3.686 | 11.041 / 10.937 | 166.9 | 383.1 |
| HC set, both attention and FFN | 14.336 | 15.155 | 15.155 | 30.310 | 134.166 / 130.053 | 113.0 | 437.0 |

**M=2 GPU timing and effective GB/s are not measured by packet46.** Those
fields are null, not inferred from M=1. Here M=2 means two changing token
rows; it does not mean rows4 output grouping. Dense rows can reuse one weight
payload. Routed rows have 10–20 unique selected experts depending on route
intersection; full reuse is possible only for common expert IDs. Serial
calls process the full 10-expert payload twice. BF16 activations and outputs
are independent for each token. A new M=2 kernel must include both rows in
its timed window and report that overlap, rather than silently assuming it.

The HC subtotal is the median **sum within each iteration** of all `hc.*`
classes. It is 134.166 µs in T1, more precise than the brief's approximate
120 µs. It includes norms, activation, mix and injection as well as GEMVs;
its low useful-weight rate does not identify all that time as bandwidth loss.
The `attention` row is output projection plus combine, not QSA attention.

`route` has **zero model-weight bytes**. The F32 512×2560 router GEMV is
already in `small.ffn.q6`. Route itself performs softmax, ranking and output
normalization in four launches. Its input/scratch/output address extent is
3,648 B at M=1 and 7,296 B at M=2; compulsory payload traffic is at least
6,072 / 12,144 B (excluding control loads). With T1/T2 43.438/43.126 µs,
that minimum gives only 0.140 GB/s. The explicit source loops express
3,221,472 B of payload reads/writes per M=1 (6,442,944 B for serial M=2),
mostly redundant denominator and all-pairs ranking reads. Dividing that by
T1 gives 74.16 GB/s, **not a DRAM rate**: caches, broadcast and compiler
hoisting may satisfy them. This is a reduction/ranking/launch opportunity.

## Rank the opportunity without relabeling it as a speed result

The following upper estimates subtract useful-weight time at 550 GB/s from
T1. Extra traffic and unavoidable arithmetic/launch cost remain, so they are
optimistic. Layer counts match the table's exact shape and format, not just
its class name. QSA output projections share the 48-layer attention shape.

| Priority group | Weight floor µs/call | Optimistic gap µs/call | Matching target layers | Sum of gap ms/target position |
| --- | ---: | ---: | ---: | ---: |
| Routed gate/up + down | 19.08 + 16.76 | 62.79 + 75.12 | gate/up 47; down 48 | **6.557** |
| HC whole set, mixed work | 27.55 | 106.61 | 48 | 5.117 |
| GDN qkv | 59.58 | 40.53 | 35 Q6 | 1.418 |
| Output/combine | 35.75 | 21.86 | 48 | 1.049 |
| Small FFN tuple | 17.00 | 10.81 | 47 Q6 | 0.508 |
| Shared down | 3.35 | 7.69 | 48 | 0.369 |
| GDN z | 35.75 | 3.99 | 35 Q6 | 0.140 |

Route's 43.43 µs above its compulsory-byte floor corresponds to 2.084 ms
across 48 layers, but is deliberately outside the GEMV ranking. HC is also
mixed work; its maximum is not a forecast for a replacement GEMV. These
bounds support starting with routed experts, then QKV; ordinary Z is already
near this weight floor and cannot save 40 µs alone. M=2 reuse can make Z a
larger lever without changing any dot-product order.

Exceptions must get separate timing: layer 2 gate/up is IQ3_S, 14.080 MB
for the pair of ten-expert matrices; its QKV/Z are Q8_0, 29.491/17.695 MB
useful expanded weights, and its small FFN tuple uses Q8 shared gate/up.
All other 35 GDN projection pairs are Q6. The complete selected routed
weight footprint is **949,760,000 B per target position** over all 48
layers, including the IQ3_S exception.

The first preregistered bar, a 1.5× expert pair improvement, saves
`173.75 - 173.75 / 1.5 = 57.92 µs` per ordinary layer. If it transfers
unchanged to both halves, that is about 1.33 ms on a 23-layer half and
1.45 ms on a 25-layer half (the layer-2 exception needs its own gate).
The alternative 40 µs/layer bar corresponds to 0.92 / 1.00 ms. These are
**per target position**, not per emitted token: speculation, draft work,
miss redo and the two overlapping halves prevent simply adding the two
numbers or converting the sum into tok/s.

## Why the source-level count matters

The finite current gate/up pair requests about 24.576 MB of packed-byte
expressions, 32.768 MB of constant codebook bytes and 32.768 MB of activation
bytes per call, despite only 10.496 MB of distinct selected weights and
5,120 B of distinct input. Down expresses 20.480 MB of packed loads and
32.768 MB of input reads versus 9.216 MB of distinct weights and 12,800 B
of input. A source load is not a memory transaction: most of these repeats
should hit caches, but they still cost addressing/instructions unless
optimized away. Dense Q6 scale loads repeat twice per scale group, and Q8
four times per group because lanes process eight weights at a time.

This motivates aligned vector loads, coalesced load-time layouts and
compile-time work geometry while preserving each lane's eight-value sequence,
its `k += 256` progression, SG32 tree, split-four tree and BF16 boundary.
Any expanded routed layout must measure the larger useful payload too; it
cannot claim a packed-weight bandwidth rate while reading expanded bytes.
