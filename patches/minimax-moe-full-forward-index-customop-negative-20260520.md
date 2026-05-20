# MiniMax MoE Full-Forward Index Custom-Op Patch Note

Date: 2026-05-20 UTC

This source patch was tested and rejected for performance. It is documented so
the path is reproducible and does not get retried as an untested idea.

## Files

- `/home/steve/src/vllm/vllm/model_executor/models/minimax_m2.py`
- `/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/vllm/model_executor/models/minimax_m2.py`

The source and installed venv copies matched after the edit.

## Change

Added an opt-in env flag:

```bash
VLLM_MINIMAX_MOE_FULL_FORWARD_INDEX_CUSTOM_OP=1
```

Added an index registry alongside the existing name registry:

```python
_MINIMAX_M2_MOE_LAYER_INDEX_REGISTRY: list["MiniMaxM2MoE"] = []
```

Registered an additional custom op:

```python
def _minimax_m2_moe_forward_index_custom(
    hidden_states: torch.Tensor,
    layer_index: int,
) -> torch.Tensor:
    layer = _MINIMAX_M2_MOE_LAYER_INDEX_REGISTRY[layer_index]
    return layer._forward_impl_flat(hidden_states)


def _minimax_m2_moe_forward_index_fake(
    hidden_states: torch.Tensor,
    layer_index: int,
) -> torch.Tensor:
    return torch.empty_like(hidden_states)
```

During `MiniMaxM2MoE.__init__`, each layer records its index and appends itself
to the index registry. During `MiniMaxM2MoE.forward`, the promoted
full-forward custom-op guard uses the index custom op only when both
`VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1` and
`VLLM_MINIMAX_MOE_FULL_FORWARD_INDEX_CUSTOM_OP=1` are set. Otherwise the
existing promoted name-based custom-op path remains active.

## Result

Full strict quality passed, but throughput regressed:

- Mean output tok/s: `88.648258`
- Mean total tok/s: `118.197678`
- Promoted baseline output tok/s: `89.314195`

Decision: rejected. Leave the new env flag unset.
