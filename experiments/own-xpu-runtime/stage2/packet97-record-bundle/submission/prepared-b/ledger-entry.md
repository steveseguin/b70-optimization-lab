## packet97-record-bundle — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvd78ela0007uj01k1ojlm8g](https://www.localmaxxing.com/runs/cmvd78ela0007uj01k1ojlm8g).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet97-record-bundle`, sealed build base `3566f04a0`, seal `c952b799199e2f8464b5af25cb5d4184934959ea511b5595ef9a86c52cd41907`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **56.08698676757046 tok/s**; all-prompt **56.24777670455502 tok/s**;
  p10 54.69951491333152, mean 56.06055025419959; median TTFT 918.9360555174062 ms; median wall 40.06638943257505 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet97-record-bundle/submission/prepared-b/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
