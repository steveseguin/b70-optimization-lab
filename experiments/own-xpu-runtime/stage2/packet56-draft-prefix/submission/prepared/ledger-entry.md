## packet56-draft-prefix — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvcconpv06o9le01nnxeuwpi](https://www.localmaxxing.com/runs/cmvcconpv06o9le01nnxeuwpi).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet56-draft-prefix`, sealed build base `44cb624cb1c06e278cde5e5843176e01d64ee821`, seal `8c1d90e124fbdcd3d932dcfd31b8819674011137fbbded2a2a8340590a639cec`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **46.96269702286488 tok/s**; all-prompt **47.20674846539052 tok/s**;
  p10 45.52471288922505, mean 46.894853702864594; median TTFT 1096.7124265007442 ms; median wall 33.49520133550886 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/submission/prepared/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
