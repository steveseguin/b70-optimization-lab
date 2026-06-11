# Qwen3.6 Logprob Fingerprint Compare

- Left: `data/qwen36-quark-int8-tp4-accepted-noasync-logprobs-p512o128-20260611c.json`
- Right: `data/qwen36-quark-int8-tp4-oracle1-logprobs-p512o128-20260611c.json`
- Cases: `2`
- All selected tokens match: `False`
- All top-k signatures match: `False`

## natural_latency_plan

- Selected tokens match: `False`
- First token diff index: `14`
- Left token: `29541`
- Right token: `4779`
- Logprobs available: `True`
- First selected-token logprob row diff: `14`
- First top-k signature diff: `0`
- First same-rank logprob delta > epsilon: `0`

Selected-token diff top-k:

- Left selected: `29541` ` reliability`
- Right selected: `4779` ` memory`
- Left top: `[{'text': ' reliability', 'token_id': 29541, 'token_ids': [29541], 'logprob': -0.01855398900806904}, {'text': '\n\n', 'token_id': 271, 'token_ids': [271], 'logprob': -5.268554210662842}, {'text': ' reliable', 'token_id': 14294, 'token_ids': [14294], 'logprob': -6.206054210662842}, {'text': ' rel', 'token_id': 1303, 'token_ids': [1303], 'logprob': -6.456054210662842}, {'text': ' no', 'token_id': 874, 'token_ids': [874], 'logprob': -6.831054210662842}]`
- Right top: `[{'text': ' memory', 'token_id': 4779, 'token_ids': [4779], 'logprob': -0.27005910873413086}, {'text': ' kernel', 'token_id': 9705, 'token_ids': [9705], 'logprob': -2.270059108734131}, {'text': ' per', 'token_id': 791, 'token_ids': [791], 'logprob': -3.707559108734131}, {'text': ' graph', 'token_id': 4618, 'token_ids': [4618], 'logprob': -3.832559108734131}, {'text': ' low', 'token_id': 3238, 'token_ids': [3238], 'logprob': -5.082559108734131}]`

## repetitive_kernel_notes

- Selected tokens match: `False`
- First token diff index: `14`
- Left token: `4752`
- Right token: `6126`
- Logprobs available: `True`
- First selected-token logprob row diff: `14`
- First top-k signature diff: `2`
- First same-rank logprob delta > epsilon: `0`

Selected-token diff top-k:

- Left selected: `4752` ` unique`
- Right selected: `6126` `PU`
- Left top: `[{'text': ' unique', 'token_id': 4752, 'token_ids': [4752], 'logprob': -0.525489330291748}, {'text': 'PU', 'token_id': 6126, 'token_ids': [6126], 'logprob': -2.087989330291748}, {'text': 'unique', 'token_id': 9301, 'token_ids': [9301], 'logprob': -2.462989330291748}, {'text': 'U', 'token_id': 52, 'token_ids': [52], 'logprob': -3.025489330291748}, {'text': ' Unique', 'token_id': 27714, 'token_ids': [27714], 'logprob': -3.087989330291748}]`
- Right top: `[{'text': 'PU', 'token_id': 6126, 'token_ids': [6126], 'logprob': -0.011984958313405514}, {'text': 'UP', 'token_id': 3024, 'token_ids': [3024], 'logprob': -6.261984825134277}, {'text': 'U', 'token_id': 52, 'token_ids': [52], 'logprob': -6.324484825134277}, {'text': 'pu', 'token_id': 5409, 'token_ids': [5409], 'logprob': -6.324484825134277}, {'text': 'WP', 'token_id': 24856, 'token_ids': [24856], 'logprob': -6.699484825134277}]`
