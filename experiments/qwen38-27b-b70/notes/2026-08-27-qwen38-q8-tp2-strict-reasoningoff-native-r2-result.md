# Qwen3.8 Q8 TP2 strict package headline: qualified

The exact packaged Q8_0/F16-KV TP2 launcher now has a strict single-user
headline: **36.726447 tok/s**. This is the median of the two fresh-server
class-balanced medians, 36.733956 and 36.718938 tok/s (0.041% relative range).

Both attempts used the full fixed twelve-prompt/six-class suite, a 512-token
natural stop/length cap, temperature zero, raw untemplated prompts, and the
99 intervals between streamed generated-token events 1 through 100. Every row
had `cached_tokens=0`; both workload gates and both objective-canary batteries
passed. Complete generated-token arrays matched **12/12** across the fresh
servers.

The R2 outputs also match all **12/12** complete response hashes from the
historical 36.772932 tok/s raw-completions oracle. The new paired result is
0.126% lower. The launcher carries `--reasoning off`, but raw untemplated
completion prompts do not invoke the chat template; reasoning policy must
still be disclosed for chat-service comparisons.

R1A remains invalid evidence. Its OpenAI-compatible stream emitted no token
IDs, so the strict gate correctly rejected it. R2 changed only transport to
llama.cpp's native raw `/completion` stream, which exposes token IDs; prompt
bytes, sampling, model/runtime identity, and cache policy were unchanged.

This qualifies only the short-context single-user TP2/MTP0 headline. The
already-qualified exact-depth and output-audited concurrency profiles retain
their own scopes. Nothing transfers to TP1, MTP, another quant, or a
chat-templated workload.
