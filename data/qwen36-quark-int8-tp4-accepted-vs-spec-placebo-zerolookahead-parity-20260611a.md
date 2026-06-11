# Qwen3.6 Model-Input Parity

- left: `data/qwen36-quark-int8-tp4-accepted-modelinput-zerolookahead-trace-20260611a.jsonl`
- right: `data/qwen36-quark-int8-tp4-spec-placebo-zerolookahead-trace-20260611a.jsonl`
- rows compared: `64`
- match all: `false`

## First Mismatch

- row: `26`
- path: `input_batch.input_ids.head[0]`

```json
{
  "left": 198,
  "path": "input_batch.input_ids.head[0]",
  "right": 271,
  "row": 26
}
```
