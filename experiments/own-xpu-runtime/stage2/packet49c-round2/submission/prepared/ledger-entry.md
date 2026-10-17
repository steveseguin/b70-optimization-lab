## packet49c-round2 — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmv9wjmtj013gle01v8k1yg4v](https://www.localmaxxing.com/runs/cmv9wjmtj013gle01v8k1yg4v).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet49c-round2`, sealed build base `192ee28f2`, seal `2ebe64adc810d7560c23f2674117c424caf360a4e7c3b75217eb25aa0b900dd7`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **45.695513175425305 tok/s**; all-prompt **45.62200425359322 tok/s**;
  p10 44.586124108407574, mean 45.46770725300328; median TTFT 1105.3894225042313 ms; median wall 32.89855705871659 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet49c-round2/submission/prepared/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
