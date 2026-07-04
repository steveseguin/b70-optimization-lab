# Qwen27 Spec Verify Trace Summary

- verify trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk-eaglechat96-20260704T144949Z/verify-trace.jsonl`
- result JSON: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk-eaglechat96-20260704T144949Z-20260704T144949Z.json`
- classification: `diagnostic_only`; not a headline throughput claim
- trace rows: `4798`
- skipped zero-draft warmup rows: `2`
- verifier steps: `4796`
- draft tokens: `14388`
- prefix-accepted tokens: `7650`
- prefix acceptance fraction: `0.5316930775646372`
- mean target-verified tokens per step: `2.5950792326939114`
- mean output tokens per verifier step: `2.5950792326939114`
- full-accept rate: `0.3240200166805671`
- accepted histogram: `{0: 1141, 1: 1214, 2: 887, 3: 1554}`
- per-position target-top1 match: `{'0': 0.76209341117598, '1': 0.6349040867389492, '2': 0.5711009174311926}`

## Paired Strict Result

- median tok/s 1-100 after TTFT: `52.3216176808597`
- p10 tok/s 1-100 after TTFT: `48.53247212342111`
- mean tok/s 1-100 after TTFT: `53.0866420650544`
- median TTFT ms: `743.8194130081683`
- final gate: `{'cached_tokens': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'cached_tokens_all_zero': True, 'chunk_count_matches_completion_tokens_all': False, 'chunk_count_matches_completion_tokens_note': 'Informational only: llama.cpp usage may count an EOS/final token that is not emitted as a text delta. Promotion requires enough streamed text deltas to measure the first metric window.', 'chunk_counts': [42, 43, 52, 48, 49, 52, 52, 50, 49, 49, 55, 48, 48, 54, 52, 51, 48, 49, 50, 56, 54, 48, 47, 50, 48, 46, 58, 46, 43, 47, 48, 57, 47, 54, 49, 51, 45, 50, 50, 50, 52, 52, 48, 50, 49, 50, 53, 52, 49, 50, 52, 54, 52, 49, 45, 50, 51, 49, 47, 51, 55, 49, 52, 46, 52, 50, 57, 50, 45, 52, 52, 53, 53, 46, 50, 51, 44, 53, 50, 47, 52, 46, 54, 45, 49, 58, 52, 52, 53, 53, 54, 49, 48, 56, 56, 50], 'completion_tokens_at_least_metric_window': True, 'metric_chunk_events_at_least_window': False, 'metric_name': 'median_tok_s_1_100_after_ttft', 'metric_token_id_events_at_least_window': True, 'metric_tokens': 100, 'passed': True, 'prompts_unique': True, 'required_policy': 'fixed realistic prompt suite; each prompt once; cached_tokens=0 every row; no repeated/warmed prompt averaging; metric is median tokens 1-100 after TTFT', 'return_token_ids_requested': True, 'stream_token_id_counts': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128], 'token_timing_source': 'openai_stream_token_ids_chunk_timestamp'}`

## Per-Prompt Trace Attribution

| prompt | steps | accepted/draft | mean target tokens/step | full accept | tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| incident-response-runbook | 51 | 104/153 | 3.0392156862745097 | 0.49019607843137253 | 65.31703061488318 |
| incident-response-memo | 43 | 77/129 | 2.7906976744186047 | 0.37209302325581395 | 60.12777975668588 |
| incident-response-review | 51 | 93/153 | 2.8235294117647056 | 0.39215686274509803 | 51.03684564943743 |
| incident-response-debug-plan | 48 | 79/144 | 2.645833333333333 | 0.3541666666666667 | 56.76837356666812 |
| incident-response-json-plan | 48 | 83/144 | 2.729166666666667 | 0.3958333333333333 | 51.08354972567077 |
| incident-response-checklist | 52 | 75/156 | 2.4423076923076925 | 0.3269230769230769 | 55.054532153008175 |
| incident-response-teaching-note | 52 | 79/156 | 2.519230769230769 | 0.3076923076923077 | 53.72727659712173 |
| incident-response-test-plan | 49 | 81/147 | 2.6530612244897958 | 0.32653061224489793 | 53.73405676720815 |
| database-operations-runbook | 48 | 78/144 | 2.625 | 0.3958333333333333 | 56.81144339668385 |
| database-operations-memo | 50 | 76/150 | 2.52 | 0.3 | 52.425838324112995 |
| database-operations-review | 54 | 77/162 | 2.4259259259259256 | 0.2962962962962963 | 49.83353980589672 |
| database-operations-debug-plan | 48 | 82/144 | 2.708333333333333 | 0.3125 | 53.75566065074861 |
| database-operations-json-plan | 48 | 83/144 | 2.729166666666667 | 0.4583333333333333 | 56.66282208624207 |
| database-operations-checklist | 53 | 71/159 | 2.339622641509434 | 0.2830188679245283 | 47.50853843338505 |
| database-operations-teaching-note | 52 | 81/156 | 2.5576923076923075 | 0.3269230769230769 | 52.28832593156312 |
| database-operations-test-plan | 50 | 81/150 | 2.62 | 0.36 | 52.28502458806853 |
| security-review-runbook | 48 | 86/144 | 2.791666666666667 | 0.375 | 53.67902174001986 |
| security-review-memo | 48 | 74/144 | 2.541666666666667 | 0.2916666666666667 | 56.582684302858944 |
| security-review-review | 50 | 90/150 | 2.8 | 0.36 | 52.261462064809855 |
| security-review-debug-plan | 55 | 65/165 | 2.1818181818181817 | 0.2 | 47.290232016772684 |
| security-review-json-plan | 53 | 83/159 | 2.566037735849057 | 0.2830188679245283 | 49.67493364155556 |
| security-review-checklist | 48 | 77/144 | 2.604166666666667 | 0.2916666666666667 | 59.98554569463639 |
| security-review-teaching-note | 46 | 78/138 | 2.6956521739130435 | 0.34782608695652173 | 56.78852307368608 |
| security-review-test-plan | 50 | 84/150 | 2.6799999999999997 | 0.3 | 53.60139919252525 |
| performance-debug-runbook | 48 | 84/144 | 2.75 | 0.3541666666666667 | 56.59825226705581 |
| performance-debug-memo | 45 | 76/135 | 2.688888888888889 | 0.35555555555555557 | 54.64404467722359 |
| performance-debug-review | 58 | 77/174 | 2.3275862068965516 | 0.27586206896551724 | 44.21899472898455 |
| performance-debug-debug-plan | 46 | 86/138 | 2.8695652173913047 | 0.41304347826086957 | 54.84287137665251 |
| performance-debug-json-plan | 43 | 88/129 | 3.046511627906977 | 0.5116279069767442 | 61.47942048825665 |
| performance-debug-checklist | 47 | 83/141 | 2.7659574468085104 | 0.3191489361702128 | 58.18879152747142 |
| performance-debug-teaching-note | 48 | 82/144 | 2.708333333333333 | 0.3958333333333333 | 53.742150758971604 |
| performance-debug-test-plan | 57 | 78/171 | 2.3684210526315788 | 0.19298245614035087 | 46.305643818237755 |
| api-design-runbook | 47 | 83/141 | 2.7659574468085104 | 0.3617021276595745 | 56.29823714746911 |
| api-design-memo | 53 | 77/159 | 2.452830188679245 | 0.24528301886792453 | 48.53759408708216 |
| api-design-review | 48 | 77/144 | 2.604166666666667 | 0.2916666666666667 | 55.172426458207454 |
| api-design-debug-plan | 51 | 82/153 | 2.607843137254902 | 0.35294117647058826 | 52.06009029520632 |
| api-design-json-plan | 45 | 82/135 | 2.822222222222222 | 0.4444444444444444 | 60.059652884482254 |
| api-design-checklist | 49 | 84/147 | 2.7142857142857144 | 0.3673469387755102 | 52.08840327018871 |
| api-design-teaching-note | 50 | 77/150 | 2.54 | 0.32 | 52.256839943931205 |
| api-design-test-plan | 50 | 80/150 | 2.6 | 0.34 | 52.22502513033235 |
| capacity-planning-runbook | 52 | 73/156 | 2.4038461538461537 | 0.2692307692307692 | 50.986445186541815 |
| capacity-planning-memo | 51 | 75/153 | 2.4705882352941178 | 0.3333333333333333 | 53.695016349497486 |
| capacity-planning-review | 49 | 82/147 | 2.673469387755102 | 0.32653061224489793 | 53.67058727972913 |
| capacity-planning-debug-plan | 49 | 84/147 | 2.7142857142857144 | 0.3673469387755102 | 55.122445398917066 |
| capacity-planning-json-plan | 48 | 74/144 | 2.541666666666667 | 0.3958333333333333 | 55.17395741231826 |
| capacity-planning-checklist | 49 | 86/147 | 2.7551020408163263 | 0.46938775510204084 | 54.9032355446596 |
| capacity-planning-teaching-note | 53 | 74/159 | 2.3962264150943398 | 0.2641509433962264 | 48.626296213465835 |
| capacity-planning-test-plan | 52 | 87/156 | 2.6730769230769234 | 0.4230769230769231 | 47.36467136378407 |
| code-review-runbook | 48 | 71/144 | 2.479166666666667 | 0.25 | 52.25240939461429 |
| code-review-memo | 49 | 83/147 | 2.6938775510204085 | 0.32653061224489793 | 52.279573999567624 |
| code-review-review | 52 | 77/156 | 2.480769230769231 | 0.25 | 52.18271270322161 |
| code-review-debug-plan | 53 | 80/159 | 2.509433962264151 | 0.3018867924528302 | 51.016111953359484 |
| code-review-json-plan | 51 | 77/153 | 2.5098039215686274 | 0.27450980392156865 | 53.58845065753531 |
| code-review-checklist | 49 | 86/147 | 2.7551020408163263 | 0.3469387755102041 | 55.200522234487 |
| code-review-teaching-note | 45 | 81/135 | 2.8 | 0.4444444444444444 | 55.23194216097222 |
| code-review-test-plan | 49 | 85/147 | 2.7346938775510203 | 0.2857142857142857 | 53.48956007830667 |
| quality-gates-runbook | 50 | 76/150 | 2.52 | 0.3 | 50.92239969173813 |
| quality-gates-memo | 49 | 77/147 | 2.571428571428571 | 0.3673469387755102 | 53.67640891696086 |
| quality-gates-review | 46 | 84/138 | 2.8260869565217392 | 0.41304347826086957 | 58.30953622940414 |
| quality-gates-debug-plan | 50 | 80/150 | 2.6 | 0.32 | 52.182355443224935 |
| quality-gates-json-plan | 55 | 74/165 | 2.3454545454545457 | 0.2909090909090909 | 48.39947383328969 |
| quality-gates-checklist | 49 | 81/147 | 2.6530612244897958 | 0.2653061224489796 | 52.304402190262195 |
| quality-gates-teaching-note | 52 | 81/156 | 2.5576923076923075 | 0.3076923076923077 | 49.837744150156304 |
| quality-gates-test-plan | 46 | 76/138 | 2.6521739130434785 | 0.34782608695652173 | 56.48196827936541 |
| release-planning-runbook | 52 | 82/156 | 2.5769230769230766 | 0.28846153846153844 | 52.236482399149075 |
| release-planning-memo | 50 | 74/150 | 2.48 | 0.32 | 52.06413227380483 |
| release-planning-review | 56 | 72/168 | 2.2857142857142856 | 0.125 | 47.49138904870741 |
| release-planning-debug-plan | 50 | 81/150 | 2.62 | 0.3 | 53.63673814319348 |
| release-planning-json-plan | 45 | 85/135 | 2.888888888888889 | 0.4 | 56.734883436344646 |
| release-planning-checklist | 52 | 79/156 | 2.519230769230769 | 0.28846153846153844 | 49.74418156817062 |
| release-planning-teaching-note | 52 | 75/156 | 2.4423076923076925 | 0.2692307692307692 | 52.41930072942971 |
| release-planning-test-plan | 53 | 85/159 | 2.6037735849056602 | 0.3584905660377358 | 50.825654729218186 |
| long-context-runbook | 52 | 77/156 | 2.480769230769231 | 0.23076923076923078 | 52.30112611344881 |
| long-context-memo | 46 | 79/138 | 2.717391304347826 | 0.43478260869565216 | 58.31597808210662 |
| long-context-review | 50 | 78/150 | 2.56 | 0.3 | 53.575395427533856 |
| long-context-debug-plan | 50 | 82/150 | 2.6399999999999997 | 0.3 | 52.20584811947227 |
| long-context-json-plan | 44 | 83/132 | 2.8863636363636367 | 0.4318181818181818 | 58.319798464458266 |
| long-context-checklist | 53 | 82/159 | 2.547169811320755 | 0.33962264150943394 | 48.527350159760054 |
| long-context-teaching-note | 50 | 74/150 | 2.48 | 0.32 | 50.81029811704261 |
| long-context-test-plan | 47 | 86/141 | 2.829787234042553 | 0.425531914893617 | 55.19386342217678 |
| support-escalation-runbook | 51 | 81/153 | 2.5882352941176467 | 0.29411764705882354 | 51.000280408801444 |
| support-escalation-memo | 46 | 80/138 | 2.7391304347826084 | 0.3695652173913043 | 56.50822434932546 |
| support-escalation-review | 54 | 78/162 | 2.4444444444444446 | 0.25925925925925924 | 49.67630534745762 |
| support-escalation-debug-plan | 45 | 85/135 | 2.888888888888889 | 0.37777777777777777 | 59.814846458252035 |
| support-escalation-json-plan | 49 | 74/147 | 2.510204081632653 | 0.2857142857142857 | 52.30718695243374 |
| support-escalation-checklist | 58 | 82/174 | 2.413793103448276 | 0.20689655172413793 | 46.4139133832026 |
| support-escalation-teaching-note | 52 | 73/156 | 2.4038461538461537 | 0.23076923076923078 | 50.921037653843975 |
| support-escalation-test-plan | 52 | 80/156 | 2.5384615384615383 | 0.2692307692307692 | 52.33604840928567 |
| architecture-tradeoff-runbook | 53 | 75/159 | 2.4150943396226414 | 0.2641509433962264 | 48.548659546309 |
| architecture-tradeoff-memo | 53 | 74/159 | 2.3962264150943398 | 0.2641509433962264 | 52.17528874917836 |
| architecture-tradeoff-review | 54 | 85/162 | 2.5740740740740744 | 0.3333333333333333 | 50.90653049141847 |
| architecture-tradeoff-debug-plan | 48 | 75/144 | 2.5625 | 0.25 | 53.69373928361768 |
| architecture-tradeoff-json-plan | 48 | 79/144 | 2.645833333333333 | 0.375 | 58.23539521846068 |
| architecture-tradeoff-checklist | 56 | 73/168 | 2.303571428571429 | 0.25 | 46.35458583484334 |
| architecture-tradeoff-teaching-note | 55 | 80/165 | 2.4545454545454546 | 0.2909090909090909 | 49.58376105925465 |
| architecture-tradeoff-test-plan | 44 | 65/132 | 2.4772727272727275 | 0.29545454545454547 | 49.53830956613855 |

## First Reject Examples

```json
[
  {
    "line_no": 3,
    "stage": "dense",
    "position": 0,
    "draft_token_id": 6250,
    "target_argmax_token_id": 86223,
    "output_token_ids": [
      86223
    ]
  },
  {
    "line_no": 11,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 19,
    "target_argmax_token_id": 17,
    "output_token_ids": [
      12,
      17
    ]
  },
  {
    "line_no": 12,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 198,
    "target_argmax_token_id": 12,
    "output_token_ids": [
      19,
      12
    ]
  },
  {
    "line_no": 18,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 23157,
    "target_argmax_token_id": 23435,
    "output_token_ids": [
      846,
      23435
    ]
  },
  {
    "line_no": 19,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 318,
    "target_argmax_token_id": 198,
    "output_token_ids": [
      23157,
      63,
      198
    ]
  },
  {
    "line_no": 20,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 2442,
    "target_argmax_token_id": 8179,
    "output_token_ids": [
      332,
      8179
    ]
  },
  {
    "line_no": 21,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 18887,
    "target_argmax_token_id": 4449,
    "output_token_ids": [
      42874,
      64700,
      4449
    ]
  },
  {
    "line_no": 24,
    "stage": "dense",
    "position": 0,
    "draft_token_id": 76531,
    "target_argmax_token_id": 18985,
    "output_token_ids": [
      18985
    ]
  }
]
```

## Interpretation

- The trace is emitted inside the verifier sampler, so `draft_token_ids` are real worker-side proposals rather than scheduler placeholders.
- Use this to decide whether drafter calibration can improve accepted tokens per verifier step.
- Any speed claim still requires the strict cold realistic suite with `cached_tokens=0`.
