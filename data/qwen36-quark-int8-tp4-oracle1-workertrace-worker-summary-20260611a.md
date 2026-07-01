# Qwen3.6 COW Worker-State Trace Summary

- Rows: `244`
- Requests: `2`
- Spec update rows: `50`
- Nonzero spec updates: `15`
- Prepare-position rows: `50`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `50`
- `before_cached_req_update`: `48`
- `after_cached_req_counter_update`: `48`
- `after_persistent_batch_update`: `48`
- `after_spec_token_update`: `48`

## Nonzero Spec Updates

- row `5`, rank `0`, req `cmpl-a036bf49c31e1bd7-0-910cd43a`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `10`, rank `0`, req `cmpl-a036bf49c31e1bd7-0-910cd43a`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `1` -> `1`
- row `15`, rank `0`, req `cmpl-a036bf49c31e1bd7-0-910cd43a`, spec `1`, write `507:508`, num_tokens_no_spec `507`, prev_draft `1` -> `1`
- row `20`, rank `0`, req `cmpl-a036bf49c31e1bd7-0-910cd43a`, spec `1`, write `509:510`, num_tokens_no_spec `509`, prev_draft `1` -> `1`
- row `25`, rank `0`, req `cmpl-a036bf49c31e1bd7-0-910cd43a`, spec `1`, write `511:512`, num_tokens_no_spec `511`, prev_draft `1` -> `1`
- row `30`, rank `0`, req `cmpl-a036bf49c31e1bd7-0-910cd43a`, spec `1`, write `513:514`, num_tokens_no_spec `513`, prev_draft `1` -> `1`
- row `35`, rank `0`, req `cmpl-a036bf49c31e1bd7-0-910cd43a`, spec `1`, write `515:516`, num_tokens_no_spec `515`, prev_draft `1` -> `1`
- row `127`, rank `0`, req `cmpl-84f7445f48f11315-0-b01312e5`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `132`, rank `0`, req `cmpl-84f7445f48f11315-0-b01312e5`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`
- row `137`, rank `0`, req `cmpl-84f7445f48f11315-0-b01312e5`, spec `1`, write `493:494`, num_tokens_no_spec `493`, prev_draft `1` -> `1`
- row `142`, rank `0`, req `cmpl-84f7445f48f11315-0-b01312e5`, spec `1`, write `495:496`, num_tokens_no_spec `495`, prev_draft `1` -> `1`
- row `147`, rank `0`, req `cmpl-84f7445f48f11315-0-b01312e5`, spec `1`, write `497:498`, num_tokens_no_spec `497`, prev_draft `1` -> `1`
- row `152`, rank `0`, req `cmpl-84f7445f48f11315-0-b01312e5`, spec `1`, write `499:500`, num_tokens_no_spec `499`, prev_draft `1` -> `1`
- row `157`, rank `0`, req `cmpl-84f7445f48f11315-0-b01312e5`, spec `1`, write `501:502`, num_tokens_no_spec `501`, prev_draft `1` -> `1`
- row `162`, rank `0`, req `cmpl-84f7445f48f11315-0-b01312e5`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `1` -> `1`

## Prepare Events

- row `1`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`
- row `11`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[504]`, seq_lens_head `[506]`
- row `16`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[506]`, seq_lens_head `[508]`
- row `21`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[508]`, seq_lens_head `[510]`
- row `26`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[510]`, seq_lens_head `[512]`
- row `31`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[512]`, seq_lens_head `[514]`
- row `36`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[514]`, seq_lens_head `[516]`
