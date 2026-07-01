# Qwen3.6 COW Worker-State Trace Summary

- Rows: `244`
- Requests: `2`
- Spec update rows: `50`
- Nonzero spec updates: `14`
- Prepare-position rows: `50`
- Prepare request windows: `50`
- Nonzero prepare request windows: `14`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `50`
- `before_cached_req_update`: `48`
- `after_cached_req_counter_update`: `48`
- `after_persistent_batch_update`: `48`
- `after_spec_token_update`: `48`

## Nonzero Spec Updates

- row `5`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, spec `1`, write `503:504`, num_tokens_no_spec `503`, prev_draft `0` -> `1`
- row `10`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, spec `1`, write `505:506`, num_tokens_no_spec `505`, prev_draft `1` -> `1`
- row `15`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, spec `1`, write `507:508`, num_tokens_no_spec `507`, prev_draft `1` -> `1`
- row `20`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, spec `1`, write `509:510`, num_tokens_no_spec `509`, prev_draft `1` -> `1`
- row `25`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, spec `1`, write `511:512`, num_tokens_no_spec `511`, prev_draft `1` -> `1`
- row `30`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, spec `1`, write `513:514`, num_tokens_no_spec `513`, prev_draft `1` -> `1`
- row `35`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, spec `1`, write `515:516`, num_tokens_no_spec `515`, prev_draft `1` -> `1`
- row `127`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `132`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`
- row `137`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, spec `1`, write `493:494`, num_tokens_no_spec `493`, prev_draft `1` -> `1`
- row `142`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, spec `1`, write `495:496`, num_tokens_no_spec `495`, prev_draft `1` -> `1`
- row `147`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, spec `1`, write `497:498`, num_tokens_no_spec `497`, prev_draft `1` -> `1`
- row `152`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, spec `1`, write `499:500`, num_tokens_no_spec `499`, prev_draft `1` -> `1`
- row `157`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, spec `1`, write `501:502`, num_tokens_no_spec `501`, prev_draft `1` -> `1`

## Prepare Events

- row `1`, rank `0`, reqs `1`, scheduled `502`, computed_gpu_head `[0]`, seq_lens_head `[502]`
- row `6`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[502]`, seq_lens_head `[504]`
- row `11`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[504]`, seq_lens_head `[506]`
- row `16`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[506]`, seq_lens_head `[508]`
- row `21`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[508]`, seq_lens_head `[510]`
- row `26`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[510]`, seq_lens_head `[512]`
- row `31`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[512]`, seq_lens_head `[514]`
- row `36`, rank `0`, reqs `1`, scheduled `2`, computed_gpu_head `[514]`, seq_lens_head `[516]`

## Nonzero Prepare Request Windows

- row `6`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, idx `0`, spec `1`, write `503:504`, computed_cpu `502`, tokens_no_spec `503`, prev_draft `1`, positions `[502, 503]`, tokens_at_pos `[{'position': 502, 'token_id': 22791}, {'position': 503, 'token_id': 440}]`, g0:blocks=2,tail=[1, 2],slots=[33270, 33271]; g1:blocks=2,tail=[3, 4],slots=[98806, 98807]; g2:blocks=2,tail=[5, 6],slots=[164342, 164343]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4534, 4535]
- row `11`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, idx `0`, spec `1`, write `505:506`, computed_cpu `504`, tokens_no_spec `505`, prev_draft `1`, positions `[504, 505]`, tokens_at_pos `[{'position': 504, 'token_id': 27044}, {'position': 505, 'token_id': 47193}]`, g0:blocks=2,tail=[1, 2],slots=[33272, 33273]; g1:blocks=2,tail=[3, 4],slots=[98808, 98809]; g2:blocks=2,tail=[5, 6],slots=[164344, 164345]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4536, 4537]
- row `16`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, idx `0`, spec `1`, write `507:508`, computed_cpu `506`, tokens_no_spec `507`, prev_draft `1`, positions `[506, 507]`, tokens_at_pos `[{'position': 506, 'token_id': 14246}, {'position': 507, 'token_id': 8129}]`, g0:blocks=2,tail=[1, 2],slots=[33274, 33275]; g1:blocks=2,tail=[3, 4],slots=[98810, 98811]; g2:blocks=2,tail=[5, 6],slots=[164346, 164347]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4538, 4539]
- row `21`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, idx `0`, spec `1`, write `509:510`, computed_cpu `508`, tokens_no_spec `509`, prev_draft `1`, positions `[508, 509]`, tokens_at_pos `[{'position': 508, 'token_id': 13}, {'position': 509, 'token_id': 24985}]`, g0:blocks=2,tail=[1, 2],slots=[33276, 33277]; g1:blocks=2,tail=[3, 4],slots=[98812, 98813]; g2:blocks=2,tail=[5, 6],slots=[164348, 164349]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4540, 4541]
- row `26`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, idx `0`, spec `1`, write `511:512`, computed_cpu `510`, tokens_no_spec `511`, prev_draft `1`, positions `[510, 511]`, tokens_at_pos `[{'position': 510, 'token_id': 383}, {'position': 511, 'token_id': 3074}]`, g0:blocks=2,tail=[1, 2],slots=[33278, 33279]; g1:blocks=2,tail=[3, 4],slots=[98814, 98815]; g2:blocks=2,tail=[5, 6],slots=[164350, 164351]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4542, 4543]
- row `31`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, idx `0`, spec `1`, write `513:514`, computed_cpu `512`, tokens_no_spec `513`, prev_draft `1`, positions `[512, 513]`, tokens_at_pos `[{'position': 512, 'token_id': 43318}, {'position': 513, 'token_id': 16401}]`, g0:blocks=2,tail=[1, 2],slots=[33280, 33281]; g1:blocks=2,tail=[3, 4],slots=[98816, 98817]; g2:blocks=2,tail=[5, 6],slots=[164352, 164353]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4544, 4545]
- row `36`, rank `0`, req `cmpl-a04056259006ad3d-0-ade19c66`, idx `0`, spec `1`, write `515:516`, computed_cpu `514`, tokens_no_spec `515`, prev_draft `1`, positions `[514, 515]`, tokens_at_pos `[{'position': 514, 'token_id': 4478}, {'position': 515, 'token_id': 11}]`, g0:blocks=2,tail=[1, 2],slots=[33282, 33283]; g1:blocks=2,tail=[3, 4],slots=[98818, 98819]; g2:blocks=2,tail=[5, 6],slots=[164354, 164355]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4546, 4547]
- row `128`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[8, 9],slots=[262632, 262633]; g1:blocks=2,tail=[10, 11],slots=[328168, 328169]; g2:blocks=2,tail=[12, 13],slots=[393704, 393705]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8552, 8553]
- row `133`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, idx `0`, spec `1`, write `491:492`, computed_cpu `490`, tokens_no_spec `491`, prev_draft `1`, positions `[490, 491]`, tokens_at_pos `[{'position': 490, 'token_id': 13}, {'position': 491, 'token_id': 78503}]`, g0:blocks=2,tail=[8, 9],slots=[262634, 262635]; g1:blocks=2,tail=[10, 11],slots=[328170, 328171]; g2:blocks=2,tail=[12, 13],slots=[393706, 393707]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8554, 8555]
- row `138`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, idx `0`, spec `1`, write `493:494`, computed_cpu `492`, tokens_no_spec `493`, prev_draft `1`, positions `[492, 493]`, tokens_at_pos `[{'position': 492, 'token_id': 4581}, {'position': 493, 'token_id': 2468}]`, g0:blocks=2,tail=[8, 9],slots=[262636, 262637]; g1:blocks=2,tail=[10, 11],slots=[328172, 328173]; g2:blocks=2,tail=[12, 13],slots=[393708, 393709]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8556, 8557]
- row `143`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, idx `0`, spec `1`, write `495:496`, computed_cpu `494`, tokens_no_spec `495`, prev_draft `1`, positions `[494, 495]`, tokens_at_pos `[{'position': 494, 'token_id': 1345}, {'position': 495, 'token_id': 28043}]`, g0:blocks=2,tail=[8, 9],slots=[262638, 262639]; g1:blocks=2,tail=[10, 11],slots=[328174, 328175]; g2:blocks=2,tail=[12, 13],slots=[393710, 393711]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8558, 8559]
- row `148`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, idx `0`, spec `1`, write `497:498`, computed_cpu `496`, tokens_no_spec `497`, prev_draft `1`, positions `[496, 497]`, tokens_at_pos `[{'position': 496, 'token_id': 7072}, {'position': 497, 'token_id': 3817}]`, g0:blocks=2,tail=[8, 9],slots=[262640, 262641]; g1:blocks=2,tail=[10, 11],slots=[328176, 328177]; g2:blocks=2,tail=[12, 13],slots=[393712, 393713]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8560, 8561]
- row `153`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, idx `0`, spec `1`, write `499:500`, computed_cpu `498`, tokens_no_spec `499`, prev_draft `1`, positions `[498, 499]`, tokens_at_pos `[{'position': 498, 'token_id': 22188}, {'position': 499, 'token_id': 13}]`, g0:blocks=2,tail=[8, 9],slots=[262642, 262643]; g1:blocks=2,tail=[10, 11],slots=[328178, 328179]; g2:blocks=2,tail=[12, 13],slots=[393714, 393715]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8562, 8563]
- row `158`, rank `0`, req `cmpl-88236ae7602f30d0-0-907d8322`, idx `0`, spec `1`, write `501:502`, computed_cpu `500`, tokens_no_spec `501`, prev_draft `1`, positions `[500, 501]`, tokens_at_pos `[{'position': 500, 'token_id': 15153}, {'position': 501, 'token_id': 1543}]`, g0:blocks=2,tail=[8, 9],slots=[262644, 262645]; g1:blocks=2,tail=[10, 11],slots=[328180, 328181]; g2:blocks=2,tail=[12, 13],slots=[393716, 393717]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8564, 8565]
