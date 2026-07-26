# Laguna S 2.1 KV-cache precision decision

Date: 2026-07-26 America/Toronto

Status: **documentation and lane decision only; no new server or benchmark was
run.**

## Decision

There are two valid answers because the objectives are different:

- For Poolside's normal `poolside/Laguna-S-2.1-INT4` deployment, **FP8 is the
  publisher-supplied official/default KV-cache format**.
- For reproduction of this lab's `102.971435596` tok/s record and its
  bitwise-exact BF16 canonical-teacher contract, **keep BF16 KV**.
- Treat an FP8-KV B70 service as a separate long-context/capacity and quality
  lane. Do not silently replace the record's KV dtype or call the two lanes
  bitwise equivalent.

The record's `FP8` label refers to 31 DFlash **weight/projection** conversions.
Its target and draft KV caches are BF16. Weight precision and KV-cache
precision are independent identity fields.

## What the official checkpoint requests

The Poolside model card says that Laguna S 2.1 uses an FP8 KV cache, and the
official vLLM recipe says that all three quantized checkpoints ship with an
FP8-quantized KV cache whose quantization is detected automatically:

- [Poolside INT4 model card](https://huggingface.co/poolside/Laguna-S-2.1-INT4)
- [official vLLM Laguna recipe](https://recipes.vllm.ai/poolside/Laguna-S-2.1)
- [official checkpoint config](https://huggingface.co/poolside/Laguna-S-2.1-INT4/blob/main/config.json)
- [vLLM quantized-KV documentation](https://docs.vllm.ai/en/latest/features/quantization/quantized_kvcache/)

The pinned local target at revision
`4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb` declares:

```json
{
  "torch_dtype": "bfloat16",
  "quantization_config": {
    "kv_cache_scheme": {
      "dynamic": false,
      "num_bits": 8,
      "observer": "minmax",
      "strategy": "tensor",
      "symmetric": true,
      "type": "float"
    }
  }
}
```

`torch_dtype=bfloat16` does **not** mean that the checkpoint recommends BF16
KV. It is the model's native dtype for unquantized tensors and activations.
`kv_cache_scheme` is the separate cache instruction. This checkpoint contains
calibrated, symmetric, per-tensor FP8 KV scales; it is not the unsafe generic
case where `--kv-cache-dtype fp8` uses default scale `1.0`.

The pinned safetensors contain 96 scalar scale tensors: one `k_scale` and one
`v_scale` for each of 48 target layers.

Pinned local evidence:

- target `config.json` SHA256:
  `9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6`;
- target `README.md` SHA256:
  `efbb977c169c513c50449b8fe77e99251ede5bc0fd6f359d972d84f86bec1d7d`;
- target config:
  `/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json`.

The local record vLLM also honors the checkpoint FP8 scheme when
`kv_cache_dtype=auto`. The record launcher deliberately overrides it with:

```text
--kv-cache-dtype bfloat16
```

The sealed server log independently resolves
`kv_cache_dtype=bfloat16`.

## BF16 versus FP8 in concrete terms

Laguna has eight KV heads with head dimension 128. For one token in one
attention layer:

```text
K + V values = 2 * 8 * 128 = 2,048 values
BF16 payload  = 2,048 * 2 bytes = 4,096 bytes
FP8 payload   = 2,048 * 1 byte  = 2,048 bytes, plus small scale metadata
```

For the 48-layer target, that is approximately 192 KiB/token aggregate in
BF16 versus 96 KiB/token in FP8. Including the six-layer DFlash draft gives a
naive 216 KiB versus 108 KiB aggregate payload. With clean TP4 KV-head
sharding, that is about 54 KiB versus 27 KiB per rank before allocator,
alignment, graph, and metadata overhead.

Laguna's 36 sliding-window layers stop growing after their 512-token window,
while its 12 global-attention layers continue growing. That improves the true
long-context curve, but runtime allocation and hybrid-cache grouping remain
authoritative; the arithmetic above is a payload explanation, not a promise of
an exact service capacity.

| Property | BF16 KV | FP8 KV |
| --- | --- | --- |
| Bytes per K/V element | 2 | 1 |
| Approximate KV payload | baseline | half |
| Cache token capacity | baseline | near 2x when KV is the limiting allocation |
| KV read bandwidth | baseline | potentially near half |
| Cache write/read work | native BF16 | quantize, store FP8, scale/dequantize or use native FP8 attention |
| Numerical precision | higher | lower mantissa precision, calibrated scaling |
| Bitwise equality to BF16 teacher | possible | not expected |
| Likely best use here | exact short-decode record | official long-context/capacity service lane |

FP8 can improve long-context decode if attention is genuinely KV-bandwidth
bound and the backend consumes FP8 efficiently. It can be neutral or slower at
short context when quantization, descale, conversion, or a less mature kernel
costs more than the bytes saved.

## Why the B70 record uses BF16

### 1. The quality contract was bitwise BF16 teacher equality

The optimization lane required every promoted DFlash output to match a
canonical q=1 target teacher token-for-token and text-for-text. The teacher,
target cache writes, exact verifier arithmetic, and width-12 graph stack were
established with BF16 KV.

Changing KV precision changes stored K/V values and therefore attention logits.
Even calibrated FP8 is not bitwise BF16. It would require a separately named
quality contract and teacher, not a guard relaxation inside the existing
record.

### 2. Laguna already had a direct BF16/FP8 B70 screen

The earlier matched-DFlash TP4+EP4 PIECEWISE comparison held the model, draft,
depth, context limit, cache budget, and one-active-generation policy fixed:

| KV dtype | Median tok/s, tokens 1-100 after TTFT | Cache tokens/card | Result |
| --- | ---: | ---: | --- |
| BF16 | `48.980858` | `110,995` | faster short decode |
| FP8 | `46.956936` | `221,990` | exactly 2x capacity, `4.132%` slower |

FP8 passed within-mode determinism and produced coherent cache-zero responses,
but it was not bitwise equal to BF16: the repeated canary diverged and four of
six strict-suite rows differed. Full evidence and boundaries are in
[the original FP8-KV result](2026-07-22-dflash-accepting-fp8-kv-result.md).

That was an early width-8/depth-7 PIECEWISE lane, not the final width-12
Breakable-graph record. It proves the local capacity effect and establishes
that FP8 was not a short-decode win on that stack. It does not prove the exact
delta on today's final source.

### 3. The record workload was nowhere near KV-capacity pressure

The sealed BF16 record allocated 7.57 GiB of KV memory per card and reported:

```text
GPU KV cache size: 136,802 tokens
Maximum concurrency for 8,192 tokens per request: 16.70x
```

The fixed benchmark used prompts from 90 through 863 tokens and outputs up to
512 tokens. Logged KV usage peaked at only 0.5%. Halving cache bytes therefore
could not improve fit or concurrency for the measured single request. It could
only help if the attention kernels saved enough bandwidth to exceed their FP8
overhead, which the earlier short-context A/B did not.

### 4. BF16 needed one explicit XPU compatibility repair

The XPU cache-write extension used the string `auto` for native caches and
initially rejected an explicitly allocated BF16 cache. vLLM commit
`6bf7d6b83cb20c335b5e9a8ffda95d646338bbf5` maps explicit native float cache
names to `auto` only at the cache-write call while retaining the actual BF16
allocation. This is why explicit BF16 works cleanly in the sealed lane.

## Recommendation for future Laguna service work

Keep these as two recipes:

1. **Exact short-decode record:** explicit BF16 KV, current canonical teacher,
   exact width-12/depth-11 graph identity.
2. **Official long-context service candidate:** checkpoint-calibrated FP8 KV,
   separately labeled quality and performance evidence.

Before promoting the FP8 service candidate:

1. Assert from the resolved engine log that the cache is FP8 and that the
   checkpoint's loaded K/V scales are used. Do not infer this from `auto`.
2. Preserve a BF16 same-source control and report actual cache tokens/card.
3. Measure short decode and long-context decode separately; include at least
   8K, 32K, and a larger practical coding/agent context if capacity allows.
4. Recheck DFlash acceptance, emitted tokens/cycle, graph topology, cache-zero
   behavior, and first-request latency.
5. Run semantic coding/tool-use, structured output, repetition/doom-loop, and
   long-context retrieval gates. Within-FP8 determinism is useful, but it is
   not a substitute for quality evaluation.
6. Call FP8 a quality-preserving replacement for BF16 only if an explicitly
   defined quality suite supports that claim. Never use BF16 token hashes as
   an expected FP8 bitwise gate.

No serving code, launcher, or current record identity was changed by this
decision note.
