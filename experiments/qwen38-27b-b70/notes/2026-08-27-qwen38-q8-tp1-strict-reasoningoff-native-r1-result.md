# Qwen3.8 Q8 TP1 strict package headline: qualified

The exact packaged one-B70 Q8_0/F16-KV launcher now has a strict single-user
headline: **19.619240 tok/s**. This is the median of two fresh-server
class-balanced medians, 19.600348 and 19.638132 tok/s (0.193% relative range).

Both attempts used the full fixed twelve-prompt/six-class suite, a 512-token
natural stop/length cap, temperature zero, raw untemplated prompts, and the 99
intervals between streamed generated-token events 1 through 100. Every row had
`cached_tokens=0`; both workload gates and objective-canary batteries passed.
Complete generated-token arrays matched **12/12** across the fresh TP1
servers.

Quality is also bound to the exact same server and SYCL-library hashes by the
earlier service battery: 7/7 expected-answer canaries, 8/8 repeat stability, a
7,617-token needle, and 16/16 cache-zero responses all passed.

## Cross-TP disclosure

TP1 does **not** reproduce TP2 byte-for-byte: 0/12 complete arrays match the
qualified TP2 raw oracle. First divergences occur at generated-token positions
59 through 444, depending on the prompt; inspected continuations remain
semantically similar. This is treated as a different arithmetic identity, not
hidden or mislabeled as exact cross-card-count equivalence.

The TP1 headline is authorized by its own two-server determinism plus its
same-binary expected-answer, repeat, long-context, cache, and current objective
gates. This qualifies only short-context single-user TP1/MTP0 decode. Nothing
transfers to TP2, MTP, long context, aggregate serving, another quantization,
or a chat-templated workload.
