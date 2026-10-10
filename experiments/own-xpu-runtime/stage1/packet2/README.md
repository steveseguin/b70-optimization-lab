# Packet 2 — official weight admission and loader/shape census

**Exit gate: PASS for CPU packet 2, 2026-10-10.** The
[gate receipt](exit-gate.json) binds the complete publisher hash check, exact
tensor reconciliation, CPU known-value/packing checks, fresh-process repeat,
M1/M2/M6 linear shape census and admitted disk/host budget. This is not native
memory admission, device arithmetic parity, inference qualification or a speed
result. Packet 4's U1–U7 comparator checks remain open.

The owner corrected the storage premise: the USB disk was unmounted when
packet 1 ran. Official `Qwen/Qwen3.8-27B-FP8` revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` already exists at
`/mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7`;
the `/mnt/fast-ai/llm-models` aliases point into that disk. The direct directory
was read successfully here. No transfer, download, mount or storage change
was needed. See the correction addenda in [STORAGE](../../STORAGE.md) and
[the plan](../../STAGE1-PLAN.md).

## Complete file and tensor receipts

[admission-receipt.json](admission-receipt.json) records each file's SHA256,
bytes, elapsed hashing seconds, Git blob SHA1, expected publisher identity and
size/mtime stability. The directory inventory remained unchanged across the
run. Hashing streamed in 4 MiB chunks at nice 19, idle I/O priority and
`OMP_NUM_THREADS=2`; total per-file hashing time was 75.28 seconds and peak
process RSS was 29,900 KiB. That is a file-check receipt, not a disk benchmark.

| File class | Count | Bytes | Verdict |
| --- | ---: | ---: | --- |
| Publisher LFS (66 safetensors shards and tokenizer.json) | 67 | 30,879,676,248 | All SHA256 and sizes match |
| Publisher small files | 14 | 10,373,349 | All Git blob hashes and sizes match; SHA256 recorded |
| Local `.cache` metadata/lock files | 83 | 9,960 | SHA256 recorded; no publisher identity claimed |
| **Whole directory** | **164** | **30,890,059,557** | **No missing or mismatching publisher files** |

The recipe's [model-direct.json](../../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json)
and packet 1's retained [HF metadata](../packet1/metadata/hf-model-info.json)
agree for every shared entry. The HF metadata additionally identifies the
empty `safetensors-md5sum.txt`; it was checked too. Small files are authenticated
with the publisher's Git object identity (`SHA1("blob <size>\0" + contents)`),
not an invented publisher SHA256. Their locally measured SHA256s are now pinned.
No network metadata refresh was performed.

[tensor-census.json](tensor-census.json) contains the independently parsed real
headers, exact offsets and sizes, plus packet 1's component/exclusion labels
only after reconciliation passed. The packet 1b `safetensors_header` and
`validate_contract` loaders checked **1,606 tensors in 66 shards**:
no missing, unexpected or duplicate names; no dtype, shape, data/file offset,
payload size or scale-pair differences; no overlapping, gapped or trailing
payload extents. The local index itself also passed its publisher hash.

Total tensor payload is **30,866,663,264 bytes**; header/prefix bytes are
**203,664**, giving **30,866,866,928 safetensors bytes**, exactly the recipe's
weight total. Tokenizer and other metadata are outside that weight total.

## FP8 scale convention and bounded real fixtures

All **407** FP8 weights have `[N,K]` row-major `F8_E4M3` storage and paired
BF16 `weight_scale_inv` tensors of shape `[N/128,K/128]`. Every dimension is
divisible by 128 in this checkpoint; the scales occupy **3,015,040 bytes**.
The real shapes and offsets establish one scale per aligned 128×128 block,
with K contiguous, without padding or a hidden per-row scale.

The decoded convention is:

```text
value[n,k] = float32(E4M3FN(weight_byte[n,k]))
             * float32(BF16(weight_scale_inv[n//128,k//128]))
CPU W8A16 reference weight = round_to_FP16(value[n,k])
```

The suffix `_inv` does not request division. Shapes alone cannot logically
distinguish multiplication from division; the
[pinned source excerpt](scale-source-evidence.json) corroborates multiplication
by passing the stored tensor directly as the oneDNN weight scale. This is the
already-reviewed packet 1b S2 wrapper at `e421889999bc1e5a5f11044d14548b9afdba644d`,
not code adopted as our runtime. Independent scalar decoding and known values
test the convention against packet 1b's CPU reference. They do not establish
the internal fused oneDNN cast/reduction order or recover pre-quantization weights.

One real example is layer 0 GDN `in_proj_qkv.weight[0,0]`: byte `0xee`
decodes to **−112**; BF16 scale bits `0x3949` decode to
**0.00019168853759765625**. Their product is exactly
**−0.0214691162109375**, matching both the independent scalar calculation and
the reference. The receipt includes explicit values on both sides of row and
column 127→128 and the last block of every sampled projection.

[sample-receipt.json](sample-receipt.json) and its
[fresh-process repeat](sample-repeat-receipt.json) cover:

- All 256 E4M3FN byte encodings, including subnormals, signed zero, 448 and the
  two NaN encodings; a synthetic 256×256 boundary fixture with four distinct
  BF16 scales and independently calculated FP32 and FP16 products.
- **20 real FP8 projections, 40 windows:** every projection in target GDN
  layer 0, target full-attention layer 3 and the native MTP block, including
  their gate/up/down FFNs. Each reads the top-left 256×256 tile and last
  128×128 block. Scalar products, reference dequantization, row-major ↔
  block-major packing and same-process repeats match byte for byte.
- **All 792 non-scale BF16 tensors**, including every exclusion and vision
  tensor (vision remains unsupported for execution). Small tensors are checked
  whole; larger tensors use deterministic first/middle/last flat ranges.
  Embedding and head use full rows 0, 127, 128 and 248319. Exact BF16 widening
  and round-trip repacking pass; the reference FP16 cast is recorded separately.
- Raw, packed, scale and decoded hashes; finite/zero counts, min/max, mean and
  RMS values; sample ranges and real known-value coordinates. All real sampled
  values and reference FP16 casts are finite. Each sample run reads only
  **2,699,464 model bytes**, with peak RSS below 764 MiB.

Both fresh CPU processes produce content SHA256
`a3ae662eefca02c013a6504806c23e58029f736efac7877cd17a4cef415414be`.
Sampling validates the loader convention on the declared ranges; it is not a
claim of full-checkpoint numerical execution or full-tensor finiteness scanning.
The complete files, unlike the numerical samples, were fully hashed.

## Shape census and one-card arithmetic

[shape-census.json](shape-census.json) enumerates **505 text/MTP linear
matrices**, **1,515 M1/M2/M6 rows** and **30 unique (M,N,K,dtype) shapes**,
including BF16 gate projections, MTP merge and the full target head.
Embedding gather bytes are separate. Each row includes exact stored weight
and scale bytes, minimum FP16 input/output bytes, `2MNK` dot operations and
one unfused logical call. Native launches, actual traffic and timing are null:
these cannot be measured in this CPU-only packet. The historical 507 GB/s
division is explicitly planning arithmetic, not a measured kernel time.

[memory-admission.json](memory-admission.json) separates exact checkpoint
payloads from all estimated runtime classes:

| Resident component | Exact bytes |
| --- | ---: |
| Target dense FFN | 17,114,849,280 |
| Target GDN weights and parameters | 5,588,296,704 |
| Target full-attention weights and parameters | 1,677,942,784 |
| Target layer norms | 1,310,720 |
| Final norm | 10,240 |
| Full target head | 2,542,796,800 |
| Native MTP weights | 477,199,744 |
| Embedding | 2,542,796,800 |
| **One card, all text/MTP weights including embedding** | **29,945,203,072 (27.889 GiB)** |
| **Alternative card weights excluding embedding** | **27,402,406,272 (25.520 GiB)** |
| Vision, not admitted for Stage 1 | 921,460,192 |

MTP shares the embedding/head, each counted once. These are stored-weight
allocation sizes, not measured GPU residency. No full dequantized checkpoint,
second packed copy or draft shortlist is silently included. The separate
embedding/UVA alternative still needs a working, qualified placement path.

At one user and 32,768 tokens, estimated FP16 KV is 2,147,483,648 bytes for
the target and 134,217,728 for MTP. Estimated FP32 GDN state is 150,994,944;
FP16 three-tap conv state is 2,949,120; one rollback copy adds 153,944,064.
Provisional graph/static, workspace, device staging and allocator/driver
allowances are 256, 512, 128 and 512 MiB respectively. **All these runtime
classes are estimates**, with no device allocation or peak measurement.

Those estimates total **4,065,984,512 bytes** beyond weights. The all-resident
scenario totals **34,011,187,584 bytes**, leaving only **348,550,784 bytes**
against a nominal 32 GiB capacity. At a decimal 32 GB it does not fit; both
sensitivities are recorded without querying the GPU. Actual usable capacity,
graphs, scratch, rollback count and host shadows can invalidate this budget.
**Native one-card admission remains unproven.** Context is not reduced and
KV is not compressed to force a fit.

The CPU packet's host budget allows the entire 30.890 GB directory in page
cache plus 2 GiB anonymous memory and an 8 GiB reserve, below the observed
117.29 GB available RAM. Hashing actually peaked at 29,900 KiB and samples at
781,976 KiB. The repository had 69.71 GB free versus a 50 GiB reserve and a
16 MiB artifact allowance. The model filesystem had 378.04 GB free; even
allowing the entire unrelated 82 GB download plus 50 GiB reserve clears the
read-only sensitivity check. No checkpoint copy or write was made. These are
dated snapshots, not reservations or permission for later allocations.

## Reproduce and provenance

From the repository root, using the existing CPU-capable torch environment:

```bash
env OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 python3 -B experiments/own-xpu-runtime/stage1/packet2/admit.py /mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7 > experiments/own-xpu-runtime/stage1/packet2/admission.log 2>&1
env OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet2/check_samples.py /mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7 > experiments/own-xpu-runtime/stage1/packet2/samples.log 2>&1
env OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet2/check_samples.py /mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7 --receipt sample-repeat-receipt.json > experiments/own-xpu-runtime/stage1/packet2/samples-repeat.log 2>&1
env OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet1b/run_tests.py --receipt experiments/own-xpu-runtime/stage1/packet2/loader-test-receipt.json > experiments/own-xpu-runtime/stage1/packet2/loader-tests.log 2>&1
env OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 python3 -B experiments/own-xpu-runtime/stage1/packet2/summarize.py
```

`admit.py`, `check_samples.py` and `summarize.py` are original lab code.
Receipts hash their source and dependencies, the pinned manifests, actual
census, and packet 1b's unchanged reference/loader. `summarize.py` additionally
reads the already-present S2 source Git object listed in the source receipt;
it does not download or execute it. The generated files are data receipts,
not model payload copies. No synthetic or sampled outputs qualify inference.

The existing packet 1b regression suite passed **97 tests** with the same priority
and CPU thread limits; [test receipt](loader-test-receipt.json) and
[log](loader-tests.log) retain the result. Its temporary synthetic directories
clean themselves up. No packet scratch or pycache remains. No GPU, server,
systemd, `/dev/dri`, port 8188, LTX unit, host setting or protected model/cache
write was used. The unrelated download and existing lanes were untouched.

Findings retained: the old missing-weight premise was a mount-state mistake;
stored scales are BF16 multipliers despite `_inv`; all tensor bytes reconcile;
32K all-resident planning has a narrow margin and does not establish native
fit. There are no failed hash or contract arms to conceal. The next stage
remains subject to the host halt and separate native authorization.
