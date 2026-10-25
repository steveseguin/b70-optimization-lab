# Persistent PP4 twelve-prompt audit: PASSED

All 5,965 output IDs match the frozen normal-service suite.
Every prompt was executed anew after a native cold reset in the same four workers;
all reset receipts, preserved allocation layouts, global wire sequences, native
commands and canonical draft input pairs passed independent checks.

Observed full-response decode median: **42.3119 tok/s**
versus **47.9706 tok/s** (0.8820×).
Each rate is (output count − 1)/(last timestamp − first timestamp); the even-sized
suite uses the mean of its two middle rates. These are uncertified observations:
candidate timestamps follow controller COMMIT replies, while the baseline uses
native completion aggregates. No first-99 interval timestamps are inferred.

All four workers exited cleanly. The final target dump and quiescence are
authenticated; this suite did not dump and compare full state for every prompt.
Earlier two-request reset qualification supplies that narrower state proof.
Six CPU-reference disagreements remain unresolved. No draft training occurred.

[Structured audit and source hashes](summary.json), [terminal result](result.json),
[suite records](suite-result.json), [final state manifest](final-state-set.json).
Original raw final state remains external. Compact native/controller traces are retained.

Full native/controller logs and all six final target/draft bundles are retained in
the independently verified durable archive; original files remain untouched. See
[durable archive receipt](../persistent-suite-b-durable-archive.json) and
[streamed raw-member verification](../persistent-suite-b-archive-verification.json).
