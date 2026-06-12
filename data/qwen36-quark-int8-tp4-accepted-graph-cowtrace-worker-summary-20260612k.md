# Qwen3.6 COW Worker-State Trace Summary

- Rows: `314`
- Requests: `2`
- Spec update rows: `64`
- Nonzero spec updates: `0`
- Prepare-position rows: `64`
- Prepare request windows: `64`
- Nonzero prepare request windows: `0`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `64`
- `before_cached_req_update`: `62`
- `after_cached_req_counter_update`: `62`
- `after_persistent_batch_update`: `62`
- `after_spec_token_update`: `62`

## Nonzero Spec Updates

- none

## Prepare Events

- row `1`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[502]`, seq_lens_head `[503]`
- row `11`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[503]`, seq_lens_head `[504]`
- row `16`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[504]`, seq_lens_head `[505]`
- row `21`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[505]`, seq_lens_head `[506]`
- row `26`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[506]`, seq_lens_head `[507]`
- row `31`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[507]`, seq_lens_head `[508]`
- row `36`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[508]`, seq_lens_head `[509]`

## Nonzero Prepare Request Windows

- none
