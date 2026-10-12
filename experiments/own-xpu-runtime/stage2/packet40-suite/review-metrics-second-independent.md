# Independent metric review

Reviewed final `suite_metrics.py` and suite request/summary wiring against `docs/localmaxxing.md`, the submission helper, its provided queue, the fixed suite class mapping, and the exact reference-baseline table. No unresolved calculation or qualification issue was found. This is a source review, not new execution evidence.

The fixed64 rate is `63 / (t64 - t1)`. The historical table rate excludes terminal EOS and uses `(N - 1) / (tN - t1)` for up to64 non-EOS events; the reference28.49 median actually has11 finite prompt rates per repeat because code-review ended immediately. These fields are separately named.

The submission window is exactly `99 / (t100 - t1)`, including natural EOS at event100. Earlier EOS has no window. The primary aggregate takes the conventional median within each prompt class, then the conventional median of those class medians. Its all-prompt median remains separately available.

Raw timestamps, counts, TTFT, wall rate, finish flags, requested cap, hashes, cache-zero fields and helper metric metadata are present. Top-level aggregation uses the first attempt; repeats have separate summaries. A distinct synthetic warmup precedes requests, with complete state reset between them. Partial suites remain labeled. The64/128 caps cannot pass the512-cap final gate: both final-gate markers remain false, and promotion attestation is still absent.

The JSON receipt records all source and authority hashes and nine reviewed conditions. No device was run or speed claimed.

## Reference identity caveat

The reference packet records unmodified llama.cpp commit `23b0202a189c44a54625aadcb37a946dd1d6278d`, SYCL F32 arithmetic, FP16 K/V, context 4096, no speculative decoding and no runtime warmup. It uses Unsloth UD-IQ3_XXS revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, the same named GGUF release and model directory used by the current lane. Its model-verification receipt hashes all three shards; this review did not rehash the large model files.

Packet40 uses the independent `iq3-p17-detmath-v2` arithmetic authority, BF16 KV/state, context 256, a distinct excluded kernel warmup, and optionally verified official MTP. The current complete 128-token oracle gives code-review 128 tokens beginning with token 1919, while the historical reference gives immediate EOG and therefore no finite decode rate. Thus the historical median uses eleven successful rate rows per repeat, whereas the new complete suite is expected to have twelve.

Matching the fixed64 formula alone does not establish equal arithmetic, output, runtime identity, or the same valid-prompt population. The user's 28.49 tok/s remains an external screening reference. It must not be described as a matched bit-identical control or used to claim a quality-qualified speedup without those additional controls. The protected reference table was not edited.
