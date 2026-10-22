## packet187-record-bundle-v3 — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmve4dtir007wrf01k57sdf23](https://www.localmaxxing.com/runs/cmve4dtir007wrf01k57sdf23).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet187-record-bundle-v3`, sealed build base `052e9cf97c59fe5a777c93fc4e5849a61798033b`, seal `f6207449118c5ef6edfbdcbc5a74fb5aec7a989ec2936fd894df871a9e1314a4`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **60.65951991975228 tok/s**; all-prompt **60.65951991975228 tok/s**;
  p10 58.521211576511206, mean 60.4068880729537; median TTFT 891.8635745067149 ms; median wall 42.560004031390235 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/submission/prepared-a/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
