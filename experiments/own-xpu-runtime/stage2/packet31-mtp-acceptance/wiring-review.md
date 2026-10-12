# Independent MTP wiring review

This review was derived from source before receiving any acceptance result or proposed implementation. It ran no model, device API, vLLM import, or kernel. All source access was read-only. The repository overlay is the primary model-definition evidence. Missing implementation dependencies were read from `/home/steve/src/vllm-current-main`, whose HEAD is `6d8724577dabbee5fa0bbc70c4d927c6174c8d8a`, the source identity named in the retained full-precision-lane records. This review establishes architectural wiring and observable numerical boundaries; it does not certify CPU/device bit parity.

## Position alignment and initialization

Let target position `p` consume `x_p`, produce final four streams `H_p`, and emit greedy `x_(p+1)`. The usable draft is

`D_(p+1) = head(MTP(H_(p-1), embed(x_p)))`.

The MTP cache/RoPE position for that row is **p-1**, not p. PROPOSER 496-499 explicitly says hidden at P and token P+1 draft token P+2. PROPOSER 762-778 shifts input IDs left one, fills the final row with the next sampled token (or next prefill token for chunked prefill, 754-760), and copies target positions unchanged. PROPOSER 306 copies the target hidden-state tensor without a corresponding shift.

Consequently the first MTP row is `(H_0, x_1)` at cache position 0. There is no zero-hidden fictitious row. Process these rows in order across the prompt and generated continuation, retaining every MTP K/V and raw-indexer key. With N prompt tokens, the draft for the first generated token x_N comes from `(H_(N-2), x_(N-1))`; the final prompt target row `(H_(N-1), x_N)` drafts the second generated token. This causal indexing also makes copy-current and next-next-token controls useful.

## Streams, merge and final head

TARGET 581-592 calls the final mixer `combine_and_mix` and keeps its returned `multi_hidden` before the mixer collapse. This materializes the pending layer-47 MoE residual injection. Dumping the earlier delayed-combine state would be wrong. TARGET 850-851 exposes that exact multi-stream buffer for MTP.

HC 10-12 and GROUPNORM 14-16 specify stream-major layout: four contiguous 2560-element streams, hidden dimension innermost. MTP 298-313 normalizes the embedding, projects it with `fc_embedding`, normalizes the **flattened 10240-element** hidden row once, reshapes it into four streams, then applies the same `fc_hidden` to each stream. `prev_block_output=inputs_embeds`, `prev_injection=None` is a unit broadcast residual combine in HC 273-294. An equivalent materialized merge is BF16(`fc_hidden(norm10240(H)) + fc_embedding(norm2560(embed(x)))`) per stream.

MTP 218-225 creates one full-attention layer at logical layer 48. TARGET 195-198 selects PLE only for configured layer IDs; CONFIG has PLE layer 2, so this draft layer has no PLE. MTP 336-347 materializes the final draft residual then invokes its own HC final mixer. There is no additional final RMSNorm between that mixer output and the shared output head. MTP 399-415 binds a separate `ParallelLMHead` when `tie_word_embeddings=false`, and CONFIG 97 says no dedicated MTP embeddings. Thus IQ3-target embedding/head bindings are a deliberate mixed-checkpoint draft variant; official BF16 rows provide a separate binding control.

## Norms and hyper-connections

All norms read directly from the official checkpoint are **Gemma offset weights**, meaning a learned gain `1+w`, with epsilon 1e-6:

- embedding pre-norm: 2560 elements; hidden pre-norm: all 10240 elements (MTP 236-241; NORM 132-160);
- HC attention/MLP/final-mixer norms: independently per 2560-element stream, with distinct affine weights for each stream (HC 121-133; GROUPNORM 74-88);
- QSA query/key norms: per 256-element head (QSA 248-249);
- indexer query/key norms: per 128-element head (INDEXER 141-147).

REFERENCE uses direct multiplicative gains because **GGUF already stores 1+w** (REFERENCE-NOTES 47-49). Passing raw official safetensor norm values to `reference_gguf.norm(..., unit=False)` is therefore incorrect. Prefer `unit=True` on raw official weights; precomputing 1+w in BF16 introduces an extra rounding boundary.

HC mixing is grouped norm; low-rank down projection; divide by four then SiLU; BF16; up projection; sigmoid-gated stream mean. Injection is `2*sigmoid(inject/4)` times the branch output, added to the original streams. Final mixer has no outgoing injection. HC 242-310 and HCOPS 89-157, 210-225 give these boundaries. The served HC Triton norm uses `y=x*rrms; y += y*w` (HCOPS 45-48), which need not be bit-identical to a CPU reassociation `x*rrms*(1+w)`. This is a numerical parity qualification, not a stream-order ambiguity.

## QSA cache and indexer

QSA 200-249 creates 24 query heads, two KV heads, head width 256, scale 1/16, sigmoid attention output gates, and Gemma Q/K norms. NEXT 366-385 splits the query projection **per head** into 256 Q and 256 gate elements, then normalizes Q/K and applies RoPE. CONFIG's partial rotary factor is 0.25, giving 64 rotary coordinates and theta 10,000,000; text positions use the same temporal/height/width position.

QSA 276-287 explicitly requires BF16 K/V and sets no KV-sharing target. INDEXER 153-166 allocates its own raw and compressed side caches. INDEXER 233-322 projects four 128-dimensional index queries plus one 128-dimensional raw key, normalizes/rotates queries, stores raw keys, pools complete chronological groups of four, then normalizes/rotates pooled keys using each group's first position. INDEXER 342-351 selects compressed blocks and expands them to token positions, with incomplete tail positions retained. CONFIG 21-25 fixes budget 2048, ratio four. The draft never uses target K/V or target indexer keys. All chronological prompt rows matter even when only generated rows are scored.

## MoE FP8/BF16 boundaries

CONFIG 101-102 fixes 512 routed experts, top ten; intermediate width 640; a shared width-640 expert is also present. NEXT 125-181 uses BF16 router/shared gate, top-k renormalization (default true), and the shared expert. The official quantization config uses dynamic FP8 activations with 128x128 weight blocks (CONFIG 155-162). CONFIG 1087-1106 excludes all MTP dense/HC/QSA/router/shared-expert projections from conversion. Only routed expert projections use E4M3 FP8 weights and block scales.

The quantity named `weight_scale_inv` is a **multiplicative dequantization scale**, not a number to reciprocate (FP8 355-356; MOE 492-566). The standard routed path quantizes the input per row in groups of 128 before gate/up; rounds gate/up outputs to BF16; applies SiLU(gate)*up into BF16; quantizes that product per expert in groups of 128 again before down; computes FP32 block-scaled dot sums; multiplies each down accumulator by its router weight **before** BF16 rounding; then sums routed expert results (MOE 1779-1874 and 598-608). This differs from first BF16-rounding an unweighted down projection and multiplying its probability afterward.

MOEUTILS 223-246 connects block FP8 to `per_token_group_quant_fp8`. QUANT 104-117 gives FP32 scale `max(abs(group),1e-10) * (1/448)`, E4M3 clamp/round, and FP32 scale storage; QUANT 534-615 confirms group and dtype rules. XPU contiguous inputs dispatch to a compiled quantization op at QUANT 598-615. The Python/Triton formula establishes semantics, but a CPU-only review cannot certify every device reciprocal, transcendental, dot accumulation or router tie bit. The reference's `Linear` docstring at REFERENCE 56-60 explicitly calls its FP8 dequant-to-BF16 dot a surrogate. Using it unchanged must not be labelled the exact served FP8 draft.

## Checks required of the measurement

1. Seal target greedy tokens and retained layer-47 stream bytes independently of the draft.
2. Use materialized pre-final-mixer four-stream state, global MTP hidden pre-norm, official offset-weight norms, stream-major layout, and p-1 cache position.
3. Populate all shifted prompt rows and maintain independent draft K/V and indexer caches for each variant/prompt.
4. Report primary `x_(p+1)` equality, copy-current `x_p`, and next-next `x_(p+2)` controls; do not shift results to maximize agreement.
5. Distinguish official FP8 weight semantics from a BF16-dequantized surrogate and from requantized-int8 draft. CPU numerical choices and lack of device parity remain explicit limitations.
6. A device overlap implementation still needs rollback/isolation of speculative target state and exact-target verification. Acceptance alone cannot certify scheduling, cache ownership or output identity.

## Source SHA-256 receipts

Source keys above refer to these exact files. Hashes cover source/config bytes only, not model tensor payloads; the measurement's build receipt must separately bind all payloads it reads.

- **MTP**: `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay/vllm/models/qwen4_exp/nvidia/mtp.py`
  SHA-256 `d1ba61dd9843e536fff1933b2dca18d92a308d6d7516f0c6ff73ce1b56ea963c`
- **TARGET**: `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay/vllm/models/qwen4_exp/nvidia/model.py`
  SHA-256 `72578443c9470fb6251ea33f4b02bcbd9e2dd2f4870ab06ec927848af0145b0f`
- **HC**: `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay/vllm/models/qwen4_exp/nvidia/hyperconnection.py`
  SHA-256 `15eaf5683f62dca162eb8a1825b632598f60b230ceaf56b8611a338cb1315663`
- **PROPOSER**: `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay/vllm/v1/worker/gpu/spec_decode/autoregressive/speculator.py`
  SHA-256 `5f688e3972a0a7491ecfa786135d2fa0e1a5aa148e97a9ef3cf507cff6dbe171`
- **FP8**: `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay/vllm/model_executor/layers/quantization/fp8.py`
  SHA-256 `dd1a2cc2d89d694ecde7cca16c82aebf61eaed08babb516c955075be9f7186cf`
- **MOE**: `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay/vllm/model_executor/layers/fused_moe/fused_moe.py`
  SHA-256 `f5252f843722ea91149b1e93c60e67318957d552ff1cf8014d15909ef30b5542`
- **QSA**: `/home/steve/src/vllm-current-main/vllm/models/qwen4_exp/nvidia/qsa.py`
  SHA-256 `cb55fe5520665dddb11172060e2b76d10e8a5888878931df749e2b60edecad3d`
- **INDEXER**: `/home/steve/src/vllm-current-main/vllm/models/qwen4_exp/nvidia/indexer_qsa.py`
  SHA-256 `668706c3a59c51e2c1ed51d19bd9a0e1564a0aad68c5e2bc20d5fb9e65cc2f98`
- **HCOPS**: `/home/steve/src/vllm-current-main/vllm/models/qwen4_exp/nvidia/ops/hc.py`
  SHA-256 `1de6e4780d25aecbaf3e36394cef4ac8d58375c708cc41891be36577341393fc`
- **GROUPNORM**: `/home/steve/src/vllm-current-main/vllm/models/qwen4_exp/common/hyperconnection.py`
  SHA-256 `cf2028bbd7dceb33f78393be62e3c936c29aff7255dc185f211d1e57cb007393`
- **NORM**: `/home/steve/src/vllm-current-main/vllm/model_executor/layers/layernorm.py`
  SHA-256 `ef94ccd617c284e0fcd01b92a741b9262d343a02110cefc71dbf3e4c22356c44`
- **NEXT**: `/home/steve/src/vllm-current-main/vllm/model_executor/models/qwen3_next.py`
  SHA-256 `83443032ab61e107a3f2245a0b91cb96c5be8c0c7d12f4717946caf5bb7c2cf5`
- **MOEUTILS**: `/home/steve/src/vllm-current-main/vllm/model_executor/layers/fused_moe/utils.py`
  SHA-256 `b7caa965a90a590978852ff1844e59c5d854bb08f7b1c216e5bc1d23331e7788`
- **QUANT**: `/home/steve/src/vllm-current-main/vllm/model_executor/layers/quantization/utils/fp8_utils.py`
  SHA-256 `f3018a467d0af630a71ca8b0073d0fe4ab93ce1d88baf44bbc9ff096adf8240d`
- **CONFIG**: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8/config.json`
  SHA-256 `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`
- **REFERENCE**: `experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/reference_gguf.py`
  SHA-256 `08cf7aeb3e55601fb63ce60a84b299897e174678ef1277388716c7844741f47b`
- **REFERENCE-NOTES**: `experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/README.md`
  SHA-256 `9fc74bbee7ff6b984152f6b23692d678d2e4ca66ba8246bdf5d79b80773a4242`

## Independent review of the packet31 CPU implementation

The initial implementation review read `draft_reference.py` after the architectural review above. No implementation code was changed by the reviewer. Findings were sent to the implementing agent before generated-position scoring. The reviewed implementation's core wiring is consistent with the source: offset-weight norms, global hidden pre-norm, unit embedding residual, independent QSA state, per-head query/gate packing, separate MTP HC mixers, ten routed experts and the shared expert, and full target-bound head.

Two fixable BF16 boundaries were identified in the initial version:

- `reference_gguf.qsa` multiplies the BF16 attention output by `sigmoid(gate.float())` directly. The served QSA source, QSA 423-426, computes `torch.sigmoid` of the BF16 gate first and then multiplies. The sigmoid result therefore rounds to BF16 before the product. The CPU wrapper needs that boundary.
- The shared expert had the same issue. `qwen2_moe.py` 110-116 computes `F.sigmoid(BF16 gate) * BF16 down_output`. The initial wrapper kept the sigmoid FP32 until after multiplication. It needs BF16 sigmoid first.

The materialized HC combine boundary is correct: HCOPS 312-317 explicitly casts the residual-plus-injected-output to BF16 before computing the following grouped norm. The initial implementation does the same. The merge with the normalized projected embedding similarly materializes BF16 before the attention HC norm.

The indexer has no observed causality error. QSAOPS 482-557 sums each complete group oldest to newest in FP32 and writes its mean to BF16, then uses the group's first position. REFERENCE `compress` matches this. Only complete blocks are visible; the incomplete causal tail is appended (QSAOPS 158-181). These short prompts fit the 2048-token budget, so all earlier positions remain eligible. A stable descending CPU block order can still differ from the device persistent-top-k slot order, and attention reductions can consequently differ in low bits despite identical selected token sets.

For the rotary table, serving BASE 80-103 computes `1 / (theta ** (arange(0,64,2)/64))`, then FP32 positions times frequencies, then cos/sin, then BF16 cache conversion (BASE 59-63). REFERENCE uses `theta ** (-arange/64)` instead. These are mathematically equal but not guaranteed FP32-equal, so using the serving expression is preferable. BASE 81-85 itself warns that CPU versus GPU table creation can differ. MROPE 93-127 applies split-half rotation over 64 coordinates; its XPU entry dispatches the CUDA-named implementation (MROPE 425-432), which uses a Triton kernel for three-axis positions. Text uses identical values on all three axes. The CPU widened multiply/add with one BF16 result is a declared semantic choice; compiler contraction and device transcendental parity have not been established.

Routed weighted down results correctly round to BF16 before the sum. The XPU source available on disk (`vllm-xpu-kernels-current-main`, HEAD `1e90ffa672ba02f17a909da11838a4c55b199783`) accumulates expert slots in increasing order in FP32 then rounds BF16 (XPUMOESUM 635-642). An explicit FP32 Python loop is preferable to `torch.stack(...).sum(0)`, whose reduction tree is not a public arithmetic contract. The shared/routed final addition in MOERUNNER 774-775 is a BF16 elementwise addition, consistent with widening both BF16 values, adding and rounding once in the wrapper. This source inspection does not certify the historical device reduction: the retained kernel identity `e421889999bc1e5a5f11044d14548b9afdba644d` was unavailable in that local checkout; a read attempt caused a failed promisor-object lookup and recovered no source.

FP8 activation scaling has an additional implementation-path limitation. QUANT's Triton fallback uses `max(absmax,1e-10)*(1/448)` then division by scale. The current compiled XPU path uses `max(absmax/448,min_scaling_factor)` then multiplication by reciprocal scale (XPUQUANT 236-265, 354-385). These differ at possible FP8 rounding boundaries. Neither selecting the fallback formula nor importing the old mathematical reference proves exact served-device FP8 bits. The packet should name its formula, retain the official stored FP8 bytes and scales, and call the result a CPU reference with device arithmetic parity unverified. The semantic CPU GEMM, BF16 projections, transcendental functions, softmax/PV tree, router tie order and any eventual tensor-parallel collective order impose the same limitation. Acceptance measures this named CPU draft, not an unmeasured device draft.

### Expanded int8 format

EXPANDED 9-20 and 53-72 define a family of existing expanded GGUF formats: code bytes (except Q3_K nibble codes), FP32 scales per 16 or 32 weights, and retained original quantization metadata. Expansion recovers original integer codes and exact original scales; it does **not** requantize with a symmetric max/127 rule. For Q6_K the scale group is 16, so the proposed new MTP int8 variant matches the relevant code/scale representation and decode multiply `scale*int8`, but its max/127 quantizer is a **new draft-only quantizer**, not an existing lossless format converter. The initial wrapper uses nearest-even codes clamped to [-127,127], FP32 max/127 group scales and BF16 activations, which is a reasonable explicitly specified new format. A device implementation needs a new FP8-to-int8 conversion/type/loader binding; existing packet10's closed GGUF type dispatch does not automatically accept it. Do not claim that running this CPU variant validates that device loader or expanded GEMV arithmetic.

### Additional source receipts

- **QSAOPS**: `/home/steve/src/vllm-current-main/vllm/models/qwen4_exp/nvidia/ops/qsa.py`
  SHA-256 `faa8d358c79745f304edd363e4da21992e4cf015a22316b14980500bd199a0ad`
- **SHAREDMLP**: `/home/steve/src/vllm-current-main/vllm/model_executor/models/qwen2_moe.py`
  SHA-256 `403f0a3b14a1ad53d3bf4734f675c9d2ee5185c63e3bbeb662de48d6c5b66dc7`
- **BASE**: `/home/steve/src/vllm-current-main/vllm/model_executor/layers/rotary_embedding/base.py`
  SHA-256 `c81804498f08f072356a26b41967f211475df2694dabf5da9f488c074d1fdef5`
- **MROPE**: `/home/steve/src/vllm-current-main/vllm/model_executor/layers/rotary_embedding/mrope.py`
  SHA-256 `3fc4d03003471ffb0360b86820ff9bc27b0554d8f6aa464d02eec91fb3c96d23`
- **ROTARYCOMMON**: `/home/steve/src/vllm-current-main/vllm/model_executor/layers/rotary_embedding/common.py`
  SHA-256 `39bf5bb498ae45ca7a38269e85aa8b9b257a00c919e2d4d14a7ceb44ac7e9c98`
- **MOERUNNER**: `/home/steve/src/vllm-current-main/vllm/model_executor/layers/fused_moe/runner/moe_runner.py`
  SHA-256 `80d4b53fdbbbaf2aa9408f22ea476bacbdbb9db5cef0e51fca62c36a4f384d25`
- **XPUMOESUM**: `/home/steve/src/vllm-xpu-kernels-current-main/csrc/moe/moe_align_sum_kernels.cpp`
  SHA-256 `8882cd31c001582883bfb3ee761810b0b37304fca90484a6420edea41311385e`
- **XPUQUANT**: `/home/steve/src/vllm-xpu-kernels-current-main/csrc/quantization/fp8/fp8_quant.cpp`
  SHA-256 `bfc9f618a552fa5f50009a290a46a097c69bb90c49189817905a7d1b63f4897a`
- **EXPANDED**: `experiments/own-xpu-runtime/stage2/packet10-kopt5/expanded.hpp`
  SHA-256 `6e96276d9eee2564aa74d2f90b6802d04709f78d2b866b394c6fca2fe818dee3`
- **EXPANDED-PYTHON**: `experiments/own-xpu-runtime/stage2/packet10-kopt5/expansion.py`
  SHA-256 `50661b485363fc1a8c97c5648060db593112e00505a52b1b4af3cbc9173f6aa3`
