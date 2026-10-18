# Packet141 result (attribution only): cold in-order kernels vs warm repeated micros, 2-card bundle 8 line

Probe `packet141c-probe-B` (lane B, 20:41:54–20:44:57 UTC October 18, fault count 2). It completed: 2 exact requests, all arm states equal, routes equal. Evidence: `stage2/packet141-transfer-gap/evidence/probe-B-repair141c/run/incident-retrospective/rank0/p141-*.jsonl`.

The packet's own `analyze.py` refused the evidence ("touch kernel count": pre-touch rows disagree with the plan's per-site kernel count). It therefore gives no gate verdict. Per review 30 there is no p141d. The coordinator summed raw event durations per class per half from `p141-events.jsonl` (non-warm-up rows; arm a = cold in-order, one half per block; arm b = warm repeated, virtual halves by repeat index; medians over halves). This is a CPU-side reading, **diagnostic only, no speed claim**:

| Class | Cold in-order a (ms/half) | Warm b (ms/half) | a/b |
| --- | ---: | ---: | ---: |
| expsgate | 1.456 | 1.192 | 1.22 |
| gdn.qkv | 1.174 | 1.027 | 1.14 |
| **attention** | **1.137** | **0.774** | **1.47** |
| expsdown | 0.933 | 0.870 | 1.07 |
| route | 0.792 | 0.751 | 1.06 |
| **gdn.z** | **0.707** | **0.542** | **1.30** |
| **router** | **0.536** | **0.289** | **1.86** |
| hc.f.gate / hc.a.gate | 0.528 / 0.524 | 0.477 / 0.475 | 1.11 / 1.10 |
| gdn.recurrence | 0.474 | 0.385 | 1.23 |

Half wall times: arm a 11.76 ms; natural order (no eviction sweep) 11.90 ms; controls 11.76 ms.

Against the preregistered rule (≥ 1.3× on a class carrying ≥ 0.5 ms/half → test that class's layout/order), **attention, router and gdn.z** qualify. Expert gate/up (1.22×) and HC (≈1.1×) do not. The ~20% transfer assumption in packets 135/140 looks too pessimistic for attention and the router, and about right for the rest.

Decision: packet141 closed as attribution. packet142's `attention-order600` variant (smoke exact at 20:40) is first priority for a one-load bracket once p142c's report fix lands. Router and gdn.z order/layout are candidates for a follow-up variant.
