# Stage 2 packet 1 — local Flash-Next identity and tensor contract

**Exit gate: PASS — CPU metadata, oracle and arithmetic only, 2026-10-10.**
The [receipt](check-receipt.json) checks the official local checkpoint's
152,089 tensors in 131 shards, all 12 complete certified response arrays,
40 parser/reader cases, and deterministic reconstruction of four manifests.
No native runtime, numerical parity, placement fit or speed gate has passed.
Stage 1 packets 2+ still await their owner decisions; this packet does not
advance them or authorize an operational window.

## What is frozen

[identity.json](identity.json) binds publisher `Qwen`, repository
`Qwen/Qwen3.8-Flash-Next-FP8`, revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, and the checkpoint at
`/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`. All 144 root file sizes and
local HF download revision/etag records match the
[official revision metadata](https://huggingface.co/api/models/Qwen/Qwen3.8-Flash-Next-FP8/revision/bcd9f01ddc9cff2316eb84281bebcd5b058bddce?blobs=true).
Small metadata files were hashed against publisher Git-blob/LFS identities;
config, tokenizer requirements, generation defaults and chat template also
matched independently fetched publisher bytes. The
[local capture receipt](metadata/local-metadata-receipt.json) retains every
file's expected publisher identity through its download metadata. Only the
8-byte length prefix and bounded JSON header were read from each safetensors
file, using unbuffered reads. **Shard payload hashes were not recomputed.**
Matching size and cached etag is metadata consistency, not authentication of
173 GiB of weight payloads.

The baseline is the [certified A367 identity](../../../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/identity.json):
**46.85424994838007 tok/s**, four B70s, TP4/EP4, native MTP1,
4,352-token capacity, BF16 activations/full 16-bit KV, exact serial GDN,
full decode graphs [1,2], fused QSA and Triton hyperconnections. The pinned
September vLLM overlay, hybrid kernel stage, oneCCL binaries, tuned MoE map,
placement, launch flags, host identity, metrics, logs and attestation references
are retained. [Archived command](evidence/server-command.shell.txt), runtime
versions and card PCI IDs were rescued and checked against A367's pre-existing
run manifest. Its original command file retains its checksum-bound trailing
space. No launcher was executed. Missing historical boot, UMD and
firmware identities remain null, rather than being filled with today's host.
The complete historical process environment was not retained; pinned launch
sources preserve the declared settings. October's newer runtime is separate.

[oracle-token-ids.json](oracle-token-ids.json) extracts **5,979 tokens** in the
original 12 rows: eleven 512-token answers and one 347-token answer. Source:
[A367 fixed-suite responses](../../../qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json),
SHA256 `f88da9b4e041255dc36363363bd78756ebcd10418953e1ea7477d63e7b8014dc`.
The [fixed suite](../../../../repro/rapid-model-snapshots-b70/realistic-suite-v1.json)
has SHA256 `0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812`.
Every array, prompt and output text is hashed; identity.json hashes the complete
extraction. All rows are cache-zero, with six varied prompt classes. The
checker recomputes each 99-interval rate and the median of class medians.
The historical 100-event compatibility metric remains distinct.

This is **chat**, with one user message, no system message and
`enable_thinking=false`: temperature 0, top_p 1, seed 20260609, natural
512-token cap, `--generation-config vllm`. Use the pinned Flash tokenizer and
chat template. Stage 1's raw-completions prompts and seed are not this oracle.
Vocabulary, merges and tokenizer JSON were hashed locally but are not duplicated
in Git; requirements, special tokens, regex and template are retained. Executing
the tokenizer and proving prompt-token parity remain later checks.

## Complete tensor directory

[tensor-contract.json](tensor-contract.json) records every name, stored dtype,
format, shape, byte extent, shard, data/file offset, graph owner and layer index; the target layer-kind schedule is stored once.
Shapes are independently reconstructed from config, with the exact PLE table
row geometry frozen from this revision; the checker rejects unknown or missing
names. The 128 PLE table partitions are tensors, not 128 extra safetensors
files. Norms are disjoint accounting rows; PLE and MTP keep their internal norms.
The MTP subtotal includes its own 512 experts but shares the target embedding
and full head, which are stored only once.

| Component | Tensors | Stored bytes |
| --- | ---: | ---: |
| embedding | 1 | 1,271,398,400 |
| gdn | 288 | 4,173,011,712 |
| hyperconnections | 290 | 1,279,262,720 |
| native mtp | 3,101 | 2,698,026,496 |
| norms | 181 | 2,014,208 |
| ple lookup | 132 | 51,200,246,042 |
| ple projection | 6 | 65,679,360 |
| qsa attention | 48 | 1,195,376,640 |
| qsa indexer | 12 | 39,321,600 |
| routed experts | 147,456 | 120,810,700,800 |
| routers | 96 | 126,074,880 |
| shared experts | 144 | 471,859,200 |
| target head | 1 | 1,271,398,400 |
| vision excluded | 333 | 897,862,112 |
| **Total** | **152,089** | **185,502,232,570** |

| Layer kind (includes its MoE, HC and norms) | Stored bytes |
| --- | ---: |
| full attention | 31,903,905,792 |
| linear attention | 147,446,513,690 |
| native mtp qsa | 2,698,026,496 |
| target global | 2,555,924,480 |
| vision excluded | 897,862,112 |

There are 36 GDN and 12 QSA/full-attention target layers, each with 512 routed
experts, top-10 selection and one BF16 shared expert. QSA includes its indexer.
Four hyperconnection streams and low-rank 320 matrices are retained. Native
MTP is one separate full-attention/MoE/HC block. Vision's 897,862,112 bytes are
counted and explicitly excluded from this text runtime.

**Byte reconciliation:** 185,502,232,570 tensor bytes + 21,084,888 header/prefix
bytes = **185,523,317,458 shard-file bytes**. Another 40,465,669 bytes of root
metadata gives **185,563,783,127 total root-file bytes**. Both lane and HF
file totals match exactly. Filesystem allocation/du includes directory/cache
and allocation effects and is not the publisher file sum.

Stored dtypes: 174,512,783,360 bytes FP8 E4M3, 10,989,448,930 bytes BF16 and
280 bytes I64. **No stored FP32 tensors exist.** All 75,264 routed-expert
block scales and PLE's one global scale are BF16 (15,052,802 bytes total).
HF's aggregate parameter summary omits all 7,526,401 scale elements; this
fully explains its difference from the headers. Experts use 128×128 block
scales, while PLE's 128 FP8 tables share one scalar. Attention, HC, shared
experts and the target head are BF16; treating the whole checkpoint as
one-byte weights would undercount it.

## Active bytes and placement

One expert's gate/up/down FP8 weights total **4,915,200 bytes**, plus **600
bytes** of BF16 scales. Top 10 therefore reads **49,158,000 bytes per layer**;
48 target layers total **2,359,584,000 bytes**, including 288,000 scale bytes.
Dense target weights contribute **8,623,998,720 bytes**. One embedding row
(5,120), sixteen PLE rows (2,560) and small PLE metadata (282) give
**10,983,590,682 logical weight bytes per target decode token**.

One MTP proposal adds **1,501,698,416 bytes**, including its top-10 experts,
merge/HC/QSA, one embedding row and the shared full target head. One target
plus one proposal is **12,485,289,098 bytes**, not a claim about bytes per
emitted MTP token: rejected verifier rows and accepted-token counts matter.
No runtime draft-head shortcut is assumed by this full-head planning count.

The historical placement replicates HC projections. Counting those known
replicas gives a target weight-read floor of **14,797,785,882 bytes across
TP4**, or **12,254,989,082 across hypothetical TP2**. Other replication,
activation scales, KV/state reads/writes, collectives and workspaces are extra.
There is no bandwidth or speed measurement here, and no borrowed throughput
is used to turn these byte counts into predicted tok/s.

If an implementation stores expert scales as FP32, the target scale traffic
becomes 576,000 instead of 288,000 bytes; widening PLE's scalar adds two bytes.
The contract records that conditional **288,002-byte** addition and the
MTP block's separate 6,000-byte addition. It does not relabel stored BF16
scales as FP32 or assume a runtime's conversion is free.

[placement-census.md](placement-census.md) and its checked
[arithmetic](placement-arithmetic.json) compare certified four-card placement
with two-card requirements. In the stated historical capacity scenario, the
two-card weight-only gap is **64,958,850,586 bytes**, after PLE and input
embeddings are already off-device. Full 16-bit KV, graphs and workspace make
the gap larger. This is not a fit approval.

## Differences and boundaries that must survive implementation

- PLE config id **2 is one-based**, stored under `model.language_model.layers.1`.
  Its 320,001,536 physical rows are split into 128 tables of 2,500,012×160;
  “20M vocabulary” is not the physical table row count. The 280 bytes of integer
  hash/offset metadata were not read as values; only their descriptions are known.
- The certified GDN verifier passes recurrent state through **BF16 between
  serial rows**. DESIGN/config's FP32 recurrent state is a proposal and cannot
  silently replace the old arithmetic. Freeze comparator fixtures before
  deciding storage/cast order. Full-precision BF16 KV remains unchanged.
- This Flash line's Triton FP8 MoE arithmetic is not the 27B W8A16 path.
  No source runtime is imported or used as an implementation base.
- All root/shard byte totals match. The only HF tensor-summary difference is
  omitted scale elements, fully reconciled above. Historical missing machine
  fields and absent payload authentication remain explicit limitations.
- The exact output authority includes the inherited quality battery's known
  code-answer miss. Exactness preserves that authority; it does not repair
  or strengthen the model's task-quality result.

## Re-run

Offline, without reading the model directory or using a network:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet1/contract-checks.py
```

Add `--local` to reread only local shard prefixes/headers and check sizes;
add `--receipt experiments/own-xpu-runtime/stage2/packet1/check-receipt.json`
to save a receipt. `--write-contracts` regenerates the four derived JSON files.
The checked parser is the repository's Stage 1 packet 1 template, extended
only for I64 metadata. Its 35 malformed/valid fixtures plus five new bounded
reader/I64 cases cover duplicate keys, dimensions/products, unsupported types,
overlaps/gaps, oversized/truncated headers and a synthetic payload-read guard.
All tensor names, shapes and scales are independently checked against the graph.

[capture-metadata.py](capture-metadata.py) reproduces the source capture from
the local directory and revision-pinned HF **metadata only**. It requires the
same nice/ionice/thread limits and writes only this packet's metadata directory.
Gzip files contain exact original header/index bytes, with deterministic gzip
headers; their uncompressed SHA256 values are retained. The checker uses only
Python's standard library. No torch/model source is executed.

This work used no GPU, model/server launch, systemd operation, port access,
device-node access, weight download, native build or host setting change.
Nothing under `/mnt/fast-ai` was modified. Temporary duplicate metadata copies
were removed; no scratch directory or bytecode cache remains.

## Next authorized Stage 2 window

The owner must resolve the host halt and authorize an exclusive native window;
this packet does not request or assume one. Before loading, reauthenticate
all admitted payloads, pin the current upstream/build plus preserved arithmetic
overlay, and collect joint per-card weights/KV/state/graph/workspace and host
RSS/PSS/pinned/shadow peaks with graceful teardown. Protect the existing lanes
and retain the loading guard as evidence, not a new-runtime allowance.

Then run the complete production operator census, including routed experts,
router top-10 order, shared expert, four-stream HC, layer-2 PLE, GDN serial
state/casts, QSA/indexer/compression and native MTP. Extract comparator fixtures
only after proving instrumentation neutrality against these full 12 arrays.
Require exact operators/layers, fresh-process repeats, unchanged target
verification and rollback before a cold full-suite speed comparison. UVA and
explicit expert staging must have bounded ownership and completion events;
if host-controlled misses split replay, say so. Two-card topology needs its
own arithmetic/output and memory admission gates and cannot inherit TP4 speed.
