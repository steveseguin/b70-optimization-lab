# packet56-draft-prefix LocalMaxxing payload — prepared, not submitted

The preregistered WS128 is the only headline. The current public record remains
[cmvcconpv06o9le01nnxeuwpi](https://www.localmaxxing.com/runs/cmvcconpv06o9le01nnxeuwpi) until the coordinator
submits and retains a successful API response. No repeat is selected or pooled.

Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS is a **quantized compressed version**, separate
from the official FP8 model. Publisher revision:
`766911a6b7369840a91dbcd95f9f997acaab6cd6`. Two B70 cards 0+1, target split 23/25,
official one-token MTP draft on rank 1, capacity 4096, full BF16 KV.

Build base revision: `44cb624cb1c06e278cde5e5843176e01d64ee821`. This comes from the seal's `runtime_revision`;
the seal and its source inventory identify the actual overlay, not that Git
revision alone. Seal `8c1d90e124fbdcd3d932dcfd31b8819674011137fbbded2a2a8340590a639cec`; device binary `b3458fb16bdcd4b5c8a1ad2004275b6fb26cae624727ef01149358afac878edd`; boot `2cba7160-054a-4ffe-b4c4-e252eb956f5f`.

Arithmetic changed from SPEED6 to **iq3-p49-split32-v1** through split32 QSA. All twelve
prompts are exact against the new packet49 CPU reference. This is lossless
against this line's own reference, not a claim of bit equality to SPEED6.
The packet49 oracle's old-versus-new report remains in the evidence bundle.

| Measurement | WS128 |
| --- | ---: |
| Median of six prompt-class medians, 99 intervals between events 1 and 100 | 46.96269702286488 tok/s |
| All-prompt median, same interval metric | 47.20674846539052 tok/s |
| All-prompt p10 / mean | 45.52471288922505 / 46.894853702864594 tok/s |
| Median TTFT | 1096.7124265007442 ms |
| Median wall rate, last token minus request start | 33.49520133550886 tok/s |
| Requests / generated tokens | 12 / 1536 |
| Observed increase over 46.00384931003733 threshold | 2.0842771359533607% |

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
Repository result path: `experiments/own-xpu-runtime/stage2/packet56-draft-prefix/submission/prepared/result.json`.

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

## Coordinator disclosure: what changed from packet 49d

Packet 56 is packet 49d with one change, in the draft. The one-token MTP draft computes its proposal argmax over **vocabulary rows [0, 91,392) of the shared output head** instead of all 248,320 rows.

**How N was chosen:** N was fixed before any device run by a preregistered rule: the smallest multiple of 256 covering ≥ 99.5% of tokens in five fixed independent local files. Coverage was 99.51%. The benchmark prompts and outputs were never used to choose N.

**Why outputs are unchanged:** the target model verifies every token with the full head and unchanged arithmetic, so outputs are identical to the packet 49 CPU oracle (12/12). Only draft acceptance can move.

**Measured effect against packet 49d's WS128:**
- head micro-benchmark 1,424 → 540 µs;
- hit cycle 19.02 → 18.22 ms;
- miss cycle 32.81 → 33.04 ms;
- acceptance 0.791 → 0.787;
- class-balanced 46.0038 → 46.9627 tok/s (+2.08%).

This is one timed WS128 run. The payload's generated notes field (bound to the computed result) does not repeat this paragraph.
