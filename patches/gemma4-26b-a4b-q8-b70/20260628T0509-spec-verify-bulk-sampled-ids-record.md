# 2026-06-28 Spec Verify Bulk Sampled IDs

Status: default-off source experiment; **submitted strict record bump**, but
still below reliable `>100`.

Source tree:
`/home/steve/src/llama.cpp-gemma-record-repro-c926`

Files touched:

- `common/sampling.cpp`
- `include/llama.h`
- harness identity capture in
  `scripts/run-gemma4-26b-first-baseline.sh` and
  `scripts/run-gemma4-26b-llamacpp-replica.sh`

Gate:

- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`

Intent:

The target verifier path already emits backend greedy argmax IDs when
`LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`. The existing verification loop
synchronizes once, then resolves each output row through
`llama_get_sampled_token_ith_nosync(ctx, idx)`. This experiment adds a
consecutive-row fast path that reads the sampled-ID host buffer once with
`llama_get_sampled_tokens(ctx)` and indexes it directly. If rows are not
nonnegative and consecutive, or if the bulk pointer is unavailable, the code
falls back to the existing per-row accessor and then to host argmax.

Result:

Four strict full512 lanes at
`data/gemma4-q8-gpu{0..3}-strict-vdr2-f16p021-bulksampled-n3-nmin2-p00475-ub1024-full512-20260628T050945Z/`
all passed the fresh-response gate (`cached_tokens=0`), but did not crack
`100 tok/s`:

- GPU0 median100 `94.8270`
- GPU1 median100 `97.9715`
- GPU2 median100 `95.7431`
- GPU3 median100 `97.1538`

Interpretation:

This is a small host-side cleanup, not a verifier-kernel breakthrough. It may
be a minor record improvement over the submitted `95.8245`, but it is not
enough by itself for reliable `>100`.

Exact confirmation:

Four strict full512 confirmation lanes at
`data/gemma4-q8-gpu{0..3}-strict-vdr2-f16p021-bulksampled-confirm-{A..D}-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/`
all passed the fresh-response gate (`cached_tokens=0`). The best lane was
GPU1/B:

- summary:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json`
- median100 `98.34046474459183`, p10 `85.97937679810455`, mean
  `95.95288855186745`
- full512 after TTFT `91.17386231553596`, wall full512
  `87.73710699260519`, TTFT median `180.21126103121787 ms`
- LocalMaxxing: `cmqxchyra03xmqr01b963gmi1`
- payload:
  `data/localmaxxing-payloads/gemma4-q8-vdr2-f16p021-bulksampled-confirm-20260628T052158.json`
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-bulksampled-full512-20260628.submit.log`

Interpretation:

Promote the flag in the current reproduction recipe because it is semantically
identical for consecutive verifier rows and produced a confirmed strict record
bump (`95.8245 -> 98.3405`). Do not treat it as the crack-100 fix; the
remaining gap is in verifier economics, especially target/verifier MoE and
LM-head cost, not per-row host sampled-ID lookup.
