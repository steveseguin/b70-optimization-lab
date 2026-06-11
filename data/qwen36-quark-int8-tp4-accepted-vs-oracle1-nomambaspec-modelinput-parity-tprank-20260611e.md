# Qwen3.6 Model-Input Parity

- left: `data/qwen36-quark-int8-tp4-accepted-noasync-oraclelane128-modelinput-trace-20260611b.jsonl`
- right: `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-modelinput-trace-20260611d.jsonl`
- alignment: `tp-rank-step`
- rows compared: `1016`
- match all: `false`

## First Mismatch

- row: `7`
- tp rank: `0`
- rank step: `1`
- path: `attn.slot_mappings.0.head`

```json
{
  "left": [
    33270
  ],
  "left_len": 1,
  "left_row": 7,
  "path": "attn.slot_mappings.0.head",
  "rank_step": 1,
  "right": [
    33270,
    33271
  ],
  "right_len": 2,
  "right_row": 4,
  "tp_rank": "0"
}
```
