## packet195-record-bundle-diet — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvk51wfn001gng01fpbfy89q](https://www.localmaxxing.com/runs/cmvk51wfn001gng01fpbfy89q).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet195-record-bundle-diet`, sealed build base `052e9cf97c59fe5a777c93fc4e5849a61798033b`, seal `2b2a4893a9a145a3bab03c2cc263af30482003ee724c0636b794b93a44bdeb96`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **63.61182359725404 tok/s**; all-prompt **63.61182359725404 tok/s**;
  p10 61.43667032845857, mean 63.510112591774316; median TTFT 891.5339119266719 ms; median wall 44.10030717742968 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/submission/prepared-a/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
