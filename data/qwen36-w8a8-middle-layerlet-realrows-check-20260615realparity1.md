# Qwen3.6 W8A8 Middle Layerlet Check

- timestamp_utc: `2026-06-15T21:21:00.238300+00:00`
- device: `Intel(R) Arc(TM) Pro B70 Graphics`
- overall_passed: `True`
- graph_replay_requested: `True`
- require_graph: `True`

| case | prefix | prefix graph | rows ref | layerlet | layerlet graph | rows out diff | gemm1 diff | q equal | scale diff | out diff |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| tiny_sparse | True | True (executed) | True | True | True (executed) | 0 | 0 | True | 0 | 0 |
| single_hot_expert | True | True (executed) | True | True | True (executed) | 0 | 0 | True | 0 | 0 |
| decode_like_sparse | True | True (executed) | True | True | True (executed) | 0 | 0 | True | 0 | 0 |
| dense_small | True | True (executed) | True | True | True (executed) | 0 | 0 | True | 0 | 0 |
