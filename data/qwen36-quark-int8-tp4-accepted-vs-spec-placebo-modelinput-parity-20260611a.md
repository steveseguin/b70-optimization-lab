# Qwen3.6 Model-Input Parity

- left: `data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611g.jsonl`
- right: `data/qwen36-quark-int8-tp4-spec-placebo-modelinput-trace-20260611a.jsonl`
- rows compared: `64`
- match all: `false`

## First Mismatch

- row: `0`
- path: `attn.block_tables.0.cpu.head`

```json
{
  "left": [
    1
  ],
  "left_len": 1,
  "path": "attn.block_tables.0.cpu.head",
  "right": [
    1,
    2
  ],
  "right_len": 2,
  "row": 0
}
```
