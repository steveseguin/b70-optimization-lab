# Qwen3.6 COW Worker-State Trace Summary

- Rows: `333`
- Requests: `2`
- Spec update rows: `64`
- Nonzero spec updates: `20`
- Prepare-position rows: `64`
- Prepare request windows: `64`
- Nonzero prepare request windows: `20`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `64`
- `before_cached_req_update`: `62`
- `after_cached_req_counter_update`: `62`
- `after_persistent_batch_update`: `62`
- `after_spec_token_update`: `62`
- `after_sampled_cache_bonus_suppression`: `19`

## Nonzero Spec Updates

- row `5`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `16`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `0` -> `1`
- row `27`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `507:508`, num_tokens_no_spec `507`, prev_draft `0` -> `1`
- row `38`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `509:510`, num_tokens_no_spec `509`, prev_draft `0` -> `1`
- row `49`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `511:512`, num_tokens_no_spec `511`, prev_draft `0` -> `1`
- row `60`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `513:514`, num_tokens_no_spec `513`, prev_draft `0` -> `1`
- row `71`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `515:516`, num_tokens_no_spec `515`, prev_draft `0` -> `1`
- row `82`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `517:518`, num_tokens_no_spec `517`, prev_draft `0` -> `1`
- row `93`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `519:520`, num_tokens_no_spec `519`, prev_draft `0` -> `1`
- row `104`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `521:522`, num_tokens_no_spec `521`, prev_draft `0` -> `1`
- row `115`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `523:524`, num_tokens_no_spec `523`, prev_draft `0` -> `1`
- row `126`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `525:526`, num_tokens_no_spec `525`, prev_draft `0` -> `1`
- row `137`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, spec `1`, write `527:528`, num_tokens_no_spec `527`, prev_draft `0` -> `1`
- row `174`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `185`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `0` -> `1`
- row `196`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, spec `1`, write `493:494`, num_tokens_no_spec `493`, prev_draft `0` -> `1`
- row `207`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, spec `1`, write `495:496`, num_tokens_no_spec `495`, prev_draft `0` -> `1`
- row `218`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, spec `1`, write `497:498`, num_tokens_no_spec `497`, prev_draft `0` -> `1`
- row `229`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, spec `1`, write `499:500`, num_tokens_no_spec `499`, prev_draft `0` -> `1`
- row `240`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, spec `1`, write `501:502`, num_tokens_no_spec `501`, prev_draft `0` -> `1`

## Prepare Events

- row `1`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`
- row `12`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[503]`, seq_lens_head `[504]`
- row `17`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[504]`, seq_lens_head `[506]`
- row `23`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[505]`, seq_lens_head `[506]`
- row `28`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[506]`, seq_lens_head `[508]`
- row `34`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[507]`, seq_lens_head `[508]`
- row `39`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[508]`, seq_lens_head `[510]`

## Nonzero Prepare Request Windows

- row `6`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `503:504`, computed_cpu `502`, tokens_no_spec `503`, prev_draft `1`, positions `[502, 503]`, tokens_at_pos `[{'position': 502, 'token_id': 22791}, {'position': 503, 'token_id': 440}]`, g0:blocks=2,tail=[1, 2],slots=[33270, 33271]; g1:blocks=2,tail=[3, 4],slots=[98806, 98807]; g2:blocks=2,tail=[5, 6],slots=[164342, 164343]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4534, 4535]
- row `17`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `505:506`, computed_cpu `504`, tokens_no_spec `505`, prev_draft `1`, positions `[504, 505]`, tokens_at_pos `[{'position': 504, 'token_id': 27044}, {'position': 505, 'token_id': 47193}]`, g0:blocks=2,tail=[1, 2],slots=[33272, 33273]; g1:blocks=2,tail=[3, 4],slots=[98808, 98809]; g2:blocks=2,tail=[5, 6],slots=[164344, 164345]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4536, 4537]
- row `28`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `507:508`, computed_cpu `506`, tokens_no_spec `507`, prev_draft `1`, positions `[506, 507]`, tokens_at_pos `[{'position': 506, 'token_id': 14246}, {'position': 507, 'token_id': 8129}]`, g0:blocks=2,tail=[1, 2],slots=[33274, 33275]; g1:blocks=2,tail=[3, 4],slots=[98810, 98811]; g2:blocks=2,tail=[5, 6],slots=[164346, 164347]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4538, 4539]
- row `39`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `509:510`, computed_cpu `508`, tokens_no_spec `509`, prev_draft `1`, positions `[508, 509]`, tokens_at_pos `[{'position': 508, 'token_id': 13}, {'position': 509, 'token_id': 24985}]`, g0:blocks=2,tail=[1, 2],slots=[33276, 33277]; g1:blocks=2,tail=[3, 4],slots=[98812, 98813]; g2:blocks=2,tail=[5, 6],slots=[164348, 164349]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4540, 4541]
- row `50`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `511:512`, computed_cpu `510`, tokens_no_spec `511`, prev_draft `1`, positions `[510, 511]`, tokens_at_pos `[{'position': 510, 'token_id': 383}, {'position': 511, 'token_id': 3074}]`, g0:blocks=2,tail=[1, 2],slots=[33278, 33279]; g1:blocks=2,tail=[3, 4],slots=[98814, 98815]; g2:blocks=2,tail=[5, 6],slots=[164350, 164351]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4542, 4543]
- row `61`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `513:514`, computed_cpu `512`, tokens_no_spec `513`, prev_draft `1`, positions `[512, 513]`, tokens_at_pos `[{'position': 512, 'token_id': 43318}, {'position': 513, 'token_id': 16401}]`, g0:blocks=2,tail=[1, 2],slots=[33280, 33281]; g1:blocks=2,tail=[3, 4],slots=[98816, 98817]; g2:blocks=2,tail=[5, 6],slots=[164352, 164353]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4544, 4545]
- row `72`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `515:516`, computed_cpu `514`, tokens_no_spec `515`, prev_draft `1`, positions `[514, 515]`, tokens_at_pos `[{'position': 514, 'token_id': 4478}, {'position': 515, 'token_id': 11}]`, g0:blocks=2,tail=[1, 2],slots=[33282, 33283]; g1:blocks=2,tail=[3, 4],slots=[98818, 98819]; g2:blocks=2,tail=[5, 6],slots=[164354, 164355]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4546, 4547]
- row `83`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `517:518`, computed_cpu `516`, tokens_no_spec `517`, prev_draft `1`, positions `[516, 517]`, tokens_at_pos `[{'position': 516, 'token_id': 4779}, {'position': 517, 'token_id': 6044}]`, g0:blocks=2,tail=[1, 2],slots=[33284, 33285]; g1:blocks=2,tail=[3, 4],slots=[98820, 98821]; g2:blocks=2,tail=[5, 6],slots=[164356, 164357]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4548, 4549]
- row `94`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `519:520`, computed_cpu `518`, tokens_no_spec `519`, prev_draft `1`, positions `[518, 519]`, tokens_at_pos `[{'position': 518, 'token_id': 11}, {'position': 519, 'token_id': 321}]`, g0:blocks=2,tail=[1, 2],slots=[33286, 33287]; g1:blocks=2,tail=[3, 4],slots=[98822, 98823]; g2:blocks=2,tail=[5, 6],slots=[164358, 164359]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4550, 4551]
- row `105`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `521:522`, computed_cpu `520`, tokens_no_spec `521`, prev_draft `1`, positions `[520, 521]`, tokens_at_pos `[{'position': 520, 'token_id': 874}, {'position': 521, 'token_id': 4131}]`, g0:blocks=2,tail=[1, 2],slots=[33288, 33289]; g1:blocks=2,tail=[3, 4],slots=[98824, 98825]; g2:blocks=2,tail=[5, 6],slots=[164360, 164361]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4552, 4553]
- row `116`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `523:524`, computed_cpu `522`, tokens_no_spec `523`, prev_draft `1`, positions `[522, 523]`, tokens_at_pos `[{'position': 522, 'token_id': 4557}, {'position': 523, 'token_id': 13}]`, g0:blocks=2,tail=[1, 2],slots=[33290, 33291]; g1:blocks=2,tail=[3, 4],slots=[98826, 98827]; g2:blocks=2,tail=[5, 6],slots=[164362, 164363]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4554, 4555]
- row `127`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `525:526`, computed_cpu `524`, tokens_no_spec `525`, prev_draft `1`, positions `[524, 525]`, tokens_at_pos `[{'position': 524, 'token_id': 198}, {'position': 525, 'token_id': 22791}]`, g0:blocks=2,tail=[1, 2],slots=[33292, 33293]; g1:blocks=2,tail=[3, 4],slots=[98828, 98829]; g2:blocks=2,tail=[5, 6],slots=[164364, 164365]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4556, 4557]
- row `138`, rank `0`, req `cmpl-8eb9a875b154b7f6-0-aedc5e55`, idx `0`, spec `1`, write `527:528`, computed_cpu `526`, tokens_no_spec `527`, prev_draft `1`, positions `[526, 527]`, tokens_at_pos `[{'position': 526, 'token_id': 440}, {'position': 527, 'token_id': 829}]`, g0:blocks=2,tail=[1, 2],slots=[33294, 33295]; g1:blocks=2,tail=[3, 4],slots=[98830, 98831]; g2:blocks=2,tail=[5, 6],slots=[164366, 164367]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4558, 4559]
- row `175`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[8, 9],slots=[262632, 262633]; g1:blocks=2,tail=[10, 11],slots=[328168, 328169]; g2:blocks=2,tail=[12, 13],slots=[393704, 393705]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8552, 8553]
- row `186`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, idx `0`, spec `1`, write `491:492`, computed_cpu `490`, tokens_no_spec `491`, prev_draft `1`, positions `[490, 491]`, tokens_at_pos `[{'position': 490, 'token_id': 13}, {'position': 491, 'token_id': 78503}]`, g0:blocks=2,tail=[8, 9],slots=[262634, 262635]; g1:blocks=2,tail=[10, 11],slots=[328170, 328171]; g2:blocks=2,tail=[12, 13],slots=[393706, 393707]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8554, 8555]
- row `197`, rank `0`, req `cmpl-afca347990bfd32e-0-996685b4`, idx `0`, spec `1`, write `493:494`, computed_cpu `492`, tokens_no_spec `493`, prev_draft `1`, positions `[492, 493]`, tokens_at_pos `[{'position': 492, 'token_id': 4581}, {'position': 493, 'token_id': 2468}]`, g0:blocks=2,tail=[8, 9],slots=[262636, 262637]; g1:blocks=2,tail=[10, 11],slots=[328172, 328173]; g2:blocks=2,tail=[12, 13],slots=[393708, 393709]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8556, 8557]
