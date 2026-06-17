| label | tok/s | decode ms/tok | JSON | color | quality | speed | promotion | first failure |
| --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| no-gdnfallback-no-topk | 97.90 | 10.22 | fail | fail | missing | fail | no | json canary: {"answer": "42.Plugin whiskey whiskey whiskey2": "widgets"}; color canary: blue whiskey whiskey green, orange, red; quality ... |
| native-gdn-initial1 | 94.00 | 10.64 | fail | fail | missing | fail | no | json canary: {"answer":"12","unit":"widgets"}; color canary: blue, green, orange,; quality suite missing/fail |
| no-gdnfallback | 94.00 | 10.64 | pass | pass | missing | fail | no | quality suite missing/fail |
| native-gdn-initial4 | 93.99 | 10.64 | fail | fail | missing | fail | no | json canary: {"answer":"12","unit":"widgets"}; color canary: blue, green, orange,; quality suite missing/fail |
| no-gdnfallback-prefill-replay | 93.69 | 10.67 | pass | fail | missing | fail | no | color canary: 伪造。 造 造 造 造 造 造 造 造 造 造 造 造造造造造; quality suite missing/fail |
| gdnfallback-max-sampler | 93.56 | 10.69 | fail | fail | missing | fail | no | json canary: {"answer": "42 whiskey whiskey whiskey whiskey2": "widgets"}; color canary: blue whiskey whiskey�ellow，green，red; quality su... |
| native-gdn-topk-prefillbypass-promotion | 92.70 | 10.80 | fail | fail | pass | fail | no | json canary: {"answer":"12","unit":"widgets"}; color canary: blue, green, orange, |
| native-gdn-jsontrace | 92.23 | 10.85 | fail | pass | missing | fail | no | json canary: {"answer":"12","unit":"widgets"}; quality suite missing/fail |
| native-gdn-zero-all-prefill-state | 92.16 | 10.86 | fail | fail | missing | fail | no | json canary: {"answer":"12","unit":"widgets"}; color canary: blue, green, orange,; quality suite missing/fail |
| native-gdn-layer0 | 91.15 | 10.97 | fail | fail | missing | fail | no | json canary: {"answer":"12","unit":"widgets"}; color canary: blue, green, orange,; quality suite missing/fail |
| native-gdn-layer0-3 | 90.35 | 11.07 | fail | fail | missing | fail | no | json canary: {"answer":"12","unit":"widgets"}; color canary: blue, green, red, yellow; quality suite missing/fail |
| gdnfallback-clone-argmax | 90.04 | 11.11 | fail | fail | missing | fail | no | json canary: {"answer": "42 whiskey whiskey.Plugin whiskey2": "widgets"}; color canary: blue whiskey whiskey�ellow，green，red; quality sui... |
| w8a8-safe-default-cache | 86.91 | 11.51 | pass | pass | missing | fail | no | quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-fixed-canaries | 85.26 | 11.74 | fail | pass | missing | fail | no | json canary: {"answer": "12.0", "unit": "widgets"}; quality suite missing/fail |
| native-gdn-syncdecode | 74.34 | 13.45 | fail | fail | missing | fail | no | json canary: {"answer":"12","unit":"widgets"}; color canary: blue, green, orange,; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-sync | 14.41 | 69.42 | fail | fail | missing | fail | no | json canary: {"answer": 42', 'unit': 'widgets'}; color canary: blue,qua, green, red, yellow; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-zero-empty | 14.40 | 69.44 | fail | fail | missing | fail | no | json canary: {"answer": 42', 'unit': 'widgets'}; color canary: blue, green- red- yellow; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0 | 14.20 | 70.42 | fail | pass | missing | fail | no | json canary: {"answer": "42", "unit": "widgets widgets"}; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-graphnone-packed-gate | 13.98 | 71.56 | pass | pass | pass | fail | no |  |
| accepted-c1-decisive-20260614-impl | 13.38 | 74.73 | missing | missing | missing | fail | no | json canary missing/fail; color canary missing/fail; quality suite missing/fail |
| w8a8-safe-default-quality | - | - | missing | missing | missing | fail | no | metrics missing/fail; json canary missing/fail; color canary missing/fail; quality suite missing/fail |
| w8a8-safe-prefill-quality | - | - | missing | missing | missing | fail | no | metrics missing/fail; json canary missing/fail; color canary missing/fail; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-eager-nopacked-canaries | - | - | pass | pass | missing | fail | no | metrics missing/fail; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-eager-packed-canaries | - | - | pass | pass | missing | fail | no | metrics missing/fail; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-fixed-quality | - | - | pass | pass | pass | fail | no | metrics missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-nopacked-canaries | - | - | pass | fail | missing | fail | no | metrics missing/fail; color canary: blue, green, orange, </think> red; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-compare | - | - | pass | pass | missing | fail | no | metrics missing/fail; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-return-direct | - | - | fail | pass | missing | fail | no | metrics missing/fail; json canary: {"{"answer": "42", "unit": "widgets"}"}; quality suite missing/fail |
| w8a8-safe-prefill-recurrent-gmem90-quality | - | - | missing | missing | missing | fail | no | metrics missing/fail; json canary missing/fail; color canary missing/fail; quality suite missing/fail |
