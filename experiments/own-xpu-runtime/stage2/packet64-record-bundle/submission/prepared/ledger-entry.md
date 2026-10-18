## packet64-record-bundle — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvco3d6606u1le01941ek8hq](https://www.localmaxxing.com/runs/cmvco3d6606u1le01941ek8hq).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet64-record-bundle`, sealed build base `53ffe460517c585b21be1c3b69ce22b7e9f195a0`, seal `2e93e792cdbcff2387efe0acb597437ada6e6db7b3cab293bec1119d52a51864`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **52.8990814513803 tok/s**; all-prompt **52.960450786753874 tok/s**;
  p10 51.50209882512183, mean 52.838467997219496; median TTFT 980.0485110026784 ms; median wall 37.69524831982081 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet64-record-bundle/submission/prepared/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
