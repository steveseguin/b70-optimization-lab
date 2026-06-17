# Qwen3.6 W8A8 Middle Layerlet Check

- timestamp_utc: `2026-06-15T04:28:42.951873+00:00`
- device: `Intel(R) Arc(TM) Pro B70 Graphics`
- overall_passed: `False`
- graph_replay_requested: `True`
- require_graph: `True`

| case | prefix | prefix graph | layerlet | layerlet graph | gemm1 diff | q equal | scale diff | out diff |
| --- | --- | --- | --- | --- | ---: | --- | ---: | ---: |
| tiny_sparse | True | True (executed) | False | False (executed) | 0 | False | 1.92237e-06 | 0.00390625 |
| single_hot_expert | True | True (executed) | False | False (executed) | 0 | False | 3.07579e-05 | 0.0117188 |
| decode_like_sparse | True | True (executed) | False | False (executed) | 0 | False | 3.07579e-05 | 0.0390625 |
| dense_small | True | True (executed) | False | False (executed) | 0 | False | 0 | 0.0175781 |
