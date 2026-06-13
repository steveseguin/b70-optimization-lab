# Qwen3.6 COW Worker-State Trace Summary

- Rows: `5112`
- Requests: `2`
- Spec update rows: `1024`
- Nonzero spec updates: `24`
- Prepare-position rows: `1024`
- Prepare request windows: `1024`
- Nonzero prepare request windows: `24`

## Stage Counts

- `after_new_req_add_spec_update`: `8`
- `after_prepare_positions`: `1024`
- `before_cached_req_update`: `1016`
- `after_cached_req_counter_update`: `1016`
- `after_persistent_batch_update`: `1016`
- `after_spec_token_update`: `1016`
- `after_sampled_cache_bonus_suppression`: `16`

## Nonzero Spec Updates

- row `17`, rank `2`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `18`, rank `3`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `19`, rank `0`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `26`, rank `1`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `32`, rank `0`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `1` -> `1`
- row `37`, rank `3`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `1` -> `1`
- row `44`, rank `2`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `1` -> `1`
- row `50`, rank `1`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `1` -> `1`
- row `68`, rank `3`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `1` -> `1`
- row `69`, rank `2`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `1` -> `1`
- row `70`, rank `0`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `1` -> `1`
- row `71`, rank `1`, req `cmpl-98526fea36905b9e-0-94b89b12`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `1` -> `1`
- row `2576`, rank `0`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `2577`, rank `2`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `2578`, rank `3`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `2579`, rank `1`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `2600`, rank `3`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `490:491`, num_tokens_no_spec `490`, prev_draft `1` -> `1`
- row `2601`, rank `2`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `490:491`, num_tokens_no_spec `490`, prev_draft `1` -> `1`
- row `2602`, rank `1`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `490:491`, num_tokens_no_spec `490`, prev_draft `1` -> `1`
- row `2603`, rank `0`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `490:491`, num_tokens_no_spec `490`, prev_draft `1` -> `1`
- row `2624`, rank `1`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`
- row `2625`, rank `3`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`
- row `2626`, rank `2`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`
- row `2627`, rank `0`, req `cmpl-80ff2925311dc22c-0-98059a90`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`

## Prepare Events

- row `4`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `5`, rank `2`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `3`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `7`, rank `1`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `20`, rank `2`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`
- row `21`, rank `3`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`
- row `22`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`
- row `27`, rank `1`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`

## Nonzero Prepare Request Windows

- row `20`, rank `2`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `503:504`, computed_cpu `502`, tokens_no_spec `503`, prev_draft `1`, positions `[502, 503]`, tokens_at_pos `[{'position': 502, 'token_id': 22791}, {'position': 503, 'token_id': 440}]`, g0:blocks=2,tail=[1, 2],slots=[33270, 33271]; g1:blocks=2,tail=[3, 4],slots=[98806, 98807]; g2:blocks=2,tail=[5, 6],slots=[164342, 164343]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4534, 4535]
- row `21`, rank `3`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `503:504`, computed_cpu `502`, tokens_no_spec `503`, prev_draft `1`, positions `[502, 503]`, tokens_at_pos `[{'position': 502, 'token_id': 22791}, {'position': 503, 'token_id': 440}]`, g0:blocks=2,tail=[1, 2],slots=[33270, 33271]; g1:blocks=2,tail=[3, 4],slots=[98806, 98807]; g2:blocks=2,tail=[5, 6],slots=[164342, 164343]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4534, 4535]
- row `22`, rank `0`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `503:504`, computed_cpu `502`, tokens_no_spec `503`, prev_draft `1`, positions `[502, 503]`, tokens_at_pos `[{'position': 502, 'token_id': 22791}, {'position': 503, 'token_id': 440}]`, g0:blocks=2,tail=[1, 2],slots=[33270, 33271]; g1:blocks=2,tail=[3, 4],slots=[98806, 98807]; g2:blocks=2,tail=[5, 6],slots=[164342, 164343]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4534, 4535]
- row `27`, rank `1`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `503:504`, computed_cpu `502`, tokens_no_spec `503`, prev_draft `1`, positions `[502, 503]`, tokens_at_pos `[{'position': 502, 'token_id': 22791}, {'position': 503, 'token_id': 440}]`, g0:blocks=2,tail=[1, 2],slots=[33270, 33271]; g1:blocks=2,tail=[3, 4],slots=[98806, 98807]; g2:blocks=2,tail=[5, 6],slots=[164342, 164343]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4534, 4535]
- row `38`, rank `0`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `504:505`, computed_cpu `503`, tokens_no_spec `504`, prev_draft `1`, positions `[503, 504]`, tokens_at_pos `[{'position': 503, 'token_id': 440}, {'position': 504, 'token_id': 27044}]`, g0:blocks=2,tail=[1, 2],slots=[33271, 33272]; g1:blocks=2,tail=[3, 4],slots=[98807, 98808]; g2:blocks=2,tail=[5, 6],slots=[164343, 164344]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4535, 4536]
- row `39`, rank `3`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `504:505`, computed_cpu `503`, tokens_no_spec `504`, prev_draft `1`, positions `[503, 504]`, tokens_at_pos `[{'position': 503, 'token_id': 440}, {'position': 504, 'token_id': 27044}]`, g0:blocks=2,tail=[1, 2],slots=[33271, 33272]; g1:blocks=2,tail=[3, 4],slots=[98807, 98808]; g2:blocks=2,tail=[5, 6],slots=[164343, 164344]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4535, 4536]
- row `45`, rank `2`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `504:505`, computed_cpu `503`, tokens_no_spec `504`, prev_draft `1`, positions `[503, 504]`, tokens_at_pos `[{'position': 503, 'token_id': 440}, {'position': 504, 'token_id': 27044}]`, g0:blocks=2,tail=[1, 2],slots=[33271, 33272]; g1:blocks=2,tail=[3, 4],slots=[98807, 98808]; g2:blocks=2,tail=[5, 6],slots=[164343, 164344]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4535, 4536]
- row `51`, rank `1`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `504:505`, computed_cpu `503`, tokens_no_spec `504`, prev_draft `1`, positions `[503, 504]`, tokens_at_pos `[{'position': 503, 'token_id': 440}, {'position': 504, 'token_id': 27044}]`, g0:blocks=2,tail=[1, 2],slots=[33271, 33272]; g1:blocks=2,tail=[3, 4],slots=[98807, 98808]; g2:blocks=2,tail=[5, 6],slots=[164343, 164344]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4535, 4536]
- row `72`, rank `2`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `505:506`, computed_cpu `504`, tokens_no_spec `505`, prev_draft `1`, positions `[504, 505]`, tokens_at_pos `[{'position': 504, 'token_id': 27044}, {'position': 505, 'token_id': 47193}]`, g0:blocks=2,tail=[1, 2],slots=[33272, 33273]; g1:blocks=2,tail=[3, 4],slots=[98808, 98809]; g2:blocks=2,tail=[5, 6],slots=[164344, 164345]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4536, 4537]
- row `73`, rank `3`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `505:506`, computed_cpu `504`, tokens_no_spec `505`, prev_draft `1`, positions `[504, 505]`, tokens_at_pos `[{'position': 504, 'token_id': 27044}, {'position': 505, 'token_id': 47193}]`, g0:blocks=2,tail=[1, 2],slots=[33272, 33273]; g1:blocks=2,tail=[3, 4],slots=[98808, 98809]; g2:blocks=2,tail=[5, 6],slots=[164344, 164345]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4536, 4537]
- row `74`, rank `0`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `505:506`, computed_cpu `504`, tokens_no_spec `505`, prev_draft `1`, positions `[504, 505]`, tokens_at_pos `[{'position': 504, 'token_id': 27044}, {'position': 505, 'token_id': 47193}]`, g0:blocks=2,tail=[1, 2],slots=[33272, 33273]; g1:blocks=2,tail=[3, 4],slots=[98808, 98809]; g2:blocks=2,tail=[5, 6],slots=[164344, 164345]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4536, 4537]
- row `75`, rank `1`, req `cmpl-98526fea36905b9e-0-94b89b12`, idx `0`, spec `1`, write `505:506`, computed_cpu `504`, tokens_no_spec `505`, prev_draft `1`, positions `[504, 505]`, tokens_at_pos `[{'position': 504, 'token_id': 27044}, {'position': 505, 'token_id': 47193}]`, g0:blocks=2,tail=[1, 2],slots=[33272, 33273]; g1:blocks=2,tail=[3, 4],slots=[98808, 98809]; g2:blocks=2,tail=[5, 6],slots=[164344, 164345]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4536, 4537]
- row `2580`, rank `3`, req `cmpl-80ff2925311dc22c-0-98059a90`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[9, 10],slots=[295400, 295401]; g1:blocks=2,tail=[11, 12],slots=[360936, 360937]; g2:blocks=2,tail=[13, 14],slots=[426472, 426473]; g3:blocks=9,tail=[136, 137, 138, 139, 140, 141, 142, 143],slots=[9128, 9129]
- row `2581`, rank `2`, req `cmpl-80ff2925311dc22c-0-98059a90`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[9, 10],slots=[295400, 295401]; g1:blocks=2,tail=[11, 12],slots=[360936, 360937]; g2:blocks=2,tail=[13, 14],slots=[426472, 426473]; g3:blocks=9,tail=[136, 137, 138, 139, 140, 141, 142, 143],slots=[9128, 9129]
- row `2582`, rank `1`, req `cmpl-80ff2925311dc22c-0-98059a90`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[9, 10],slots=[295400, 295401]; g1:blocks=2,tail=[11, 12],slots=[360936, 360937]; g2:blocks=2,tail=[13, 14],slots=[426472, 426473]; g3:blocks=9,tail=[136, 137, 138, 139, 140, 141, 142, 143],slots=[9128, 9129]
- row `2583`, rank `0`, req `cmpl-80ff2925311dc22c-0-98059a90`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[9, 10],slots=[295400, 295401]; g1:blocks=2,tail=[11, 12],slots=[360936, 360937]; g2:blocks=2,tail=[13, 14],slots=[426472, 426473]; g3:blocks=9,tail=[136, 137, 138, 139, 140, 141, 142, 143],slots=[9128, 9129]
