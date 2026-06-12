# Qwen3.6 MoE Live-ABI Graph Capture Gate

- Status: `pass`.
- Records total: `228`.
- Records after filters: `228`.
- Failures: `none`.
- Has stream-capture skip: `True`.
- Has deferred post-capture sample: `True`.

## Observation Counts

- `deferred_post_capture_sample`: `60`
- `eager_or_post_capture_checksum`: `108`
- `stream_capture_skip_no_tensor_copy`: `60`

## Requirements

- `layer_regex`: `None`
- `rank`: `0`
- `require_capture_skip`: `True`
- `require_deferred_sample`: `True`

## Interpretation

Passing this gate proves the diagnostic log saw the requested graph-capture evidence. It does not prove model quality, endpoint speed, or full graph/eager tensor parity by itself.
