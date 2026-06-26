# 2026-06-26T22:25Z llama.cpp Gemma4 Current Record Stack

Patch:

- `20260626T2225-llamacpp-gemma4-current-record-stack.patch`

Base:

- upstream llama.cpp commit `c926ad098`
- local source tree:
  `/home/steve/src/llama.cpp-gemma-record-stack`

Validated headline result:

- `data/gemma4-q8-gpu2-routecache-mtpfusedoutargmax-selfusedweights-full-20260626T222525Z/summary.json`
- fresh row0 after TTFT: `103.95374341972274 tok/s`
- supporting mean after TTFT: `104.13506066488091 tok/s`
- chat canary: `1536/1536`
- LocalMaxxing: `cmqviful602p0qr01vp27jw5i`

Promoted recipe flags from this patch stack:

- `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`
- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`
- `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`
- `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`
- `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`
- `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`
- `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`
- `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`

Important caveat:

This is a **cumulative local research patch stack**, not a minimal upstreamable
patch. It intentionally preserves default-off experiment code and diagnostics
that were tested during the Gemma lane, including some rejected paths. The
validated record uses only the promoted flags listed above. Keep the rejected
paths available as research artifacts so future agents do not rediscover the
same dead ends.

For copy-ready runtime reproduction, use
`../../results/gemma4-26b-a4b-q8-b70/reproduce.md`.
