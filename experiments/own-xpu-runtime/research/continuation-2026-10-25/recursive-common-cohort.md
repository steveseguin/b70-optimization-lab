# Recursive guesses on matching observable positions

The retained twelve-prompt probe was rejoined against its verified output tokens.
Every probe first passed the existing identity, true-prefix and complete mutable
restore checks. Input hashes and per-prompt counts are in
[the result](recursive-common-cohort.json); [the analyzer](analyze_common_proposal_cohort.py)
does not run an engine or train a draft.

| Available lookahead | Positions | First guess wrong | Only first correct | First two correct, third wrong | Entire prefix correct |
| --- | ---: | ---: | ---: | ---: | ---: |
| Two guesses | 5,953 | 1,420 | 1,220 | — | 3,313 |
| Three guesses | 5,941 | 1,417 | 1,216 | 918 | 2,390 |

The last one or two positions of each answer cannot observe the complete chosen
lookahead, so they are excluded consistently within each row. On these common
cohorts, both guesses match in 55.653% of depth-two probes and all three match in
40.229% of depth-three probes. The mean correct recursive prefix is 1.318 or
1.721 guesses respectively.

These probes start from a true prefix at each position. They do not measure a
rolling scheduler's realized acceptance, wasted stage work, throughput or latency.
In particular, a later canonical guess may disagree with an already issued
recursive guess. The issued work retains its identity until the target verifies
it. Deeper pipeline work must measure that behavior and the full cost of rejected
suffixes; these counts alone are not a speed forecast.
