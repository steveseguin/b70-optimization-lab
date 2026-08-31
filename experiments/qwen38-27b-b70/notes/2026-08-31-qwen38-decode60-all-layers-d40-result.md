# Qwen3.8 token-60 all-layer trace D40 result

D40 captured all 192 decoder boundaries in every process. The generic runner
labeled the result `invalid-localization` because it compared generated-token
index 60 directly with internal call index 62. That guard does not account for
the two engine profile/prefill calls and is not the authority for this trace.

The boundary data is decisive:

- layer 0 input, hidden output, and residual: one hash each;
- layer 1 input: one hash;
- layer 1 hidden output and residual: four hashes each;
- every later layer receives already divergent input.

Thus true M=1 decode first diverges inside decoder layer 1, a GDN layer. D41
traces its internal production stages at call 62.
