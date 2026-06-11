# Qwen3.6 Model-Input Parity

- left: `data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611f.jsonl`
- right: `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-trace-20260611a.jsonl`
- rows compared: `80`
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
