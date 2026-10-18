## packet136-record-bundle — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvdx8urg0068rf01vvb32bcs](https://www.localmaxxing.com/runs/cmvdx8urg0068rf01vvb32bcs).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet136-record-bundle`, sealed build base `052e9cf97c59fe5a777c93fc4e5849a61798033b`, seal `fa9cf3d1372cecfc7c75d30814e6f2ba5138b410e45ff0f140d25da9a823e975`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **58.798108759182306 tok/s**; all-prompt **58.76183737770384 tok/s**;
  p10 57.10056557704859, mean 58.682606874931196; median TTFT 897.3597449949011 ms; median wall 41.66277391626218 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/rehearsal/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
