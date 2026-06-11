# Qwen3.6 Model-Input Parity

- left: `data/qwen36-quark-int8-tp4-accepted-noasync-metadata-trace-20260611f.jsonl`
- right: `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-trace-20260611f.jsonl`
- alignment: `tp-rank-step`
- rows compared: `712`
- match all: `false`

## First Mismatch

- row: `1`
- tp rank: `0`
- rank step: `0`
- path: `top.config.num_spec_tokens`

```json
{
  "left": 0,
  "left_row": 1,
  "path": "top.config.num_spec_tokens",
  "rank_step": 0,
  "right": 1,
  "right_row": 0,
  "tp_rank": "0"
}
```
