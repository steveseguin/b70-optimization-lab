# Round 19, guess-count rule study (costk, 2026-11-12 21:00)

Question (Codex's review, point 1): would a cost-aware rule for how many draft guesses to check (pick the count that
gives the most expected tokens per millisecond, using the check-cost curve and calibrated confidences) beat the
current cutoff (`OWN_SPEC_TAU=0.5`: check guesses while the running product of confidences stays >= 0.5)?

Data: `tau0.sh` (round18-scripts/strategy) ran tp105 guessing with every guess checked (`OWN_SPEC_TAU=0`) on all five
prompts with the draft vocabulary: answers SAME AS the plain run on all five; 136.5 / 138.9 / 94.9 / 125.0 / 121.5
tok/s (code / analysis / prose / docs / ops); check 20.4-20.7 ms per cycle. `spec/` = the guess logs (per cycle: five
confidences, checked count, kept count, draft ms, check ms, n-gram flag).

Check time per cycle by guesses checked (unprofiled, tg105v + tau0 logs, median): 0: 10.02, 1: 12.70, 2: 14.96,
3: 16.55, 4: 19.04, 5: 20.64 ms; draft 1.78 ms.

`sim.py` (reads dsv41-work/runs/tau0) scores a rule as sum of tokens / sum of (draft + check) over the recorded
cycles. It reads high against measured runs at the same cutoff (code +7 %, others +1-4 %: cycle start points shift
with the rule), so only differences between rules count. Output in `sim-output.txt`.

## In plain words

- **The current cutoff is already near the best rule that uses the draft's confidences.** Mean over five prompts:
  cutoff 0.5 = 148.8 (sim); cost-aware with calibration, scored on held-out prompts = 148.2-148.6; best per-position
  cutoffs fitted on the same data (optimistic) = 149.7 (+0.6 %). Other cutoffs: 0.4 / 0.45 = 147.9, 0.6 = 147.0.
- **Calibration with the vocabulary is fine for the first guess** (cumulative product 0.5-0.6 -> 55 % right) and
  over-confident in the middle for later guesses (guess 2 at 0.3-0.4 -> 20 %), but fixing that buys nothing
  measurable.
- **Re-picking under projected check costs:** 1 ms cheaper 1-2 guess checks (helper ck2's target) or a cheaper
  4-guess check leave 0.5 the best cutoff.
- **The real gap is the draft knowing when it is right:** checking exactly the guesses that will be kept would give
  173.6 (+17 %). Only better confidence signals (or a better draft) can reach into that, not the selection rule.

## Decision

Lever closed: `OWN_SPEC_TAU=0.5` stays; no controller is built. Re-run `sim.py` when the check-cost curve changes a
lot (new check forms) to re-pick the cutoff.
