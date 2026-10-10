# Packet 1 — weight admission and census

**CPU admission PASS, 2026-10-10. No inference result yet.** All three complete
shards match publisher SHA256 and byte counts. All 1,224 tensors and every
header byte match the range-request census, with zero differences. The
[exit receipt](exit-gate.json) binds the evidence below. This admits stored
weights and bounded CPU fixtures; it does not qualify native arithmetic,
full-model output, two-card fit, speed or a deployment.

## Model and authenticated files

Separate model: **Qwen3.8 Flash-Next UD-IQ3_XXS (Unsloth), quantized compressed
version**. Publisher `unsloth/Qwen3.8-Flash-Next-GGUF`, revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`, folder `UD-IQ3_XXS`.
The owner approved this source and confirmed the completed download at:

```text
/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS/
```

The existing [publisher manifest](../../own-xpu-runtime/data/unsloth-flash-next-stage2-files.json)
is the expected identity; no network refresh or download was used.
[admission-receipt.json](admission-receipt.json) records complete streamed
SHA256s, byte counts, timing, before/after inode/size/mtime/ctime and priority.
The three-file inventory stayed unchanged. Every model read used nice 19,
`ionice -c 3`, `OMP_NUM_THREADS=2`, and read-only file handles.

| Shard suffix | Bytes | SHA256 | Verdict |
| --- | ---: | --- | --- |
| 00001-of-00003.gguf | 10,946,624 | `268f81fdedf3149a538f252308927a4d5d1f6e062c178568a51e3b519744f8a8` | PASS |
| 00002-of-00003.gguf | 49,567,921,344 | `cfe600b236b88c7fad1613a5ca5e83b9f2beb63cbd44c32b2be50a44747c695f` | PASS |
| 00003-of-00003.gguf | 32,382,955,968 | `f1912ba34c79427d2295a58dcb2b732b5931af5bef7a373c60557a57d9ee7250` | PASS |
| **Total** | **81,961,823,936** | All publisher LFS identities match | **PASS** |

Hashing used 4 MiB chunks, 154.006 seconds summed over the files, and peak
process RSS 83,296 KiB. These are admission receipts, not a disk benchmark.
No checkpoint copy or full tensor materialization was needed.

## Full header reconciliation and metadata

The unchanged packet 1b [GGUF parser](../../own-xpu-runtime/stage1/packet1b/loaders/headers.py)
parsed complete metadata and tensor directories from the real files.
[reconciliation.json](reconciliation.json) compares names, type IDs/names,
fastest-first dimensions, reversed row-major shapes, shard identity, relative
and absolute offsets, and tensor bytes against
[packet 1c](../../own-xpu-runtime/stage2/packet1c/ud-census.json).
All **1,224** descriptors match. Header SHA256s also match all three retained
range captures, covering metadata including the complete tokenizer arrays.
Split ordinals, unique names, complete aligned extents and final file lengths
pass; only the 57 expected alignment bytes remain outside headers/payload.
Shard tensor counts are **0 / 468 / 756**. Tensor payload totals
**81,950,799,360 bytes**, with **11,024,519 header bytes**.

[metadata.json](metadata.json) lists every metadata key and GGUF type and
retains scalar/small-array values and the complete chat template. Large
arrays have lengths, edge examples and hashes of the explicitly described
canonical JSON encoding; their original bytes remain authenticated by the
whole-file and header hashes. Key findings:

- Container: GGUF v3, little endian, 32-byte default alignment.
- `general.architecture=qwen4exp`, `general.quantization_version=2`,
  `general.file_type=23`. File type/name is a recipe label, never a tensor decoder.
- `tokenizer.ggml.model=gpt2`, `tokenizer.ggml.pre=qwen35`, 248,320 tokens,
  247,587 merges; BOS/padding 248044, EOS 248046, `add_bos_token=false`.
  Tokenizer execution and prompt-template parity remain packet 2 work.
- `split.count=3`, `split.no=0/1/2`, `split.tensors.count=1224`.
- 48 target layers, 512 experts per layer, top 10. **No native MTP block**.
  PLE's three control arrays carry 35 U64 values, or 280 bytes.

## Actual grids and row/block admission

[tensor-census.json](tensor-census.json) contains every real descriptor,
component ownership, grid bytes and all observed row widths. Component labels
were attached only after descriptor reconciliation passed.

| Grid | Tensor count | Payload bytes | Elements / bytes per block | Row widths |
| --- | ---: | ---: | --- | --- |
| IQ2_S | 94 | 25,257,574,400 | 256 / 82 | 2560 |
| IQ3_S | 2 | 720,896,000 | 256 / 110 | 2560 |
| IQ4_NL | 49 | 51,449,379,840 | 32 / 18 | 160, 640 |
| Q6_K | 250 | 3,328,281,600 | 256 / 210 | 2560, 6144 |
| Q8_0 | 248 | 841,850,880 | 32 / 34 | 320, 640, 2560, 10240 |
| F32 | 557 | 313,495,040 | 1 / 4 | 4, 48, 128, 256, 2560, 10240 |
| BF16 | 24 | 39,321,600 | 1 / 2 | 2560 |
| **Total** | **1,224** | **81,950,799,360** | All rows divisible by block size | |

**IQ3_XXS, Q3_K and F16 counts are zero.** No samples are invented for absent
types. Gate/up experts use IQ2_S except layer 2's two IQ3_S banks; down experts
use IQ4_NL. The other IQ4_NL tensor is PLE. This confirms packet 1c's correction.
Stored scales are already inside these block sizes. No official FP8 scale is
added to a quantized grid, and blocks never cross row boundaries.

## This model's first CPU reference fixtures

Packet 1b previously admitted F32/IQ2_S/IQ3_S/IQ4_NL headers but rejected their
numerical decoding. This packet adds original scalar CPU implementations and
credited normative IQ2_S/IQ3_S tables to that reference. The updated
[format equations and provenance](../../own-xpu-runtime/stage1/packet1b/loaders/FORMAT.md)
identify the exact pinned research source and retained MIT format-data license.
No external runtime implementation became our code base.

[112 loader tests](loader-test-receipt.json) pass, including logical field
packing, every new grid entry, scale/sign/high-bit planes, signed zero, F32 bit
preservation, row/payload rejection and prior decoder/header regressions.
The separate [offline comparison](dequant-crosscheck.json) matches **576
synthetic blocks / 104,448 values bit-for-bit** against the pinned independent
NumPy format implementation; it is a test-only research dependency. The four
header-range guards and three admission-reconciliation tests also pass.

[sample-receipt.json](sample-receipt.json) records **48 real tensors / 156
windows / 182,730 model bytes** spanning every present grid and every
component/type group. Selection is fixed: first/middle/last tensor name per
group, then first/middle/last flattened row. Quantized rows are complete;
F32/BF16 rows wider than 64 use 64-element edge windows. This covers both IQ3_S
banks, expert slice interiors/ends, PLE's 160-wide rows, embedding and full-head
row layout without loading whole matrices.

Each window records its tensor/row/column, absolute file offset, raw-byte
SHA256, decoded FP32 little-endian SHA256, first eight values, min/max, mean,
RMS, finite/zero/signed-zero counts and repeat result. Every sampled value is
finite; same-process and [fresh-process](sample-repeat-receipt.json) output
bytes match. Shared deterministic fixture content SHA256:

```text
db8f3e8645b245b4d43e27f94fb2b463c1b1cbb47a24330062bbd3642daa7fa4
```

These fixtures establish the CPU dequantization authority for the selected
bytes. They are not full-model inference, a complete finiteness scan, a native
kernel comparison or an oracle token stream. FP8 output differences are never
a tolerance gate for this separate model.

## Exact packed residency and estimated working memory

[memory-admission.json](memory-admission.json) recomputes placement from the
real census. The Stage 2 convention offloads PLE/input embeddings, keeps all
48 expert banks callable and resident, and adds one extra HC down/up copy for
TP2. Other replicas are not silently assumed free.

| Component | Resident bytes across two cards |
| --- | ---: |
| Routed experts | 48,627,712,000 |
| GDN weights/controls | 1,754,576,384 |
| Hyperconnections including extra 675,430,400-byte HC copy | 1,366,589,440 |
| QSA attention | 490,291,200 |
| QSA indexer | 39,321,600 |
| Routers | 252,149,760 |
| Shared experts | 213,376,000 |
| Norms | 4,028,416 |
| PLE projections | 35,102,720 |
| Full target head | 521,472,000 |
| **Target packed resident total** | **53,304,619,520** |
| Off-device PLE table | 28,800,138,240 |
| Off-device input embedding | 521,472,000 |

Exact equation: `81,950,799,360 − 28,800,138,240 − 521,472,000 +
675,430,400 = 53,304,619,520`. The optimistic balanced half is
26,652,309,760 bytes/card, not an actual rank allocation plan.
At the historical **68,484,595,712-byte** two-card capacity scenario, the
weight-only margin is **15,179,976,192 bytes**. Subtracting 280-byte PLE
metadata and the plan's **753,139,712-byte historical full-16-bit KV budget**
leaves **14,426,836,200 bytes**. That KV number is twice an old per-rank
allocation budget, not a derived TP2 requirement or a 32K calculation.

The [official MTP option](../../own-xpu-runtime/STAGE2-PLAN.md#mtp-source-for-the-two-card-line)
uses `Qwen/Qwen3.8-Flash-Next-FP8` revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`: **2,698,026,496 stored bytes**,
from its retained tensor contract, not payload authentication in this packet.
This gives **56,002,646,016 bytes** of target+one-copy MTP weights and
**11,728,809,704 bytes** after the historical KV/metadata subtraction.
Six known MTP HC matrices need another **39,321,600 bytes** for TP2 replication,
raising packed weights to **56,041,967,616** before other replicas. MTP KV/state,
rollback and shared quantized target embedding/head interfaces need their own
binding and tests. This is a mixed-checkpoint draft configuration, never the
certified FP8 configuration; the unchanged quantized target must verify every
accepted proposal. No official MTP payload was read or downloaded here.

A separate **estimated** one-user, 32,768-token scenario uses full 16-bit KV:

| Runtime class (all estimates) | Bytes across two cards |
| --- | ---: |
| Target KV: 12 × 32768 × K/V × 2 heads × 256 × 2 bytes | 805,306,368 |
| BF16 GDN recurrent state | 56,623,104 |
| GDN convolution history | 2,211,840 |
| PLE convolution history, 10240 channels × 3 × 2 bytes | 61,440 |
| Raw and pooled QSA index, including one extra TP2 copy | 251,658,240 |
| **Live target state subtotal** | **1,115,860,992** |
| One recurrent/conv/PLE rollback copy | 58,896,384 |
| Graph/static buffer allowance, 1 GiB/card | 2,147,483,648 |
| Operator scratch allowance, 1 GiB/card | 2,147,483,648 |
| Allocator/driver reserve, 1 GiB/card | 2,147,483,648 |
| Bounded staging allowance, 256 MiB/card | 536,870,912 |

With 280 metadata bytes these estimates total **8,154,079,512 bytes** beyond
weights: **61,458,699,032 bytes** target-only, or **64,284,127,512 bytes** with
MTP plus its known HC replica and an estimated additional 88,080,384 bytes of
MTP KV/index. These scenarios leave 7,025,896,680 / 4,200,468,200 bytes under
the historical capacity. The allowances are assumptions, not measured bounds.
Additional replicas, padding, repacks, dequant buffers, prefill peaks and MTP
transaction buffers can invalidate them. Full dequantized shadows are not
included; there is **no native fit verdict**.

The **29,321,610,240 off-device bytes** exceed the two-card host's 15 GiB RAM.
A bounded file-backed lookup plan, measured I/O, host staging and driver-shadow
budget are still needed. Offloaded file bytes do not imply resident host RAM.
The checks ran on `steve-b70s`, not on the 15 GiB host.

## Reproduce and next packet

From repository root, with the existing CPU-capable environment; each command
writes only the requested packet's receipts. No dependency download is needed.

```bash
export OMP_NUM_THREADS=2
MODEL_DIR=/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS
PACKET=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1
CPU_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
nice -n 19 ionice -c 3 python3 -B "$PACKET/admit.py" "$MODEL_DIR" > "$PACKET/admission.log" 2>&1
nice -n 19 ionice -c 3 "$CPU_PYTHON" -B "$PACKET/check_samples.py" "$MODEL_DIR" > "$PACKET/samples.log" 2>&1
nice -n 19 ionice -c 3 "$CPU_PYTHON" -B "$PACKET/check_samples.py" "$MODEL_DIR" --receipt sample-repeat-receipt.json > "$PACKET/samples-repeat.log" 2>&1
nice -n 19 ionice -c 3 "$CPU_PYTHON" -B experiments/own-xpu-runtime/stage1/packet1b/run_tests.py --receipt "$PACKET/loader-test-receipt.json" > "$PACKET/loader-tests.log" 2>&1
nice -n 19 ionice -c 3 python3 -B "$PACKET/test_admission.py" > "$PACKET/admission-tests.log" 2>&1
nice -n 19 ionice -c 3 python3 -B experiments/own-xpu-runtime/stage2/packet1c/test_ranges.py > "$PACKET/range-tests.log" 2>&1
nice -n 19 ionice -c 3 "$CPU_PYTHON" -B experiments/own-xpu-runtime/stage1/packet1b/tests/compare_pinned_quant_reference.py --source-dir /home/steve/build/flash-next-iq3-baseline-20261010/llama.cpp/gguf-py/gguf --receipt "$PACKET/dequant-crosscheck.json"
nice -n 19 ionice -c 3 python3 -B "$PACKET/summarize.py" > "$PACKET/summary.log" 2>&1
```

**Next: packet 2 — this quantized model's tokenizer, production shape/operator
contract and complete CPU oracle preparation.** Bind prompt-template/token IDs
to these authenticated GGUF metadata, enumerate M1/M2/prefill shapes and exact
quantized operator semantics, and extend the oracle beyond weight samples.
Native resource admission and parity against the prepared independent baseline
remain later, separately authorized work; the host fault halt is unchanged.

No GPU, server, systemd, `/dev/dri`, port 8188, LTX unit, host setting,
download or protected-model-directory write was used. Temporary test/research
scratch was deleted; receipts, codebooks and logs are deliberate lab artifacts.
