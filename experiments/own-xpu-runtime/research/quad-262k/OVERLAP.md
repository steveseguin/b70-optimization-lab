# Four-stage overlap and live-MTP result (2026-10-27)

The native 262K four-stage foundation remains valid, but the measured decode schedulers are not promoted: none beats the live two-card B24 service at **66.19 tok/s**.

## Exactness gates

Using the same three-token input and 32 output tokens on cards 23/27/43/47:

- Scripted verified-wavefront overlap produced identical outputs and matched serial target-only execution across **2,065 committed source keys**.
- Six forced wrong guesses produced six native aborts and six byte-verified restores on every applicable stage, with no pending tickets; the final committed state again matched all 2,065 sources.
- Real depth-one MTP produced identical outputs, 33 canonical true-pair records and ten naturally rejected proposals. All ten aborts were byte-verified. Final target state matched all 2,065 sources, and independent draft state matched a no-proposal live run across **73 draft sources**.

## Speed observations

All rates below are controller-observed, uncertified diagnostics. Sustained decode uses `(output_count - 1) / (last_commit - first_commit)`, not a median of per-token intervals.

| Configuration | Observation | Verdict |
|---|---:|---|
| Serial four-stage target-only, 4K | 25.29 tok/s median interval | Baseline |
| Scripted all-hit overlap, 4K | 72.17 tok/s sustained | Scheduling ceiling only; not live drafting |
| Real depth-one MTP, 4K | 14.10 tok/s sustained | Draft/rollback stalls dominate |
| Balanced rolling depth two, warm second request | 49.55 tok/s sustained | Below two-card B24 |
| Balanced rolling depth three, warm second request | 51.26 tok/s sustained | Best real PP4 result; still below B24 |

The balanced rolling runs used boundaries `[0,8,21,34,48]`, actual MTP proposals and cold RESET before each request. Both depth-two and depth-three requests produced the expected 32 tokens. No full-state or service-speed claim is made for those measured-policy runs.

Decision: keep the two-card B24 service and continue exact rank-local kernel work. The experimental PP4 HTTP backend was removed rather than retained as an unadopted second service stack.
