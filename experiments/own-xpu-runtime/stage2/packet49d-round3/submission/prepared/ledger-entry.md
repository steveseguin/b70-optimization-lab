## packet49d-round3 — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvc9xc0f06o0le01x7afsrcw](https://www.localmaxxing.com/runs/cmvc9xc0f06o0le01x7afsrcw).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet49d-round3`, sealed build base `a58ed0d9ae1c0bdc9cd111a9fb0bf5fec1249e86`, seal `6fdc4d1ae838156d141611e3ba8367f245075f70e4be91dfbd3ac56e6e28e861`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **46.00384931003733 tok/s**; all-prompt **46.05812192861572 tok/s**;
  p10 45.1009385680535, mean 45.87243533913688; median TTFT 1101.6737950048991 ms; median wall 33.05283784197146 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet49d-round3/submission/prepared/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
