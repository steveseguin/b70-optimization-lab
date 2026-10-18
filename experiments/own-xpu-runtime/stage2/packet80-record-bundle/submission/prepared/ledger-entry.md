## packet80-record-bundle — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvcuvh4q080wle01pgjwixvj](https://www.localmaxxing.com/runs/cmvcuvh4q080wle01pgjwixvj).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet80-record-bundle`, sealed build base `e2e3bed9cc48c172c50ca1100a638ce4e482583b`, seal `60aec5968c169e502f39aedebbeb51efb5db1488e3c1787fe9e0a528fcb0fc9e`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **55.18991716741779 tok/s**; all-prompt **55.34434506355716 tok/s**;
  p10 53.86181041756037, mean 55.153240668866694; median TTFT 936.7901745063136 ms; median wall 39.33248906980643 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet80-record-bundle/submission/prepared/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
