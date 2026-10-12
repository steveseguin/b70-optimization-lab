# Schedule model for the two-card pipeline (arithmetic, 2026-10-12)

[simulate.py](simulate.py) replays the measured hit/miss sequences of the official draft
head against the quantized target (packet 31, four prompts, 64 generated tokens each,
8-bit draft) through a small event model of the two rank processes. It is a planning
aid, not a measurement. Output of the run on 2026-10-12: [model.md](model.md),
[model.json](model.json).

Calibration: for packet 36 as measured (halves 22.8 / 23.1 ms, draft 4.2 ms) the model
gives 32.8 tok/s on the development prompt; the two device runs measured 30.37 and
31.02. The model is about 6% optimistic: it has no fixture-capture steps (the first
eight generated tokens retain layer fixtures and are slower) and it prices every wrong
guess at about 47 ms, while the device runs average 55 ms (some misses cost about 60 ms).

What it says about the next steps, as medians over the four prompts (tok/s, model):

| Step | Model |
| --- | ---: |
| packet 36 as measured | 31.5 |
| packet 38 as expected: packet 37's halves (20.7 ms each), draft 3.7 ms, native controller | 35.3 |
| draft moved to the first card (second copy of the output head), layers rebalanced so that draft + first half = second half | 36.9 |
| the same with a 2.5 ms draft | 37.6 |
| the same with 38 ms of total kernel time per token (epilogues, QSA attention) | 40.8 |

By prompt the spread is about 12% (code-review, 43 of 64 guesses right, is the slowest;
incident-retrospective, 54 of 64, the fastest), so a twelve-prompt median will sit below
the development prompt's figure.
