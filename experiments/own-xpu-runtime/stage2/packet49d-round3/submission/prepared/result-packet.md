# packet49d-round3 LocalMaxxing payload — prepared, not submitted

The preregistered WS128 is the only headline. The current public record remains
[cmvc9xc0f06o0le01x7afsrcw](https://www.localmaxxing.com/runs/cmvc9xc0f06o0le01x7afsrcw) until the coordinator
submits and retains a successful API response. No repeat is selected or pooled.

Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS is a **quantized compressed version**, separate
from the official FP8 model. Publisher revision:
`766911a6b7369840a91dbcd95f9f997acaab6cd6`. Two B70 cards 0+1, target split 23/25,
official one-token MTP draft on rank 1, capacity 4096, full BF16 KV.

Build base revision: `a58ed0d9ae1c0bdc9cd111a9fb0bf5fec1249e86`. This comes from the seal's `runtime_revision`;
the seal and its source inventory identify the actual overlay, not that Git
revision alone. Seal `6fdc4d1ae838156d141611e3ba8367f245075f70e4be91dfbd3ac56e6e28e861`; device binary `05b2c282b45d90e037b8d6d27b9e0082d041d3a142ad564f3570560b666c45a8`; boot `2cba7160-054a-4ffe-b4c4-e252eb956f5f`.

Arithmetic changed from SPEED6 to **iq3-p49-split32-v1** through split32 QSA. All twelve
prompts are exact against the new packet49 CPU reference. This is lossless
against this line's own reference, not a claim of bit equality to SPEED6.
The packet49 oracle's old-versus-new report remains in the evidence bundle.

| Measurement | WS128 |
| --- | ---: |
| Median of six prompt-class medians, 99 intervals between events 1 and 100 | 46.00384931003733 tok/s |
| All-prompt median, same interval metric | 46.05812192861572 tok/s |
| All-prompt p10 / mean | 45.1009385680535 / 45.87243533913688 tok/s |
| Median TTFT | 1101.6737950048991 ms |
| Median wall rate, last token minus request start | 33.05283784197146 tok/s |
| Requests / generated tokens | 12 / 1536 |
| Observed increase over 45.695513175425305 threshold | 0.6747623851565576% |

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
Repository result path: `experiments/own-xpu-runtime/stage2/packet49d-round3/submission/prepared/result.json`.

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

## Coordinator disclosure: kernel selection and measured transfer

Packet 49d is packet 49c plus exact-order kernels.

- **Banked from packet 53b:**
  - expert gate/up virtual8 split-stream;
  - expert down virtual16;
  - small FFN virtual4.
- **Selected from packet 54:**
  - route `route-exp32-rank4`;
  - GDN recurrence `rows4-shared`.

All are byte-identical, so the same packet 49 CPU oracle applies.

The integration trigger was a **resource gate** for spending the device chain. The original rule was 40 µs per ordinary layer; the coordinator lowered it to 30 µs before any 49d device work. That amendment is hash-bound in `../../coordinator-amendment.json` (note commit `57ccb5e53`). The amendment did not touch exactness, scope or the record floor.

Measured against packet 49c's WS128:
- class-balanced +0.67% (45.6955 → 46.0038);
- hit cycle 19.16 → 19.02 ms;
- miss cycle 33.20 → 32.81 ms;
- acceptance unchanged at 0.791.

The isolated micro-benchmarks projected about 30 µs per layer, roughly 0.7 ms per half. About 20% of that transferred to the full engine. The benchmarks loop over synthetic weights that stay warm in cache, so they overstate the gains. This is one timed WS128 run.
