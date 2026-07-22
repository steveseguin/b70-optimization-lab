# DeepSeek V4 Flash K160 record validity

The 80.820052 tok/s row is valid only under all of these conditions:

- one active generation on four B70s; never aggregate concurrent throughput;
- exact model, draft, runtime commits, topology, graph modes, and selector
  identity from the standalone repro;
- unchanged K160 target verifies every accepted DSpark token at M=8;
- plain temperature-zero greedy sampling for the sharded-target-argmax path;
  unsupported grammar, logprob, penalty, bias, bad-word, draft-logit, or
  non-greedy configurations must fall back to the canonical path;
- each realistic prompt is unique and sent once cold;
- `cached_tokens=0` for every request and no prefix cache, response reuse,
  n-gram/history acceleration, or context checkpoints;
- primary metric is the median generated-token throughput for tokens 1-100
  after TTFT across the fixed 12-prompt suite;
- exact canaries pass before, between, and after the three strict suites.

The public K160 checkpoint is hash-pruned and its calibration is not
reproducible. The gate supports a result for this exact experimental artifact;
it does not certify the artifact as official DeepSeek V4 Flash or true REAP.

Evidence is the [record note](../../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-sharded-target-argmax-record.md),
the [compact JSON](../../experiments/deepseek-v4-flash-reap-xpu-b70/data/dspark-sharded-target-argmax-record-20260718.json),
and LocalMaxxing approval `cmrquta9905w3lg013m5vxoqx`.
