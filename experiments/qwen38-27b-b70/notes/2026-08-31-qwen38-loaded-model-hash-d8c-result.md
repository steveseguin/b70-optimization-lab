# Qwen3.8 loaded-model cross-process hash D8c result

D8c is a **negative causal screen**. Every one of the 1,091 named parameters
and buffers in the completely loaded TP1 model matched across four fresh
processes, including name, kind, dtype, shape, stride, and full content hash.
The four complete JSON receipts were themselves byte-identical at SHA-256
`561f7ceaedb55a5ffe70d52d10e5db38bd94a511916406aa5f646345edbc899b`.

The pinned model also passed the direct-and-ordinary storage verification gate.
No inference request was sent: each process stopped immediately after its
atomic loaded-state receipt. Therefore checkpoint storage, vLLM stacking and
packing, and loaded parameter/buffer state are not supported causes of the
fresh-server output mismatch.

This does not establish inference determinism. The next diagnostic must locate
the first decoder layer or final-logit stage whose output differs across fresh
processes under a fixed token-ID request. No performance or publication claim
follows from D8c.
