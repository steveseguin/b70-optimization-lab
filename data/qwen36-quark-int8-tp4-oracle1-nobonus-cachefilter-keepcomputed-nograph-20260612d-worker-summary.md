# Qwen3.6 COW Worker-State Trace Summary

- Rows: `316`
- Requests: `2`
- Spec update rows: `64`
- Nonzero spec updates: `4`
- Prepare-position rows: `64`
- Prepare request windows: `64`
- Nonzero prepare request windows: `4`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `64`
- `before_cached_req_update`: `62`
- `after_cached_req_counter_update`: `62`
- `after_persistent_batch_update`: `62`
- `after_spec_token_update`: `62`
- `after_sampled_cache_bonus_suppression`: `2`

## Nonzero Spec Updates

- row `5`, rank `0`, req `cmpl-957211a127b2ee63-0-b5740812`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `11`, rank `0`, req `cmpl-957211a127b2ee63-0-b5740812`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `1` -> `1`
- row `163`, rank `0`, req `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `169`, rank `0`, req `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed`, spec `1`, write `490:491`, num_tokens_no_spec `490`, prev_draft `1` -> `1`

## Prepare Events

- row `1`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`
- row `12`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[504]`, seq_lens_head `[505]`
- row `17`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[504]`, seq_lens_head `[505]`
- row `22`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[505]`, seq_lens_head `[506]`
- row `27`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[506]`, seq_lens_head `[507]`
- row `32`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[507]`, seq_lens_head `[508]`
- row `37`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[508]`, seq_lens_head `[509]`

## Nonzero Prepare Request Windows

- row `6`, rank `0`, req `cmpl-957211a127b2ee63-0-b5740812`, idx `0`, spec `1`, write `503:504`, computed_cpu `502`, tokens_no_spec `503`, prev_draft `1`, positions `[502, 503]`, tokens_at_pos `[{'position': 502, 'token_id': 22791}, {'position': 503, 'token_id': 440}]`, g0:blocks=2,tail=[1, 2],slots=[33270, 33271]; g1:blocks=2,tail=[3, 4],slots=[98806, 98807]; g2:blocks=2,tail=[5, 6],slots=[164342, 164343]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4534, 4535]
- row `12`, rank `0`, req `cmpl-957211a127b2ee63-0-b5740812`, idx `0`, spec `1`, write `504:505`, computed_cpu `504`, tokens_no_spec `504`, prev_draft `1`, positions `[504]`, tokens_at_pos `[{'position': 504, 'token_id': 27044}]`, g0:blocks=2,tail=[1, 2],slots=[33272]; g1:blocks=2,tail=[3, 4],slots=[98808]; g2:blocks=2,tail=[5, 6],slots=[164344]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4536]
- row `164`, rank `0`, req `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[8, 9],slots=[262632, 262633]; g1:blocks=2,tail=[10, 11],slots=[328168, 328169]; g2:blocks=2,tail=[12, 13],slots=[393704, 393705]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8552, 8553]
- row `170`, rank `0`, req `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed`, idx `0`, spec `1`, write `490:491`, computed_cpu `490`, tokens_no_spec `490`, prev_draft `1`, positions `[490]`, tokens_at_pos `[{'position': 490, 'token_id': 13}]`, g0:blocks=2,tail=[8, 9],slots=[262634]; g1:blocks=2,tail=[10, 11],slots=[328170]; g2:blocks=2,tail=[12, 13],slots=[393706]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8554]
