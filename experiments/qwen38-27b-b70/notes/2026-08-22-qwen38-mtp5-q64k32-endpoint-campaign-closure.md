# Qwen3.8 MTP5 Q64xK32 endpoint campaign closure

Date: 2026-08-22

Classification: **design closed as blocked on the lane's prompt-6
nondeterminism, per the preregistered bounded-relaunch rule. The
integration DSO is endpoint-deployable and engaged; its short-KV suite
effect is `+0.53%` and `+0.33%` across the two completed A-B pairs
(report-only). No conjunctive paired verdict was obtainable.**

## Campaign chronicle (all roots preserved)

| Attempt | Outcome |
|---|---|
| endpoint (a1 label) | pre-launch identity refusal: uncommitted vLLM WIP (preserved); no GPU work |
| endpoint2 | a1 PASS `100.928` conv; b1 terminal: r2 DSO undeployable (kernel-farm coverage) |
| endpoint3 | a1 invalid: prompt-6 short family (58 tokens) — stochastic stop #1 |
| endpoint4 | a1 PASS `101.523`; b1 ran full 25, markers 2/2, `102.059` (`+0.53%`), 23/25 parity; stopped by the runner's inherent 25/25 peer-parity gate (design mismatch, fixed in endpoint5) |
| endpoint5 | a1 PASS `101.073`; b1 full PASS `101.405` (`+0.33%`, 22/25 parity, battery green); b2 invalid: prompt-6 short family — stochastic stop #2 |
| endpoint6 | a1 PASS; b1 invalid: prompt-6 short family — stochastic stop #3, budget exhausted |

## What is established

1. **The integration DSO (`979e91c1…`) is production-deployable**: engine
   init clean, both per-rank engagement markers on every candidate arm,
   sealed cache/identity gates green, quality battery passed on the
   candidate route (endpoint5 b1).
2. **Short-KV suite effect is small and consistent**: `+0.53%` and
   `+0.33%` on two independent completed pairs. This matches the KV-mix
   arithmetic: the qualified `~75 us/call` saving is a KV1300 figure; this
   suite's short prompts keep the measured decode window at low KV where
   the per-call saving is a fraction of that. The lever's serving value
   concentrates in long-context workloads.
3. **The blocking pathology is the incumbent lane's own**: prompt 6
   (`selection--sql-debugging`) stochastically emits an early-EOS family
   (58/68-token instances documented; a 168-token variant also appeared)
   at a tonight-observed rate near 30% per arm, refusing the strict
   100-token metric window. This reproduces in stock control arms and is
   independent of the candidate.

## Disposition

- No further relaunches under this design. Any successor campaign must
  preregister a prompt-6-robust metric (for example: median over
  valid-window rows with a minimum-valid-row gate and full reporting of
  refused rows) or a revised suite, as a new identity.
- A **long-KV endpoint suite** is the natural next preregistration if the
  Q64xK32 serving win is to be realized where it is large; the operator
  qualification (r4) and the deployable stage stand ready.
- The two-pair short-KV evidence is report-only and must not be promoted
  or submitted.
