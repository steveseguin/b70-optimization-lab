# packet136-record-bundle LocalMaxxing payload — prepared, not submitted

The preregistered WS128 is the only headline. The current public record remains
[cmvdx8urg0068rf01vvb32bcs](https://www.localmaxxing.com/runs/cmvdx8urg0068rf01vvb32bcs) until the coordinator
submits and retains a successful API response. No repeat is selected or pooled.

Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS is a **quantized compressed version**, separate
from the official FP8 model. Publisher revision:
`766911a6b7369840a91dbcd95f9f997acaab6cd6`. Two B70 cards 0+1, target split 23/25,
official one-token MTP draft on rank 1, capacity 4096, full BF16 KV.

Build base revision: `052e9cf97c59fe5a777c93fc4e5849a61798033b`. This comes from the seal's `runtime_revision`;
the seal and its source inventory identify the actual overlay, not that Git
revision alone. Seal `fa9cf3d1372cecfc7c75d30814e6f2ba5138b410e45ff0f140d25da9a823e975`; device binary `fd7e8b6f5fb24c5042d051f59026091a9184c0f15149d7de110528b7d3ac5451`; boot `2cba7160-054a-4ffe-b4c4-e252eb956f5f`.

Arithmetic changed from SPEED6 to **iq3-p49-split32-v1** through split32 QSA. All twelve
prompts are exact against the new packet49 CPU reference. This is lossless
against this line's own reference, not a claim of bit equality to SPEED6.
The packet49 oracle's old-versus-new report remains in the evidence bundle.

| Measurement | WS128 |
| --- | ---: |
| Median of six prompt-class medians, 99 intervals between events 1 and 100 | 58.798108759182306 tok/s |
| All-prompt median, same interval metric | 58.76183737770384 tok/s |
| All-prompt p10 / mean | 57.10056557704859 / 58.682606874931196 tok/s |
| Median TTFT | 897.3597449949011 ms |
| Median wall rate, last token minus request start | 41.66277391626218 tok/s |
| Requests / generated tokens | 12 / 1536 |
| Observed increase over 58.2238342935355 threshold | 0.9863219635305898% |

One cold response per fixed prompt, zero cached tokens, complete state resets,
a distinct excluded kernel warmup, and no prompt/KV/response/history reuse.
The target verifies accepted draft tokens. KD and W2m pass, and WS, sequential
WSs, WS128x and WS128 agree with all 12 CPU oracle outputs in independent rank
processes. WS128x checker receipts bind 16 × 48 fixtures per prompt; WS128 retains
none. Fixture equality is attested by the hash-bound original checker receipts;
this preparation does not rerun device work or copy all layer arrays.

No new fault signatures appear in the retained window journal tails. Historical
preflight fault lines remain preserved; this is not a clean-boot claim.
This is one preregistered timed WS128, with independent exactness windows, not
multiple fresh-server speed measurements or a completed A-B-A speed comparison.

The coordinator's October 17 decision extends the existing owner-authorized
**128-token scope** to this pinned packet. Both the raw realistic final gate and
the strict **512-token gate remain false**. Standard 512-input-token prefill and
512-token natural completion are **not measured**. The observed increase is not
a confidence interval or an assertion of equal outputs to the older arithmetic.

[Result JSON](result.json), [attestation](promotion-attestation.json),
[payload queue](payload-queue.json), [original evidence bundle](evidence.json.gz).
Repository result path: `experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/rehearsal/result.json`.

The gzip bundle is a JSON object with original bytes in `members[*].raw_base64`,
a SHA256 for each member and its original path. It retains the seal, oracle
completion/manifest, prompt outputs, independent repeat, device windows, request
receipts, dispatch and journal tails. The submission helper replays token equality,
identity and metric checks from this bundle before accepting `tokSOut`.
The bundle must be retained with these files; it is required evidence, not cache.

Preparation stops after local and server dry-runs. The coordinator separately
commits the generated evidence, records the dry-run response, performs the real
submit and fills the ledger with the returned ID. This document asserts none of
those external actions has occurred.
