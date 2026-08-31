# Qwen3.8 runtime-sitecopy GDN pad D39 result

D39 passed the packaged prefill boundary: four fresh server processes produced
one identical layer-0 production-forward trace, and its output hash exactly
matched D36's repaired reference. This validates the site-packages patch and
withdraws the cwd-biased r1 invalid classification.

The complete 64-token outputs still split at generated token index 60 into two
identical pairs. Therefore the prefill repair is necessary but not sufficient;
a separate late decode-time source remains. D40 captures the complete decoder
stack at the call that produces token 60 without making a quality or speed
claim.
