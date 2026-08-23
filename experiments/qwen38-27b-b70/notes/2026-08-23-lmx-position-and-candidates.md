# LocalMaxxing position: candidates ready, and the margin question laid out

Date: 2026-08-23. Documentation only - NOTHING here submits, amends, or
withdraws anything. Prepared so the leaderboard decisions can be made with
everything in one place.

## Submission candidates (certified this week, not yet sealed)

| Lane | Number | Status | What sealing still needs |
| --- | ---: | --- | --- |
| vLLM XPU nightly, TP1, MTP off, XPU graph | 30.22 / 30.26 conventional | Objective battery PASS; cache-zero; fresh-compile determinism candidate closed negative | Natural-EOS final gate; battery with an actual baseline; exact-cache replay/sealing; mandatory cross-boot disclosure |
| vLLM XPU nightly, TP4, MTP off, XPU graph | 71.293 natural-EOS final; 71.67 / 71.55 diagnostic ceiling | Natural-EOS strict gate PASS; objective battery PASS; cache-zero; cross-boot speed stable | Battery with an actual baseline; exact-cache replay/sealing; mandatory cross-boot and unsupported/experimental multi-GPU XPU Graph disclosures; fastest target-only Qwen3.8 result for this AutoRound/nightly identity, not the lab-wide target-only record |
| llama.cpp Q4_K_M TP1 (promoted) | 27.81/27.82 conventional | 24/24 bit-exact, full battery, submission-ready since 2026-08-21 | Nothing - submit-ready; user previously declined ("the 27 is lame") |

**Mandatory disclosure for the two nightly lanes:** deterministic within a
boot (8/8 stress on TP1-class config), NOT across boots (autotuned kernel
selection; 19-20/25 cross-boot output agreement). Rates are stable across
boots (0.17% pairs); outputs are not byte-pinned. Any submission must say
this. A bounded `PYTHONHASHSEED=0` plus tuner-disabled program preserved
30.2-class speed but still matched only 19/25 full outputs, so that candidate
is closed. Exact-cache replay is the only sealed deterministic path shown.

The TP4 candidate now has a passing natural-EOS, 99-interval final gate at
71.2933. TP1 still needs its natural-EOS final gate. The battery files have
`baseline_comparisons={}` because no
`--baseline-json` was supplied; their objective canaries pass, but the
compatibility field `baseline_match_all=true` is not oracle evidence. Neither
candidate is submission-ready until its remaining gates are rerun correctly.

## The margin question (user decision pending)

Two published rows (MTP5 `101.922`, MTP4 `100.497`) used
`VALIDATION_DETERMINISTIC_GREEDY_MARGIN=1`. The audit evidence
(`results/localmaxxing-submissions.md`, data
`MARGIN_INVALIDATES_PUBLISHED_RECORDS_20260820`):

- margin ON vs OFF changes generated text on 18/25 prompts (control: 25/25
  reproducible), so the flag is output-changing;
- the quality gate could not see it (its baseline was captured margin-on -
  blind by construction) and generates too few tokens to catch the flip rate;
- the margin is 2-4 ULP at real logit magnitudes while INT8 LM-head noise is
  ~3x wider, so it is not a numerics guard; it was an underived opt-in;
- separately, the published `commandSnippet` carries a wrong scratch flag, so
  a third party copying it configures a different run than the one measured.

Two defensible readings:

- **Audit reading (README rows as written):** the records' published claims
  include promotion-grade exactness/self-determinism/quality; the margin
  taints those claims, so the rows are invalid AS PUBLISHED and should be
  withdrawn or re-measured margin-free.
- **User reading (2026-08-23):** the throughputs were genuinely measured;
  the rows stand as speed observations of that exact configuration. Under
  this reading the honest cure is disclosure/correction (config described
  accurately, exactness claims dropped), not withdrawal.

The ledger itself already says "needs a human decision" - only the README
row wording asserts invalidity as fact. Decision options, all reversible
except (c): (a) leave everything as-is; (b) soften the README rows to
"disputed - see ledger" pending re-measurement; (c) re-measure margin-free
(the margin-free anchor already exists: 101.170 all-25, so the re-measured
truth is already on the board); (d) amend/withdraw upstream. No action taken.
