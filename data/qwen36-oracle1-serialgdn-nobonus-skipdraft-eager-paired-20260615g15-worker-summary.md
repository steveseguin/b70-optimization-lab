# Qwen3.6 COW Worker-State Trace Summary

- Rows: `340`
- Requests: `2`
- Spec update rows: `64`
- Nonzero spec updates: `28`
- Prepare-position rows: `64`
- Prepare request windows: `64`
- Nonzero prepare request windows: `28`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `64`
- `before_cached_req_update`: `62`
- `after_cached_req_counter_update`: `62`
- `after_persistent_batch_update`: `62`
- `after_spec_token_update`: `62`
- `after_sampled_cache_bonus_suppression`: `26`

## Nonzero Spec Updates

- row `10`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `0` -> `1`
- row `21`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `506:507`, num_tokens_no_spec `506`, prev_draft `0` -> `1`
- row `32`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `508:509`, num_tokens_no_spec `508`, prev_draft `0` -> `1`
- row `43`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `510:511`, num_tokens_no_spec `510`, prev_draft `0` -> `1`
- row `54`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `512:513`, num_tokens_no_spec `512`, prev_draft `0` -> `1`
- row `65`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `514:515`, num_tokens_no_spec `514`, prev_draft `0` -> `1`
- row `76`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `516:517`, num_tokens_no_spec `516`, prev_draft `0` -> `1`
- row `87`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `518:519`, num_tokens_no_spec `518`, prev_draft `0` -> `1`
- row `113`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `523:524`, num_tokens_no_spec `523`, prev_draft `0` -> `1`
- row `118`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `524:525`, num_tokens_no_spec `524`, prev_draft `1` -> `1`
- row `129`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `526:527`, num_tokens_no_spec `526`, prev_draft `0` -> `1`
- row `140`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, spec `1`, write `528:529`, num_tokens_no_spec `528`, prev_draft `0` -> `1`
- row `172`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `183`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `0` -> `1`
- row `194`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `493:494`, num_tokens_no_spec `493`, prev_draft `0` -> `1`
- row `205`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `495:496`, num_tokens_no_spec `495`, prev_draft `0` -> `1`
- row `216`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `497:498`, num_tokens_no_spec `497`, prev_draft `0` -> `1`
- row `227`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `499:500`, num_tokens_no_spec `499`, prev_draft `0` -> `1`
- row `238`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `501:502`, num_tokens_no_spec `501`, prev_draft `0` -> `1`
- row `249`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `260`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `0` -> `1`
- row `271`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `507:508`, num_tokens_no_spec `507`, prev_draft `0` -> `1`
- row `282`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `509:510`, num_tokens_no_spec `509`, prev_draft `0` -> `1`
- row `293`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `511:512`, num_tokens_no_spec `511`, prev_draft `0` -> `1`
- row `304`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `513:514`, num_tokens_no_spec `513`, prev_draft `0` -> `1`
- row `315`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `515:516`, num_tokens_no_spec `515`, prev_draft `0` -> `1`
- row `326`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `517:518`, num_tokens_no_spec `517`, prev_draft `0` -> `1`
- row `337`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, spec `1`, write `519:520`, num_tokens_no_spec `519`, prev_draft `0` -> `1`

## Prepare Events

- row `1`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[502]`, seq_lens_head `[503]`
- row `11`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[503]`, seq_lens_head `[505]`
- row `17`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[504]`, seq_lens_head `[505]`
- row `22`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[505]`, seq_lens_head `[507]`
- row `28`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[506]`, seq_lens_head `[507]`
- row `33`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[507]`, seq_lens_head `[509]`
- row `39`, rank `0`, reqs `1`, scheduled `1`, computed_gpu_head `[508]`, seq_lens_head `[509]`

## Nonzero Prepare Request Windows

- row `11`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `504:505`, computed_cpu `503`, tokens_no_spec `504`, prev_draft `1`, positions `[503, 504]`, tokens_at_pos `[{'position': 503, 'token_id': 440}, {'position': 504, 'token_id': 27044}]`, g0:blocks=2,tail=[1, 2],slots=[33271, 33272]; g1:blocks=2,tail=[3, 4],slots=[98807, 98808]; g2:blocks=2,tail=[5, 6],slots=[164343, 164344]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4535, 4536]
- row `22`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `506:507`, computed_cpu `505`, tokens_no_spec `506`, prev_draft `1`, positions `[505, 506]`, tokens_at_pos `[{'position': 505, 'token_id': 47193}, {'position': 506, 'token_id': 14246}]`, g0:blocks=2,tail=[1, 2],slots=[33273, 33274]; g1:blocks=2,tail=[3, 4],slots=[98809, 98810]; g2:blocks=2,tail=[5, 6],slots=[164345, 164346]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4537, 4538]
- row `33`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `508:509`, computed_cpu `507`, tokens_no_spec `508`, prev_draft `1`, positions `[507, 508]`, tokens_at_pos `[{'position': 507, 'token_id': 8129}, {'position': 508, 'token_id': 13}]`, g0:blocks=2,tail=[1, 2],slots=[33275, 33276]; g1:blocks=2,tail=[3, 4],slots=[98811, 98812]; g2:blocks=2,tail=[5, 6],slots=[164347, 164348]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4539, 4540]
- row `44`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `510:511`, computed_cpu `509`, tokens_no_spec `510`, prev_draft `1`, positions `[509, 510]`, tokens_at_pos `[{'position': 509, 'token_id': 24985}, {'position': 510, 'token_id': 383}]`, g0:blocks=2,tail=[1, 2],slots=[33277, 33278]; g1:blocks=2,tail=[3, 4],slots=[98813, 98814]; g2:blocks=2,tail=[5, 6],slots=[164349, 164350]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4541, 4542]
- row `55`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `512:513`, computed_cpu `511`, tokens_no_spec `512`, prev_draft `1`, positions `[511, 512]`, tokens_at_pos `[{'position': 511, 'token_id': 3074}, {'position': 512, 'token_id': 43318}]`, g0:blocks=2,tail=[1, 2],slots=[33279, 33280]; g1:blocks=2,tail=[3, 4],slots=[98815, 98816]; g2:blocks=2,tail=[5, 6],slots=[164351, 164352]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4543, 4544]
- row `66`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `514:515`, computed_cpu `513`, tokens_no_spec `514`, prev_draft `1`, positions `[513, 514]`, tokens_at_pos `[{'position': 513, 'token_id': 16401}, {'position': 514, 'token_id': 4478}]`, g0:blocks=2,tail=[1, 2],slots=[33281, 33282]; g1:blocks=2,tail=[3, 4],slots=[98817, 98818]; g2:blocks=2,tail=[5, 6],slots=[164353, 164354]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4545, 4546]
- row `77`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `516:517`, computed_cpu `515`, tokens_no_spec `516`, prev_draft `1`, positions `[515, 516]`, tokens_at_pos `[{'position': 515, 'token_id': 11}, {'position': 516, 'token_id': 29541}]`, g0:blocks=2,tail=[1, 2],slots=[33283, 33284]; g1:blocks=2,tail=[3, 4],slots=[98819, 98820]; g2:blocks=2,tail=[5, 6],slots=[164355, 164356]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4547, 4548]
- row `88`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `518:519`, computed_cpu `517`, tokens_no_spec `518`, prev_draft `1`, positions `[517, 518]`, tokens_at_pos `[{'position': 517, 'token_id': 33389}, {'position': 518, 'token_id': 11}]`, g0:blocks=2,tail=[1, 2],slots=[33285, 33286]; g1:blocks=2,tail=[3, 4],slots=[98821, 98822]; g2:blocks=2,tail=[5, 6],slots=[164357, 164358]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4549, 4550]
- row `114`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `523:524`, computed_cpu `522`, tokens_no_spec `523`, prev_draft `1`, positions `[522, 523]`, tokens_at_pos `[{'position': 522, 'token_id': 321}, {'position': 523, 'token_id': 4581}]`, g0:blocks=2,tail=[1, 2],slots=[33290, 33291]; g1:blocks=2,tail=[3, 4],slots=[98826, 98827]; g2:blocks=2,tail=[5, 6],slots=[164362, 164363]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4554, 4555]
- row `119`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `524:525`, computed_cpu `523`, tokens_no_spec `524`, prev_draft `1`, positions `[523, 524]`, tokens_at_pos `[{'position': 523, 'token_id': 874}, {'position': 524, 'token_id': 4131}]`, g0:blocks=2,tail=[1, 2],slots=[33291, 33292]; g1:blocks=2,tail=[3, 4],slots=[98827, 98828]; g2:blocks=2,tail=[5, 6],slots=[164363, 164364]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4555, 4556]
- row `130`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `526:527`, computed_cpu `525`, tokens_no_spec `526`, prev_draft `1`, positions `[525, 526]`, tokens_at_pos `[{'position': 525, 'token_id': 4557}, {'position': 526, 'token_id': 13}]`, g0:blocks=2,tail=[1, 2],slots=[33293, 33294]; g1:blocks=2,tail=[3, 4],slots=[98829, 98830]; g2:blocks=2,tail=[5, 6],slots=[164365, 164366]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4557, 4558]
- row `141`, rank `0`, req `cmpl-a10e1749ff57ba54-0-97d8299c`, idx `0`, spec `1`, write `528:529`, computed_cpu `527`, tokens_no_spec `528`, prev_draft `1`, positions `[527, 528]`, tokens_at_pos `[{'position': 527, 'token_id': 271}, {'position': 528, 'token_id': 760}]`, g0:blocks=2,tail=[1, 2],slots=[33295, 33296]; g1:blocks=2,tail=[3, 4],slots=[98831, 98832]; g2:blocks=2,tail=[5, 6],slots=[164367, 164368]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4559, 4560]
- row `173`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[8, 9],slots=[262632, 262633]; g1:blocks=2,tail=[10, 11],slots=[328168, 328169]; g2:blocks=2,tail=[12, 13],slots=[393704, 393705]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8552, 8553]
- row `184`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, idx `0`, spec `1`, write `491:492`, computed_cpu `490`, tokens_no_spec `491`, prev_draft `1`, positions `[490, 491]`, tokens_at_pos `[{'position': 490, 'token_id': 13}, {'position': 491, 'token_id': 78503}]`, g0:blocks=2,tail=[8, 9],slots=[262634, 262635]; g1:blocks=2,tail=[10, 11],slots=[328170, 328171]; g2:blocks=2,tail=[12, 13],slots=[393706, 393707]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8554, 8555]
- row `195`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, idx `0`, spec `1`, write `493:494`, computed_cpu `492`, tokens_no_spec `493`, prev_draft `1`, positions `[492, 493]`, tokens_at_pos `[{'position': 492, 'token_id': 4581}, {'position': 493, 'token_id': 2468}]`, g0:blocks=2,tail=[8, 9],slots=[262636, 262637]; g1:blocks=2,tail=[10, 11],slots=[328172, 328173]; g2:blocks=2,tail=[12, 13],slots=[393708, 393709]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8556, 8557]
- row `206`, rank `0`, req `cmpl-a88b2797c1a1a5c4-0-be8d2e0d`, idx `0`, spec `1`, write `495:496`, computed_cpu `494`, tokens_no_spec `495`, prev_draft `1`, positions `[494, 495]`, tokens_at_pos `[{'position': 494, 'token_id': 1345}, {'position': 495, 'token_id': 28043}]`, g0:blocks=2,tail=[8, 9],slots=[262638, 262639]; g1:blocks=2,tail=[10, 11],slots=[328174, 328175]; g2:blocks=2,tail=[12, 13],slots=[393710, 393711]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8558, 8559]
