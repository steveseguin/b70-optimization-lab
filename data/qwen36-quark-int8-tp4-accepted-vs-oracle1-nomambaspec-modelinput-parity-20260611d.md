# Qwen3.6 Model-Input Parity

- left: `data/qwen36-quark-int8-tp4-accepted-noasync-oraclelane128-modelinput-trace-20260611b.jsonl`
- right: `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-modelinput-trace-20260611d.jsonl`
- rows compared: `1016`
- match all: `false`

## First Mismatch

- row: `0`
- path: `top.tp_rank`

```json
{
  "left": 1,
  "path": "top.tp_rank",
  "right": 3,
  "row": 0
}
```
