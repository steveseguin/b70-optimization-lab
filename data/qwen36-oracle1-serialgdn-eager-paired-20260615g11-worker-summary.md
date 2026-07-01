# Qwen3.6 COW Worker-State Trace Summary

- Rows: `249`
- Requests: `2`
- Spec update rows: `51`
- Nonzero spec updates: `16`
- Prepare-position rows: `51`
- Prepare request windows: `51`
- Nonzero prepare request windows: `16`

## Stage Counts

- `after_new_req_add_spec_update`: `2`
- `after_prepare_positions`: `51`
- `before_cached_req_update`: `49`
- `after_cached_req_counter_update`: `49`
- `after_persistent_batch_update`: `49`
- `after_spec_token_update`: `49`

## Nonzero Spec Updates

- row `10`, rank `0`, req `cmpl-b778328a79aacaf2-0-bc09d75b`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `0` -> `1`
- row `15`, rank `0`, req `cmpl-b778328a79aacaf2-0-bc09d75b`, spec `1`, write `506:507`, num_tokens_no_spec `506`, prev_draft `1` -> `1`
- row `20`, rank `0`, req `cmpl-b778328a79aacaf2-0-bc09d75b`, spec `1`, write `508:509`, num_tokens_no_spec `508`, prev_draft `1` -> `1`
- row `25`, rank `0`, req `cmpl-b778328a79aacaf2-0-bc09d75b`, spec `1`, write `510:511`, num_tokens_no_spec `510`, prev_draft `1` -> `1`
- row `147`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `489:490`, num_tokens_no_spec `489`, prev_draft `0` -> `1`
- row `152`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `491:492`, num_tokens_no_spec `491`, prev_draft `1` -> `1`
- row `187`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `498:499`, num_tokens_no_spec `498`, prev_draft `0` -> `1`
- row `192`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `500:501`, num_tokens_no_spec `500`, prev_draft `1` -> `1`
- row `197`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `502:503`, num_tokens_no_spec `502`, prev_draft `1` -> `1`
- row `202`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `504:505`, num_tokens_no_spec `504`, prev_draft `1` -> `1`
- row `207`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `506:507`, num_tokens_no_spec `506`, prev_draft `1` -> `1`
- row `212`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `508:509`, num_tokens_no_spec `508`, prev_draft `1` -> `1`
- row `227`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `511:512`, num_tokens_no_spec `511`, prev_draft `0` -> `1`
- row `232`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `513:514`, num_tokens_no_spec `513`, prev_draft `1` -> `1`
- row `237`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `515:516`, num_tokens_no_spec `515`, prev_draft `1` -> `1`
- row `247`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, spec `1`, write `518:519`, num_tokens_no_spec `518`, prev_draft `0` -> `1`

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

- row `11`, rank `0`, req `cmpl-b778328a79aacaf2-0-bc09d75b`, idx `0`, spec `1`, write `504:505`, computed_cpu `503`, tokens_no_spec `504`, prev_draft `1`, positions `[503, 504]`, tokens_at_pos `[{'position': 503, 'token_id': 440}, {'position': 504, 'token_id': 27044}]`, g0:blocks=2,tail=[1, 2],slots=[33271, 33272]; g1:blocks=2,tail=[3, 4],slots=[98807, 98808]; g2:blocks=2,tail=[5, 6],slots=[164343, 164344]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4535, 4536]
- row `16`, rank `0`, req `cmpl-b778328a79aacaf2-0-bc09d75b`, idx `0`, spec `1`, write `506:507`, computed_cpu `505`, tokens_no_spec `506`, prev_draft `1`, positions `[505, 506]`, tokens_at_pos `[{'position': 505, 'token_id': 47193}, {'position': 506, 'token_id': 14246}]`, g0:blocks=2,tail=[1, 2],slots=[33273, 33274]; g1:blocks=2,tail=[3, 4],slots=[98809, 98810]; g2:blocks=2,tail=[5, 6],slots=[164345, 164346]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4537, 4538]
- row `21`, rank `0`, req `cmpl-b778328a79aacaf2-0-bc09d75b`, idx `0`, spec `1`, write `508:509`, computed_cpu `507`, tokens_no_spec `508`, prev_draft `1`, positions `[507, 508]`, tokens_at_pos `[{'position': 507, 'token_id': 8129}, {'position': 508, 'token_id': 13}]`, g0:blocks=2,tail=[1, 2],slots=[33275, 33276]; g1:blocks=2,tail=[3, 4],slots=[98811, 98812]; g2:blocks=2,tail=[5, 6],slots=[164347, 164348]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4539, 4540]
- row `26`, rank `0`, req `cmpl-b778328a79aacaf2-0-bc09d75b`, idx `0`, spec `1`, write `510:511`, computed_cpu `509`, tokens_no_spec `510`, prev_draft `1`, positions `[509, 510]`, tokens_at_pos `[{'position': 509, 'token_id': 271}, {'position': 510, 'token_id': 760}]`, g0:blocks=2,tail=[1, 2],slots=[33277, 33278]; g1:blocks=2,tail=[3, 4],slots=[98813, 98814]; g2:blocks=2,tail=[5, 6],slots=[164349, 164350]; g3:blocks=9,tail=[64, 65, 66, 67, 68, 69, 70, 71],slots=[4541, 4542]
- row `148`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `489:490`, computed_cpu `488`, tokens_no_spec `489`, prev_draft `1`, positions `[488, 489]`, tokens_at_pos `[{'position': 488, 'token_id': 3817}, {'position': 489, 'token_id': 17856}]`, g0:blocks=2,tail=[8, 9],slots=[262632, 262633]; g1:blocks=2,tail=[10, 11],slots=[328168, 328169]; g2:blocks=2,tail=[12, 13],slots=[393704, 393705]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8552, 8553]
- row `153`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `491:492`, computed_cpu `490`, tokens_no_spec `491`, prev_draft `1`, positions `[490, 491]`, tokens_at_pos `[{'position': 490, 'token_id': 13}, {'position': 491, 'token_id': 78503}]`, g0:blocks=2,tail=[8, 9],slots=[262634, 262635]; g1:blocks=2,tail=[10, 11],slots=[328170, 328171]; g2:blocks=2,tail=[12, 13],slots=[393706, 393707]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8554, 8555]
- row `188`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `498:499`, computed_cpu `497`, tokens_no_spec `498`, prev_draft `1`, positions `[497, 498]`, tokens_at_pos `[{'position': 497, 'token_id': 1543}, {'position': 498, 'token_id': 6126}]`, g0:blocks=2,tail=[8, 9],slots=[262641, 262642]; g1:blocks=2,tail=[10, 11],slots=[328177, 328178]; g2:blocks=2,tail=[12, 13],slots=[393713, 393714]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8561, 8562]
- row `193`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `500:501`, computed_cpu `499`, tokens_no_spec `500`, prev_draft `1`, positions `[499, 500]`, tokens_at_pos `[{'position': 499, 'token_id': 16401}, {'position': 500, 'token_id': 85683}]`, g0:blocks=2,tail=[8, 9],slots=[262643, 262644]; g1:blocks=2,tail=[10, 11],slots=[328179, 328180]; g2:blocks=2,tail=[12, 13],slots=[393715, 393716]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8563, 8564]
- row `198`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `502:503`, computed_cpu `501`, tokens_no_spec `502`, prev_draft `1`, positions `[501, 502]`, tokens_at_pos `[{'position': 501, 'token_id': 15162}, {'position': 502, 'token_id': 5832}]`, g0:blocks=2,tail=[8, 9],slots=[262645, 262646]; g1:blocks=2,tail=[10, 11],slots=[328181, 328182]; g2:blocks=2,tail=[12, 13],slots=[393717, 393718]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8565, 8566]
- row `203`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `504:505`, computed_cpu `503`, tokens_no_spec `504`, prev_draft `1`, positions `[503, 504]`, tokens_at_pos `[{'position': 503, 'token_id': 4618}, {'position': 504, 'token_id': 3817}]`, g0:blocks=2,tail=[8, 9],slots=[262647, 262648]; g1:blocks=2,tail=[10, 11],slots=[328183, 328184]; g2:blocks=2,tail=[12, 13],slots=[393719, 393720]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8567, 8568]
- row `208`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `506:507`, computed_cpu `505`, tokens_no_spec `506`, prev_draft `1`, positions `[505, 506]`, tokens_at_pos `[{'position': 505, 'token_id': 17856}, {'position': 506, 'token_id': 13}]`, g0:blocks=2,tail=[8, 9],slots=[262649, 262650]; g1:blocks=2,tail=[10, 11],slots=[328185, 328186]; g2:blocks=2,tail=[12, 13],slots=[393721, 393722]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8569, 8570]
- row `213`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `508:509`, computed_cpu `507`, tokens_no_spec `508`, prev_draft `1`, positions `[507, 508]`, tokens_at_pos `[{'position': 507, 'token_id': 78503}, {'position': 508, 'token_id': 4581}]`, g0:blocks=2,tail=[8, 9],slots=[262651, 262652]; g1:blocks=2,tail=[10, 11],slots=[328187, 328188]; g2:blocks=2,tail=[12, 13],slots=[393723, 393724]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8571, 8572]
- row `228`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `511:512`, computed_cpu `510`, tokens_no_spec `511`, prev_draft `1`, positions `[510, 511]`, tokens_at_pos `[{'position': 510, 'token_id': 7072}, {'position': 511, 'token_id': 3817}]`, g0:blocks=2,tail=[8, 9],slots=[262654, 262655]; g1:blocks=2,tail=[10, 11],slots=[328190, 328191]; g2:blocks=2,tail=[12, 13],slots=[393726, 393727]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8574, 8575]
- row `233`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `513:514`, computed_cpu `512`, tokens_no_spec `513`, prev_draft `1`, positions `[512, 513]`, tokens_at_pos `[{'position': 512, 'token_id': 22188}, {'position': 513, 'token_id': 13}]`, g0:blocks=2,tail=[8, 9],slots=[262656, 262657]; g1:blocks=2,tail=[10, 11],slots=[328192, 328193]; g2:blocks=2,tail=[12, 13],slots=[393728, 393729]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8576, 8577]
- row `238`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `515:516`, computed_cpu `514`, tokens_no_spec `515`, prev_draft `1`, positions `[514, 515]`, tokens_at_pos `[{'position': 514, 'token_id': 15153}, {'position': 515, 'token_id': 1543}]`, g0:blocks=2,tail=[8, 9],slots=[262658, 262659]; g1:blocks=2,tail=[10, 11],slots=[328194, 328195]; g2:blocks=2,tail=[12, 13],slots=[393730, 393731]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8578, 8579]
- row `248`, rank `0`, req `cmpl-ab7be22d838d79fd-0-879a7125`, idx `0`, spec `1`, write `518:519`, computed_cpu `517`, tokens_no_spec `518`, prev_draft `1`, positions `[517, 518]`, tokens_at_pos `[{'position': 517, 'token_id': 85683}, {'position': 518, 'token_id': 15162}]`, g0:blocks=2,tail=[8, 9],slots=[262661, 262662]; g1:blocks=2,tail=[10, 11],slots=[328197, 328198]; g2:blocks=2,tail=[12, 13],slots=[393733, 393734]; g3:blocks=9,tail=[127, 128, 129, 130, 131, 132, 133, 134],slots=[8581, 8582]
