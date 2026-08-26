# Embedded-Q8 MTP3/F16 TP1 exact-depth R3

R3 is a fresh create-only retry. R2 is preserved as a zero-cell failure because
llama-server rejects a literal empty `input_ids` array. No R2 measurement or
candidate artifact transfers into R3.

The 2K, 4K, 8K, 16K, 24K, and 32K requests remain exactly unchanged: each
submits the pinned fixture token count and must report that same
`usage.prompt_tokens` value. The display x=0 point has a distinct, explicit
HTTP-serving meaning:

> zero tokens are active before the request; the request then submits the one
> ordinary token ID `90`, and must report `usage.prompt_tokens=1` and
> `cached_tokens=0`.

Token `90` is copied directly from the first token of the pinned 2K fixture. It
is not BOS, EOS, padding, or another inferred special token. The x=0 receipt is
not evidence for a literal empty prompt or a raw-engine zero-token invocation.
Any site view must carry the same disclosure.

All other model, runtime, DSO, graph-off, MTP0/MTP3, parity, counter, quality,
cleanup, and authority gates remain inherited. Static check is inert:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py --check
```
