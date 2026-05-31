# Patches

Store patch snapshots and patch notes here.

Naming:

```text
vllm-deepseek-v4-xpu-<short-topic>-YYYYMMDD.patch
llm-scaler-deepseek-v4-<short-topic>-YYYYMMDD.patch
deepseek-v4-<negative-topic>-YYYYMMDD.md
```

Patch notes should include:

- exact source commit;
- why the patch exists;
- command used to test it;
- quality result;
- benchmark result;
- whether it is promoted, neutral, or rejected.

First expected patch areas:

- CUDA stream/event guards in `vllm/model_executor/models/deepseek_v4.py` and
  `vllm/model_executor/layers/deepseek_v4_attention.py`.
- XPU/correctness fallback for sparse MLA.
- AutoRound/INC naming or `extra_config` fixes if the loader rejects weights.
- B70 W4A16 MoE config once a baseline runs.
