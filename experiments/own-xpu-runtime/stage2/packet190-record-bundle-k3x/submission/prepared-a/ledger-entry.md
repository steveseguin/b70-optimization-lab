## packet190-record-bundle-k3x — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvjvabyv040jrf01dricuz8s](https://www.localmaxxing.com/runs/cmvjvabyv040jrf01dricuz8s).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet190-record-bundle-k3x`, sealed build base `052e9cf97c59fe5a777c93fc4e5849a61798033b`, seal `3d7cfa2ad7d5f0058ff55554ebb99f7c8030730adf157a08f0512302d644d204`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **62.345281904743764 tok/s**; all-prompt **62.26489094733665 tok/s**;
  p10 60.21037483924873, mean 62.19880034346824; median TTFT 911.5335315000266 ms; median wall 43.16364317893503 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/submission/prepared-a/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
