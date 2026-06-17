# Qwen3.6 W8A8 Middle Layerlet Check

- timestamp_utc: `2026-06-14T17:10:45.536610+00:00`
- device: `Intel(R) Arc(TM) Pro B70 Graphics`
- overall_passed: `True`
- graph_replay_requested: `False`
- require_graph: `False`

| case | eager | graph | gemm1 diff | q equal | scale diff | out diff |
| --- | --- | --- | ---: | --- | ---: | ---: |
| tiny_sparse | True | n/a | 0 | True | 0 | 0 |
| single_hot_expert | True | n/a | 0 | True | 0 | 0 |
| decode_like_sparse | True | n/a | 0 | True | 0 | 0 |
| dense_small | True | n/a | 0 | True | 0 | 0 |
