# Qwen3.6 W8A8 Offset Route Gate

- Decision: `rejected`.
- Eager route replay exact: `True`.
- Offset speed gate passed: `False`.
- Endpoint provenance passed: `False`.

## No-Server Route Replay

| profile | rows | mean xpu_fused_moe us | mean scratch us | mean fused-prologue us | mean fused-prologue offset us | max diff |
|---|---:|---:|---:|---:|---:|---:|
| base integration | 12 | 347.086 | 382.570 | 356.576 | 269.867 | 0.000000 |
| offset env integration | 12 | 409.229 | 445.174 | 297.177 | 225.970 | 0.000000 |

## Endpoint Gate

- `repetitive_kernel_notes[14]`: expected `4752`, actual `6126`, ok `False`.
- `natural_latency_plan[17]`: expected `11436`, actual `11436`, ok `True`.
- `natural_latency_plan[25]`: expected `198`, actual `271`, ok `False`.

Endpoint errors:
- natural_latency_plan output prefix drift: {'index': 25, 'current': 271, 'baseline': 198, 'current_context': [11436, 29796, 11, 321, 874, 4131, 4557, 13, 271, 248068, 198, 90700, 8340, 25, 271], 'baseline_context': [11436, 29796, 11, 321, 874, 4131, 4557, 13, 198, 22791, 440, 27044, 47193, 14246, 8129]}
- repetitive_kernel_notes output prefix drift: {'index': 14, 'current': 6126, 'baseline': 4752, 'current_context': [1345, 28043, 7072, 3817, 22188, 13, 15153, 1543, 6126, 16401, 85683, 15162, 5832, 4618, 3817, 17856], 'baseline_context': [1345, 28043, 7072, 3817, 22188, 13, 15153, 1543, 4752, 271, 248068, 198, 8160, 579, 264, 7047]}
- sentinel failed: {'name': 'repetitive_kernel_notes', 'index': 14, 'expected_token_id': 4752, 'actual_token_id': 6126, 'ok': False}
- sentinel failed: {'name': 'natural_latency_plan', 'index': 25, 'expected_token_id': 198, 'actual_token_id': 271, 'ok': False}

## Interpretation

- Eager route replay is useful, but it is not sufficient for promotion: the endpoint failed provenance while this eager gate stayed exact.
- The offset-env integration is slower than base in no-server replay, so the offset path is rejected on performance even before endpoint quality is considered.
- The next correctness gate for similar ideas must exercise the compiled/graph serving path or capture live graph-path tensors, not only eager synthetic tensors.
