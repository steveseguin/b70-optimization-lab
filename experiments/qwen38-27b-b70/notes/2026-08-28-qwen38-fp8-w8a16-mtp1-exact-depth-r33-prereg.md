# Qwen3.8 official FP8 TP2 W8A16 MTP1 exact-depth R33 preregistration

## Question

Does the strictly qualified deterministic MTP1 profile remain target-exact and
useful from 2K through 32K active context, or must its public 32K cell remain
withheld?

## Frozen profile

- model: official `Qwen/Qwen3.8-27B-FP8` revision already direct-verified by
  the promoted TP2 packet;
- image:
  `neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31`, immutable
  image ID
  `sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b`;
- XPU kernels: `1e90ffa672ba02f17a909da11838a4c55b199783`;
- TP2, official block-FP8 weights with the lab W8A16 dispatch, FP16/auto KV,
  MTP depth 1, no prefix caching, one active sequence, 33,024-token capacity;
- deterministic compiler scheduling and the qualified packed-two-row
  RMSNorm replay are required; no dynamic MTP, selected prompt, response
  cache, or warmed repeated request is allowed;
- a new empty runtime/compile cache and one fresh server lifetime are used;
- exact depths: 2,048, 4,096, 8,192, 16,384, 24,576, and 32,768 tokens;
- response: 128 token IDs, temperature zero, EOS ignored solely to retain the
  fixed measurement window.

## Promotion gates

Every point must pass the existing exact-depth receipt gates: exact prompt
count, 128 returned token IDs, `cached_tokens=0`, no truncation or context
shift, and a positive conventional 99-interval decode rate. Every complete
output-token array must also equal the corresponding qualified MTP0/W8A16 TP2
depth receipt under the same exact fixture. Any target mismatch withholds the
entire MTP1 curve from public package cells; the raw observations remain
diagnostic evidence.

This is Grade-C repeated-token context-shape evidence. It cannot become a
strict natural-prompt decode headline, a quality claim beyond the declared
oracle comparison, or a LocalMaxxing submission. No point may be interpolated
or extrapolated. A startup or 32K capacity failure is itself the result; a
changed memory profile requires a new preregistration.
