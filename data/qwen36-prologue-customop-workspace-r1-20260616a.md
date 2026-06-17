# Qwen3.6 Prologue TP Capture Repro

- overall_status: `fail`
- ranks: `1`
- captures: `1`
- layers_per_capture: `1`
- distinct_layers: `False`
- endpoint_context: `True`
- workspace_manager: `True`
- custom_op_wrapper: `True`
- post_copy: `True`

| rank | status | captures | replays | error |
| ---: | --- | ---: | ---: | --- |
| 0 | fail | 0 | 0 | infer_schema(func): Unsupported type annotation torch.Tensor. It is not a type. Got func with signature (hidden_states: 'torch.Tensor', router_logits: 'torch.Tensor', shared_experts_input: 'torch.Tensor', input_ids: 'torch.Tensor \| None', layer_index: 'int') -> 'tuple[torch.Tensor, torch.Tensor]') |
