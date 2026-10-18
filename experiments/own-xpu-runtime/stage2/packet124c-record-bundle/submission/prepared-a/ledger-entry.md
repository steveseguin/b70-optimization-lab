## packet124c-record-bundle — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvdpmbbo0022rf017ynt8i35](https://www.localmaxxing.com/runs/cmvdpmbbo0022rf017ynt8i35).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet124c-record-bundle`, sealed build base `0a8aadaedeefd71c64372d1f786a08514a16c24a`, seal `b75bc5db9a21020b97685edf68d679d974fe1429ca1a5618dc7735f2344ffc69`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **58.2238342935355 tok/s**; all-prompt **58.20518576564042 tok/s**;
  p10 56.558999500001434, mean 58.08179415125559; median TTFT 897.1203134860843 ms; median wall 41.40277167820319 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet124c-record-bundle/submission/prepared-a/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
