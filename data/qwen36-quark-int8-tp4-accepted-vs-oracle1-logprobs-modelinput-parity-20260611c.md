# Qwen3.6 Model-Input Parity

- left: `data/qwen36-quark-int8-tp4-accepted-noasync-logprobs-modelinput-trace-20260611c.jsonl`
- right: `data/qwen36-quark-int8-tp4-oracle1-logprobs-modelinput-trace-20260611c.jsonl`
- rows compared: `968`
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
