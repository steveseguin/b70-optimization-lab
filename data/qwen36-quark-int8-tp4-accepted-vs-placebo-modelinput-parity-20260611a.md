# Qwen3.6 Model-Input Parity

- left: `data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611f.jsonl`
- right: `data/qwen36-quark-int8-tp4-placebo-modelinput-trace-20260611a.jsonl`
- rows compared: `80`
- match all: `false`

## First Mismatch

- row: `0`
- path: `attn.slot_mappings.1.head[0]`

```json
{
  "left": 65536,
  "path": "attn.slot_mappings.1.head[0]",
  "right": 98304,
  "row": 0
}
```
