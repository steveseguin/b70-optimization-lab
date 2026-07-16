# DeepSeek V4 K160 post-record MTP1 fusion sweep

Date: 2026-07-16

## Outcome

The qualified four-B70, single-session record remains **60.264242 tok/s** with
**56.243105 p10**. Three exact post-record candidates were implemented and
tested, but none independently confirmed above that result. No LocalMaxxing
submission was made.

Structured evidence is in
`../data/mtp1-post-record-fusion-sweep-20260716.json`. Raw service evidence is
under `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu`.

## M=2 QNorm/RoPE/direct-KV fusion

The existing fused Triton program was already row-general; only its selector
was restricted to M=1. vLLM `375470ae9` adds an independently recorded,
default-one maximum width and exact M=2 shape agreement checks. The reusable
hardware gate was expanded with `--tokens`.

Every B70 passed 40/40 changed eager inputs and 8/8 changed fixed-address graph
replays bitwise in both normalized Q and every FP8 cache byte. The boundary
improved from 76.57-85.98 us to 37.30-41.81 us, projecting 1.68-1.90 ms over
43 layers in isolation.

The full-model result did not reproduce that ceiling reliably:

- screen: 61.194851 tok/s, p10 56.758131;
- independent confirmation: 60.043135 tok/s, p10 56.751210;
- 20/20 ordered exact suites, all cached-zero.

This is a real isolated fusion win but an inconclusive reusable-graph model
win. The default maximum remains one; preserve the code for a later package.

## M=2 in-place TP all-reduce

vLLM `ea2dd31eb` adds a separate default-off selector for the verifier's
`[2,4096]` reductions. It requires TP4, XPU, BF16, contiguous storage, the
exact two-row shape, and the mutation-declared custom-op path outside compiler
capture. Existing M=1 behavior is unchanged.

Packaged with the M=2 QNorm fusion, it reached:

- screen: 59.895145 tok/s, p10 56.249942;
- independent confirmation: 58.999027 tok/s, p10 56.329269;
- 20/20 ordered exact suites, all cached-zero.

The expected clone saving was only about 0.10-0.20 ms per 87-reduction cycle.
It did not overcome service variance or graph costs and remains default-off.

## Draft local-argmax reduction

The MTP draft previously projected a local 32,320-token shard, all-gathered the
full 129,280 BF16 logits, and then took an argmax. vLLM `cfa2a67b4` adds the
missing DeepSeek V4 XPU `get_top_tokens` methods. It keeps the same HC head,
shared-head RMSNorm, shared LM-head weights, BF16 values, and tie behavior, but
all-gathers four FP32 value/index pairs instead.

This reduces aggregate TP4 ring traffic from about 775,680 bytes to 96 bytes
per draft decision, an 8,080x reduction. The selector logged on all four ranks,
and 20/20 ordered exact suites passed with no cached prompt tokens. Results:

- screen: 59.064142 tok/s, p10 55.287985;
- independent confirmation: 59.094659 tok/s, p10 55.138052.

The reason the enormous communication ratio does not translate to a large
model gain is that the 252.5 MiB/rank LM-head weight read and local projection
remain. The removed collective is a small tail. The path is exact and useful
as optional infrastructure, but it is disabled in the qualified recipe.

## Decision

Do not stack these flags merely because their local arithmetic is exact. At
this optimization level, extra graph nodes, collective setup, and run variance
can erase tens-of-microseconds savings. A new service load now needs either a
measured complete-cycle saving large enough to survive graph replay or a new
architectural change with a clear ceiling. The qualified source identity stays:

- vLLM `9cf403e516566b44bbfcc7ad00eef976867c861b`;
- XPU kernels `46b95e64a315e04002e071640e8855b2398ab1ec`;
- oneCCL `48fda4f0e074db005596d6899d5227d3f0316c12`;
- LocalMaxxing `cmrmvjbok1np3mj01p9il8486`.

The code and failures are retained so the same attractive microbenchmarks are
not rediscovered and promoted without full-model confirmation.
