## packet103-record-bundle — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvdgjqwj000rrf013ay3ew6t](https://www.localmaxxing.com/runs/cmvdgjqwj000rrf013ay3ew6t).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet103-record-bundle`, sealed build base `295f4ea7f45ac2d16984382d9004cec13173f3d4`, seal `3d209d2dfd58546027f476dadef992c40299e47d3bfc57dd467c67fb9a9c16ab`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **57.55057346032133 tok/s**; all-prompt **57.739403339964994 tok/s**;
  p10 56.19796858781631, mean 57.576594187878015; median TTFT 902.5350525189424 ms; median wall 41.04610679430046 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet103-record-bundle/submission/prepared-b/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
