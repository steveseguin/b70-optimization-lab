# Packet 1c — actual Unsloth GGUF tensor census

**IQ3_XXS remains the first two-card capacity candidate. The reason is its
larger working-space margin, not homogeneous IQ3 experts.** All three actual
filesets pass the weight-only arithmetic with PLE/input embeddings off-device.
In particular, IQ4_XS no longer necessarily needs expert offload. This is
packed-weight accounting, not a measured fit, quality pass or speed result.

The complete [comparison table](comparison.md) replaces the provisional grid
numbers. [ud-census.json](ud-census.json) contains every tensor, row-major shape
(and original fastest-first GGUF dimensions), type ID/name, byte extent, shard,
component, layer, source correspondence, decode-read contribution, per-layer
expert triplet size, component totals and placement arithmetic. Components use
the disjoint names in [packet 1](../packet1/tensor-contract.json), including
separate norms, routers, QSA attention/indexer and PLE lookup/projection.

## What the real files change

- Each variant contains **1,224 tensors across three shards**. The first shard
  contains tokenizer/model metadata and zero tensors. All target layers 0–47
  are present, with 512 experts and top-10 selection per layer.
- **Native MTP is absent**, including the extra expert bank, merge projections
  and block. Its census subtotal is zero and proposal read cost is unavailable,
  not zero-cost MTP. The old plan counted 49 banks. These files cannot implement
  the certified MTP1 configuration by themselves. No additional file was fetched.
- IQ3_XXS's actual expert gate/up matrices use IQ2_S except layer 2's IQ3_S;
  its expert down matrices use IQ4_NL. **No tensor in that fileset uses the
  IQ3_XXS grid.** The complete type distribution for each other variant is in
  the comparison and census; filenames never select the size formula.
- PLE's 128 official FP8 partitions become one **28,800,138,240-byte IQ4_NL**
  table. Its 35 hash/offset/vocabulary values are U64 metadata (280 bytes),
  not tensor payload. The old FP8 global scale is replaced by the packed grid's
  own scales. One 160-element lookup row occupies 90 bytes; sixteen cost 1,440.
- UD also quantizes HC down/up and PLE key/value to Q8_0, the full output head
  to Q6_K, and dense GDN/QSA/shared-expert projections to the types itemized in
  the census. Input embedding types vary by variant. Routers, norms, HC inject,
  small GDN control/conv and PLE conv/norm tensors are F32; the QSA indexer
  projections stay BF16. These widenings are charged as well as the savings.
  `nonexpert_type_inventory` lists **every affected tensor name** by component
  and type, rather than carrying over the official nonexpert floor.

Mapping is based on complete names/shapes and the frozen graph: packed expert
banks correspond to 512 separate official tensors, QSA indexer q/k tensors
split the official combined projection, and singleton conv/gate dimensions
are squeezed. This establishes ownership/size, **not numerical conversion
equivalence**. Values were never read. Quant quality and tokenizer execution
remain untested; these are separate lossy alternatives to the official FP8 line.

## Accounting definitions

For each expert projection bank, `bytes / 512 × 10` is exact for ten distinct
experts: all 512 slices within a bank share one type and shape. Sum over the
three projections and all 48 layers; no routing frequency assumption is needed.
Dense tensors are read once, the full head once, plus one input embedding row
and sixteen PLE rows. The reported decode total also includes 280 bytes of PLE
metadata; the JSON separately retains tensor-only bytes. All packed scales are
already included. Nothing adds official FP8 scales to a GGUF grid.

Two-card resident bytes are `all tensor bytes − PLE table − input embedding
+ one extra HC down/up copy`, matching the previous plan's placement convention.
The 280 metadata bytes are shown separately. All 48 expert banks are resident;
the table does not claim that only the ten selected experts consume capacity.
The per-card halves are optimistic balanced arithmetic, not rank allocation
plans. Additional router/norm/indexer replicas, padding, repacks, dequantization
buffers, GDN state, full 16-bit KV, graphs and scratch still need admission.
The historical capacity is 68,484,595,712 bytes across two cards, and the same
753,139,712-byte KV scenario is subtracted separately for comparison.

These logical reads exclude KV/state/activation traffic and collectives. The
JSON also gives target reads with the extra HC copy for hypothetical TP2.
They are neither measured device traffic nor PCIe misses, and no tok/s claim
follows. The host still needs a PLE/storage plan: even the smaller 28.8 GB
table exceeds the 15 GiB host's RAM. Storage, quant quality, and a native window
remain the owner's decisions; nothing here authorizes a weight download.

## Fetch and validation evidence

The publisher is [Unsloth at the pinned revision](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/tree/766911a6b7369840a91dbcd95f9f997acaab6cd6).
[fetch-receipt.json](fetch-receipt.json) records request URLs, redirects, exact
inclusive ranges, response lengths, range hashes, complete retained-prefix
hashes and HF file identities. The compressed `headers/` files preserve only
the bytes parsed; no alignment padding or tensor data was fetched. The
compressed HF API response is retained to recheck sizes/LFS identities offline.
HF LFS hashes are publisher claims; **payload hashes were not verified**.

[fetch-headers.py](fetch-headers.py) uses our packet 1b GGUF parser with structural
lower-bound hints. Every HTTP body must have status 206, exact Content-Range
including the HF total size, matching Content-Length, and identity encoding
before it is read. Requests are at most 1 MiB, end at a proven header boundary,
and have a 64,000,000-byte file cap; the parser's stricter 32 MiB limit also
remains. There is no generic chunk read past the final tensor-info record.
The parser gained size support for F32, IQ4_NL, IQ3_S and IQ2_S using the
already-pinned [format declarations](../../stage1/packet1b/loaders/FORMAT.md).
Numerical decoding of those newly admitted types still rejects explicitly.

The initial unsupported-IQ4_NL discovery stopped before the full table was
available. Its small discarded prefix was fetched again before persistent
per-range progress was added; the receipt records this separately, including
the limits of the reconstructed attempt. Subsequent parser extensions resumed
from retained bytes. No tensor payload was involved in any attempt.

The offline checker validates every saved range hash, refreshed HF sizes/LFS
identities, shard ordinals and complete tensor coverage, all 1,224 expected
names/shapes, row-block divisibility, tensor extents/alignment, final file size,
component sums, and a deterministic rebuild. The 38 header tests and four
packet-specific guards cover header-only bounds, rejected HTTP responses,
the hard cap, and rejection of header-only formats by the numerical decoder.
The broader old arithmetic/dequant test collection requires torch, absent
from the system Python; it was not installed or used for this header-only job.

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet1c/census.py
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet1c/test_ranges.py
nice -n 19 env OMP_NUM_THREADS=2 PYTHONPATH=experiments/own-xpu-runtime/stage1/packet1b python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage1/packet1b/tests -p test_headers.py
```

`census.py --write` regenerates the JSON from retained headers. Reacquisition
uses `fetch-headers.py --fetch` and skips completed receipt entries; it needs
only the same metadata/header access authorized for this packet. There was no
GPU, server, systemd, port, device-node, power or memory-setting operation.
Existing lanes were untouched. Temporary fetch-progress files were removed;
the retained compressed prefixes are deliberate evidence, not scratch.
