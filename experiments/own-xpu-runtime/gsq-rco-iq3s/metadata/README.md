# SC117 GSQ-RCO IQ3_S header compatibility

**Header census passed; engine execution remains unqualified.** Both models contain the same 1,224 tensor names and dimensions, including 48 target layers and no MTP/draft tensors. Storage types differ for 695 tensors. This is a separate modified model; old token or checkpoint output is not its correctness oracle.

The candidate is `SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF` revision `eec4e10a2c29b440a2ae85591fa11569ce752963`, IQ3_S two-shard variant. Download/readback hashes are inherited from the existing download completion record, not recomputed here. The comparator is the existing three-shard Unsloth UD-IQ3_XXS at revision prefix `766911a6`. SC117 supplies the modified release; its embedded GGUF provenance still names ISTA DASLab. The model card describes transplanted residual projections and learned GSQ/RCO quantization. These payload/provenance claims were not independently verified by header inspection.

## Exact metadata boundary

All `qwen4exp.*` architecture/PLE values and all `tokenizer.*` values match. Arrays were compared using complete canonical JSON SHA256 values, not displayed first/last samples. The full chat-template string is retained and compared. Geometry remains qwen4exp, 48 layers, embedding 2,560, 512 experts/top10, vocabulary 248,320 and advertised context 262,144. Tokenizer EOS remains 248046; PLE EOS remains 248044. This does not admit an inference context capacity.

No metadata keys were added or removed after excluding only shard-specific `split.*` bookkeeping. Every other field was compared. Eight differences are `general.file_type`, `general.name`, `general.quantized_by`, `general.repo_url`, `general.tags`, and `quantize.imatrix.file`, `.dataset`, `.chunks_count`. There are no new GSQ codebook/scale metadata keys or additional scale tensors. This does not establish equality of tensor bodies.

## Storage types

Candidate files total 83,863,586,496 bytes versus 81,961,823,936 bytes: +1,901,762,560 bytes. The model-level IQ3_S label does not mean every tensor uses IQ3_S.

| Type | Old tensors | New tensors | New payload bytes |
| --- | ---: | ---: | ---: |
| BF16 | 24 | 484 | 1,527,889,920 |
| F16 | 0 | 1 | 81,920 |
| F32 | 557 | 292 | 10,063,360 |
| IQ2_S | 94 | 40 | 10,747,904,000 |
| IQ3_S | 2 | 20 | 7,208,960,000 |
| IQ3_XXS | 0 | 34 | 10,918,297,600 |
| IQ4_NL | 49 | 40 | 47,202,647,040 |
| IQ4_XS | 0 | 45 | 1,398,906,880 |
| Q2_0 | 0 | 9 | 2,123,366,400 |
| Q4_K | 0 | 43 | 163,307,520 |
| Q5_K | 0 | 31 | 303,677,440 |
| Q6_K | 250 | 89 | 1,361,740,800 |
| Q8_0 | 248 | 96 | 885,719,040 |

## Projection roles

Dimensions in JSON are GGUF fastest-first; `shape` is their row-major reversal. Full role/type/byte inventories are retained in both censuses.

| Role | Old types/counts | New types/counts | New payload bytes |
| --- | --- | --- | ---: |
| `output.weight` | Q6_K ×1 | Q6_K ×1 | 521,472,000 |
| `token_embd.weight` | Q6_K ×1 | IQ4_XS ×1 | 337,715,200 |
| `per_layer_token_embd.weight` | IQ4_NL ×1 | IQ4_NL ×1 | 28,800,138,240 |
| `blk.*.attn_qkv.weight` | Q6_K ×35, Q8_0 ×1 | IQ4_XS ×2, Q4_K ×2, Q5_K ×10, Q6_K ×22 | 710,656,000 |
| `blk.*.attn_gate.weight` | Q6_K ×35, Q8_0 ×1 | IQ4_XS ×8, Q4_K ×10, Q5_K ×4, Q6_K ×14 | 379,207,680 |
| `blk.*.ssm_out.weight` | Q6_K ×36 | Q8_0 ×36 | 601,620,480 |
| `blk.*.attn_q.weight` | Q6_K ×12 | IQ4_XS ×3, Q4_K ×1, Q5_K ×3, Q6_K ×5 | 261,734,400 |
| `blk.*.attn_k.weight` | Q6_K ×12 | IQ4_XS ×1, Q6_K ×11 | 12,523,520 |
| `blk.*.attn_v.weight` | Q6_K ×12 | Q5_K ×2, Q6_K ×10 | 12,554,240 |
| `blk.*.attn_output.weight` | Q6_K ×12 | Q8_0 ×12 | 200,540,160 |
| `blk.*.ffn_gate_exps.weight` | IQ2_S ×47, IQ3_S ×1 | IQ2_S ×20, IQ3_S ×10, IQ3_XXS ×17, IQ4_XS ×1 | 14,883,225,600 |
| `blk.*.ffn_up_exps.weight` | IQ2_S ×47, IQ3_S ×1 | IQ2_S ×20, IQ3_S ×10, IQ3_XXS ×17, IQ4_XS ×1 | 14,883,225,600 |
| `blk.*.ffn_down_exps.weight` | IQ4_NL ×48 | IQ4_NL ×39, Q2_0 ×9 | 20,525,875,200 |
| `blk.*.ffn_gate_shexp.weight` | Q6_K ×47, Q8_0 ×1 | IQ4_XS ×15, Q4_K ×16, Q5_K ×4, Q6_K ×13 | 49,779,200 |
| `blk.*.ffn_up_shexp.weight` | Q6_K ×47, Q8_0 ×1 | IQ4_XS ×13, Q4_K ×14, Q5_K ×8, Q6_K ×13 | 50,700,800 |
| `blk.*.ffn_down_shexp.weight` | Q8_0 ×48 | Q8_0 ×48 | 83,558,400 |
| `blk.*.ple_conv1d.weight` | F32 ×1 | F16 ×1 | 81,920 |

`output.weight`: Q6_K, `[2560,248320]`, 521,472,000 bytes. `token_embd.weight`: IQ4_XS, the same dimensions, 337,715,200 bytes. PLE table remains IQ4_NL, `[160,320001536]`, 28,800,138,240 bytes. Q2_0 appears only in expert-down layers 1, 8, 10, 12, 13, 20, 21, 30 and 36: each `[640,2560,512]`, 235,929,600 bytes. Gate/up type assignments match within each layer. Many HC/router/alpha/beta matrices changed to BF16; PLE convolution changed F32→F16. Type-specific loader, expanded-layout, conversion and dispatch checks must be regenerated; existing type whitelists/configuration are not reusable admission.

## Parser and provenance

`census.py` reuses the frozen packet1b bounded Reader, metadata decoder, type map and shard validator. The inherited parser initially refused raw GGML type42 at `blk.1.ffn_down_exps.weight`. The additive wrapper records that refusal and adds Q2_0 format knowledge without editing the parent. Authoritative local llama.cpp HEAD is `23b0202a189c44a54625aadcb37a946dd1d6278d`; the three named format files were clean relative to that HEAD when inspected. Full file hashes are retained. `ggml.h` assigns Q2_0=42; `ggml-common.h` defines 64 elements, one fp16 scale and 16 packed code bytes (18 bytes/block); `ggml-quants.c` decodes four adjacent 2-bit codes per byte as `(code-1)*scale`. This credits format knowledge, not adoption or execution of an external runtime.

Unknown IDs would remain opaque reserved directory spans, not invented payload sizes; none remain in the actual censuses. Known block divisibility, reserved extents, alignment, file bounds, split coverage and unique names passed. The wrapper refuses malformed metadata/duplicates, nonfinite values, truncation and illegal extents. It uses unbuffered read-only descriptors, regular-file and stable inode/size/timestamp checks, and hashes exactly parser-requested bytes. It read 22,049,047 header bytes across five shards, zero padding/payload bytes. No model load, mmap, native executable, device enumeration, service or setting change occurred.

## Files and reproduction

- [new-census.json](new-census.json), [old-census.json](old-census.json): `metadata[key]={gguf_type_id,value,canonical_json_sha256}`; large arrays carry full canonical hash/count plus samples. `tensors[name]` records raw type ID/name, dimensions, reversed shape, elements, payload bytes, shard, absolute file offset and reserved span. `by_type` and `by_projection_role` give counts/bytes/type distributions.
- [compatibility-delta.json](compatibility-delta.json): complete name/shape/type and metadata differences, equal keys and type-transition counts.
- [receipt.json](receipt.json): source identity, exact header hashes and download provenance binding.
- [tests-receipt.json](tests-receipt.json), [tests.log](tests.log): 12 bounded CPU tests: eight malformed/header-only/aggregation controls and four retained-artifact checks. No payload replay.

The artifacts total about 1.3 MB and intentionally retain every tensor directory entry. They support loader/dispatch planning and tiny future decoder-slice selection without scanning bodies. They are permanent research metadata; Git restores them. They contain no weights and do not replace full-model hashes. Re-execution uses exclusive outputs and refuses overwriting existing censuses:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
taskset -c 8-15,24-31 nice -n 19 /home/steve/.venvs/vllm-xpu/bin/python -B \
experiments/own-xpu-runtime/gsq-rco-iq3s/metadata/census.py
```
