# packet103-record-bundle LocalMaxxing payload — prepared, not submitted

The preregistered WS128 is the only headline. The current public record remains
[cmvdgjqwj000rrf013ay3ew6t](https://www.localmaxxing.com/runs/cmvdgjqwj000rrf013ay3ew6t) until the coordinator
submits and retains a successful API response. No repeat is selected or pooled.

Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS is a **quantized compressed version**, separate
from the official FP8 model. Publisher revision:
`766911a6b7369840a91dbcd95f9f997acaab6cd6`. Two B70 cards 0+1, target split 23/25,
official one-token MTP draft on rank 1, capacity 4096, full BF16 KV.

Build base revision: `295f4ea7f45ac2d16984382d9004cec13173f3d4`. This comes from the seal's `runtime_revision`;
the seal and its source inventory identify the actual overlay, not that Git
revision alone. Seal `3d209d2dfd58546027f476dadef992c40299e47d3bfc57dd467c67fb9a9c16ab`; device binary `81cd3f47a91ff4ad3737e39904f87198e019f37730ac4fa966f8e3c4dd18aa19`; boot `2cba7160-054a-4ffe-b4c4-e252eb956f5f`.

Arithmetic changed from SPEED6 to **iq3-p49-split32-v1** through split32 QSA. All twelve
prompts are exact against the new packet49 CPU reference. This is lossless
against this line's own reference, not a claim of bit equality to SPEED6.
The packet49 oracle's old-versus-new report remains in the evidence bundle.

| Measurement | WS128 |
| --- | ---: |
| Median of six prompt-class medians, 99 intervals between events 1 and 100 | 57.55057346032133 tok/s |
| All-prompt median, same interval metric | 57.739403339964994 tok/s |
| All-prompt p10 / mean | 56.19796858781631 / 57.576594187878015 tok/s |
| Median TTFT | 902.5350525189424 ms |
| Median wall rate, last token minus request start | 41.04610679430046 tok/s |
| Requests / generated tokens | 12 / 1536 |
| Observed increase over 56.08698676757046 threshold | 2.6094942465283655% |

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
Repository result path: `experiments/own-xpu-runtime/stage2/packet103-record-bundle/submission/prepared-b/result.json`.

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
