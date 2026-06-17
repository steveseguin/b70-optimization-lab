# Qwen3.6 COW Worker-State Trace Summary

- Rows: `294`
- Requests: `2`
- Spec update rows: `60`
- Nonzero spec updates: `6`
- Prepare-position rows: `60`
- Prepare request windows: `60`
- Nonzero prepare request windows: `6`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `60`
- `before_cached_req_update`: `58`
- `after_cached_req_counter_update`: `58`
- `after_persistent_batch_update`: `58`
- `after_spec_token_update`: `58`

## Nonzero Spec Updates

- row `10`, rank `0`, req `cmpl-975f60d8a448fb1c-0-a44ae2d9`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `0` -> `1`
- row `15`, rank `0`, req `cmpl-975f60d8a448fb1c-0-a44ae2d9`, spec `1`, write `506:507`, num_tokens_no_spec `506`, prev_draft `1` -> `1`
- row `20`, rank `0`, req `cmpl-975f60d8a448fb1c-0-a44ae2d9`, spec `1`, write `508:509`, num_tokens_no_spec `508`, prev_draft `1` -> `1`
- row `25`, rank `0`, req `cmpl-975f60d8a448fb1c-0-a44ae2d9`, spec `1`, write `510:511`, num_tokens_no_spec `510`, prev_draft `1` -> `1`
- row `147`, rank `0`, req `cmpl-a415a4dec2b1cf7f-0-83233257`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `152`, rank `0`, req `cmpl-a415a4dec2b1cf7f-0-83233257`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`

## Prepare Events

- row `1`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[502]`, seq_lens_head `[503]`
- row `11`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[503]`, seq_lens_head `[505]`
- row `16`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[505]`, seq_lens_head `[507]`
- row `21`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[507]`, seq_lens_head `[509]`
- row `26`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[509]`, seq_lens_head `[511]`
- row `31`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[510]`, seq_lens_head `[511]`
- row `36`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[511]`, seq_lens_head `[512]`

## Nonzero Prepare Request Windows

- row `11`, rank `0`, req `cmpl-975f60d8a448fb1c-0-a44ae2d9`, idx `0`, spec `1`, write `504:505`, computed_cpu `503`, tokens_no_spec `504`, prev_draft `1`, positions `[503, 504]`, tokens_at_pos `[{'position': 503, 'token_id': 440}, {'position': 504, 'token_id': 27044}]`, g0:blocks=2,tail=[1, 2],slots=[33271, 33272]; g1:blocks=2,tail=[3, 4],slots=[98807, 98808]; g2:blocks=2,tail=[5, 6],slots=[164343, 164344]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4535, 4536]
- row `16`, rank `0`, req `cmpl-975f60d8a448fb1c-0-a44ae2d9`, idx `0`, spec `1`, write `506:507`, computed_cpu `505`, tokens_no_spec `506`, prev_draft `1`, positions `[505, 506]`, tokens_at_pos `[{'position': 505, 'token_id': 47193}, {'position': 506, 'token_id': 14246}]`, g0:blocks=2,tail=[1, 2],slots=[33273, 33274]; g1:blocks=2,tail=[3, 4],slots=[98809, 98810]; g2:blocks=2,tail=[5, 6],slots=[164345, 164346]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4537, 4538]
- row `21`, rank `0`, req `cmpl-975f60d8a448fb1c-0-a44ae2d9`, idx `0`, spec `1`, write `508:509`, computed_cpu `507`, tokens_no_spec `508`, prev_draft `1`, positions `[507, 508]`, tokens_at_pos `[{'position': 507, 'token_id': 8129}, {'position': 508, 'token_id': 13}]`, g0:blocks=2,tail=[1, 2],slots=[33275, 33276]; g1:blocks=2,tail=[3, 4],slots=[98811, 98812]; g2:blocks=2,tail=[5, 6],slots=[164347, 164348]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4539, 4540]
- row `26`, rank `0`, req `cmpl-975f60d8a448fb1c-0-a44ae2d9`, idx `0`, spec `1`, write `510:511`, computed_cpu `509`, tokens_no_spec `510`, prev_draft `1`, positions `[509, 510]`, tokens_at_pos `[{'position': 509, 'token_id': 271}, {'position': 510, 'token_id': 760}]`, g0:blocks=2,tail=[1, 2],slots=[33277, 33278]; g1:blocks=2,tail=[3, 4],slots=[98813, 98814]; g2:blocks=2,tail=[5, 6],slots=[164349, 164350]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4541, 4542]
- row `148`, rank `0`, req `cmpl-a415a4dec2b1cf7f-0-83233257`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[8, 9],slots=[262632, 262633]; g1:blocks=2,tail=[10, 11],slots=[328168, 328169]; g2:blocks=2,tail=[12, 13],slots=[393704, 393705]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8552, 8553]
- row `153`, rank `0`, req `cmpl-a415a4dec2b1cf7f-0-83233257`, idx `0`, spec `1`, write `491:492`, computed_cpu `490`, tokens_no_spec `491`, prev_draft `1`, positions `[490, 491]`, tokens_at_pos `[{'position': 490, 'token_id': 13}, {'position': 491, 'token_id': 78503}]`, g0:blocks=2,tail=[8, 9],slots=[262634, 262635]; g1:blocks=2,tail=[10, 11],slots=[328170, 328171]; g2:blocks=2,tail=[12, 13],slots=[393706, 393707]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8554, 8555]
