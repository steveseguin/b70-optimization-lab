# Qwen3.6 COW Worker-State Trace Summary

- Rows: `314`
- Requests: `2`
- Spec update rows: `64`
- Nonzero spec updates: `16`
- Prepare-position rows: `64`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `64`
- `before_cached_req_update`: `62`
- `after_cached_req_counter_update`: `62`
- `after_persistent_batch_update`: `62`
- `after_spec_token_update`: `62`

## Nonzero Spec Updates

- row `5`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `10`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `1` -> `1`
- row `15`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `1` -> `1`
- row `20`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `506:507`, num_tokens_no_spec `506`, prev_draft `1` -> `1`
- row `25`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `507:508`, num_tokens_no_spec `507`, prev_draft `1` -> `1`
- row `30`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `508:509`, num_tokens_no_spec `508`, prev_draft `1` -> `1`
- row `35`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `509:510`, num_tokens_no_spec `509`, prev_draft `1` -> `1`
- row `40`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `510:511`, num_tokens_no_spec `510`, prev_draft `1` -> `1`
- row `45`, rank `0`, req `cmpl-90583939dcf68be9-0-8b7d15a2`, spec `1`, write `511:512`, num_tokens_no_spec `511`, prev_draft `1` -> `1`
- row `162`, rank `0`, req `cmpl-bcef8a4a7367bcb8-0-84e2b9a7`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `167`, rank `0`, req `cmpl-bcef8a4a7367bcb8-0-84e2b9a7`, spec `1`, write `490:491`, num_tokens_no_spec `490`, prev_draft `1` -> `1`
- row `172`, rank `0`, req `cmpl-bcef8a4a7367bcb8-0-84e2b9a7`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`
- row `177`, rank `0`, req `cmpl-bcef8a4a7367bcb8-0-84e2b9a7`, spec `1`, write `492:493`, num_tokens_no_spec `492`, prev_draft `1` -> `1`
- row `182`, rank `0`, req `cmpl-bcef8a4a7367bcb8-0-84e2b9a7`, spec `1`, write `493:494`, num_tokens_no_spec `493`, prev_draft `1` -> `1`
- row `187`, rank `0`, req `cmpl-bcef8a4a7367bcb8-0-84e2b9a7`, spec `1`, write `494:495`, num_tokens_no_spec `494`, prev_draft `1` -> `1`
- row `192`, rank `0`, req `cmpl-bcef8a4a7367bcb8-0-84e2b9a7`, spec `1`, write `495:496`, num_tokens_no_spec `495`, prev_draft `1` -> `1`

## Prepare Events

- row `1`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`
- row `11`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[503]`, seq_lens_head `[505]`
- row `16`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[504]`, seq_lens_head `[506]`
- row `21`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[505]`, seq_lens_head `[507]`
- row `26`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[506]`, seq_lens_head `[508]`
- row `31`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[507]`, seq_lens_head `[509]`
- row `36`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[508]`, seq_lens_head `[510]`
