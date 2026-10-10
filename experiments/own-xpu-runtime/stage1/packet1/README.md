# Packet 1 — CPU identity and tensor contract

**Exit gate: PASS, 2026-10-10.** The owner approved the objective and the reviewer
accepted Stage 0 for CPU work. This packet implements only packet 1 of the
[Stage 1 plan](../../STAGE1-PLAN.md): deterministic manifests, exact frozen
oracle hashes and 12 rows, dense-model structure, and malformed-header
rejection. The [check receipt](check-receipt.json) records the successful CPU
run. This does not pass Stage 1's native, output-parity or speed gates.

## Frozen identity

[identity.json](identity.json) pins official `Qwen/Qwen3.8-27B-FP8` revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, the tracked config and its receipt,
the independently fetched identical config, index, tokenizer requirements,
generation defaults and chat template. The checkpoint is dense: 64 target
layers, 48 GDN and 16 full attention, plus one native MTP block. Generic MoE
names in the publisher's exclusion list do not imply expert tensors.

The fixed suite is
`repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`, SHA256
`df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac`.
The oracle is
`experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/tp1-mtp0-b896-strict-performance.json`,
SHA256 `1ee5743c99c1c0057a9dd19ee5d452e48dd282cca893942b7e2c9e2339998283`.
Both are repository-relative paths; their historical folder names are preserved.
[oracle-token-ids.json](oracle-token-ids.json) extracts all 12 arrays without
changing order or contents: 5,904 tokens, eleven 512-token arrays and one
272-token array. Each row has its length and compact-JSON SHA256. The hash of
the ordered list of all arrays is
`e0b26cadc75857c3c56c2c2c20fe23ff794a712bff1c20f222cc59c22b711e29`.
The identity also hashes the complete derived oracle file.

The oracle used raw completions prompts, no system prompt or chat template,
temperature 0, top_p 1 and seed 42, with a natural 512-token cap. Preserve that
input policy instead of applying the publisher's sampling defaults. Config
EOS is 248044; generation metadata allows 248046 and 248044, and tokenizer EOS
is `<|im_end|>` (248046). Keep those distinct declarations. The full tokenizer
config, added-token map and regex are pinned. Vocabulary/merges files are pinned
by publisher Git blob or LFS identities without fetching them; tokenizer
execution and prompt-token parity have not been tested.

## Tensor directory and byte accounting

[tensor-contract.json](tensor-contract.json) enumerates all **1,606 tensors in
66 shards**, with exact index names, stored dtypes, shapes, contiguous strides,
data-relative and file-relative offsets, payload bytes, scale pairing,
publisher exclusions, graph component and proposed residency class. Its
ownership definitions follow [DESIGN.md](../../DESIGN.md): the directory owns
metadata/mappings, the graph component owns arithmetic, the placement plan
owns allocations, and the executor owns queues/events/graphs. MTP shares the
target embedding/head; neither is counted twice. Vision is fully counted but
unsupported for Stage 1 text execution.

| Graph component | Tensors | Payload bytes |
| --- | ---: | ---: |
| Dense FFN, target layers | 384 | 17,114,849,280 |
| GDN, target layers | 576 | 5,588,296,704 |
| Full attention, target layers | 160 | 1,677,942,784 |
| Target layer norms | 128 | 1,310,720 |
| Embedding | 1 | 2,542,796,800 |
| Full target head | 1 | 2,542,796,800 |
| Final target norm | 1 | 10,240 |
| Native MTP, including merge and norms | 22 | 477,199,744 |
| Vision, unsupported in Stage 1 | 333 | 921,460,192 |
| **All tensor payloads** | **1,606** | **30,866,663,264** |

| Future residency class | Payload bytes |
| --- | ---: |
| Card 0 target weights, excluding embedding | 26,925,206,528 |
| Card 0 native MTP weights | 477,199,744 |
| Embedding: device or host-UVA decision unresolved | 2,542,796,800 |
| Vision: not admitted | 921,460,192 |

These classes are accounting, not a placement decision or proof of fit. No
allocation was made. KV/recurrent state, graph/static buffers, scratch, staging,
host shadows and allocator overhead are outside the checkpoint tensor total.
They still need a future admission census.

The **30,866,663,264 payload bytes + 203,664 header/prefix bytes =
30,866,866,928 package bytes**, exactly matching the pinned package manifest
and publisher file metadata. There is no unexplained byte difference.
Stored FP8 E4M3 payload is 24,699,207,680 bytes; BF16 is 6,167,455,584 bytes.
There are no stored FP16 or FP32 tensors in this revision. BF16 exclusions
remain BF16 storage; the certified W8A16 execution profile separately requires
FP16 activations/KV and FP32 GDN state. No dtype conversion is implemented here.

## Findings and negative-result record

- All **407 block-scale tensors are BF16**, with publisher suffix
  `weight_scale_inv` and 128×128 blocks. The plan's kernel-budget example used
  F32 scales. A 17,408×5,120 matrix plus its actual stored scales is
  **89,139,840 bytes**, not 89,150,720. The plan is retained unchanged; the
  contract records the exact storage. Numerical scale application and cast
  order still need packet 2's known-value fixtures.
- HF's parameter summary excludes 1,507,520 BF16 scale elements
  (**3,015,040 bytes**). It agrees exactly after those elements are subtracted
  from the complete header census. Do not use parameter count as file size.
- Publisher exclusion aliases are not a graph. The actual embedding is
  `model.language_model.embed_tokens.weight`, while the exclusion list names
  `model.embed_tokens`. The final target norm also has no direct exclusion
  entry. Both are independently checked against their BF16 headers and
  config-derived shapes as non-linear-projection tensors. No expert/router
  tensors exist despite the generic exclusion names.
- During checker development, strict guards exposed those alias/final-norm
  distinctions and the HF summary's omission of scales. They were reconciled
  explicitly rather than weakening the tensor coverage or size checks.
  No native experiment or performance result was produced.

## Re-run the CPU check

From the repository root:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 experiments/own-xpu-runtime/stage1/packet1/contract-checks.py
```

The default check is offline and read-only. It uses Python's standard library,
checks source hashes, independently derives every tensor's name/shape/dtype
from config, validates index/header coverage, checked products and offset bounds,
scale shapes and exclusions, package totals, prompt hashes and token arrays.
It regenerates manifests twice in memory and requires identical serialized
bytes. The [35 synthetic parser fixtures](parser-fixtures.json) include four
valid cases and 31 malformed/unsupported cases: duplicate keys, truncation,
invalid types, overflow, overlaps, gaps, wrong sizes and unknown encodings.
They contain only header descriptions, no tensor payload or operator fixtures.
GGUF, INT4, alternate FP8 encodings/block sizes, unknown tensors/dtypes,
zero-size tensors and pickle/model-supplied Python are unsupported here.

To write a fresh receipt after a successful check:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 experiments/own-xpu-runtime/stage1/packet1/contract-checks.py --receipt experiments/own-xpu-runtime/stage1/packet1/check-receipt.json
```

`--write-contracts` reconstructs the three derived JSON files from the retained
metadata; it is not needed for verification. The metadata acquisition command
used for this packet was:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 experiments/own-xpu-runtime/stage1/packet1/fetch-metadata.py
```

That optional command refreshes the metadata snapshots and retrieval receipt;
the Hub API also includes mutable repository statistics, so a refresh may
change its hash even at the same model revision. It never fetches tokenizer
vocabulary, merges or weight payloads. Each safetensors request reads exactly
the 8-byte length or the bounded JSON header. It refuses any response lacking
the exact HTTP 206 range and content length before reading its body.

## Provenance and command receipt

| Files | Provenance |
| --- | --- |
| `metadata/hf-model-info.json` | Official revision-pinned HF API file sizes, blob/LFS hashes and aggregate parameter summary; retained raw response |
| `metadata/config.json`, index, tokenizer config, generation config, chat template | Official pinned metadata; raw bytes checked against HF Git blob identities; config also equals the tracked Stage 0 copy |
| `metadata/headers/*.json` | Exact padded JSON header bytes, no tensor payload; each range, prefix, size, hash and publisher shard identity is in [fetch-receipt.json](metadata/fetch-receipt.json) |
| `fetch-metadata.py` | Original lab metadata fetcher, following the [official safetensors metadata format](https://huggingface.co/docs/safetensors/main/en/metadata_parsing); no external runtime code imported |
| `contract-checks.py`, `parser-fixtures.json` | Original lab CPU contract, independent config shape formulas, and synthetic malformed-header cases |
| `identity.json`, `tensor-contract.json`, `oracle-token-ids.json` | Deterministically derived by `contract-checks.py --write-contracts` from the pinned sources above and the tracked suite/oracle |
| `check-receipt.json` | Successful offline check; exact command, time, host, nice/thread settings, input/script hashes, parser results and totals |
| This README, stage index, lane status and current-state paragraph | Lab-authored packet summary derived from the plan and check receipt |

The [official revision](https://huggingface.co/Qwen/Qwen3.8-27B-FP8/tree/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a)
is the sole remote model source. The fetch retained 497,124 metadata bytes,
plus 528 prefix bytes represented as hex in its receipt. Publisher shard
hashes are metadata identities, **not locally verified payload hashes**.
No GPU, server, systemd unit, port 8188, device node, native compilation,
weight download or storage change was used. No scratch directory was created;
all new files are intentional packet artifacts. Work stops at packet 1.
