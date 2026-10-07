# Durable pilot: failed quality gate, retrieval protocol findings

The pilot stopped at 02:15 UTC after sixteen completed trials. The seventeenth,
dispatch seed 303 with summaries, exhausted its 24 retrieval operations without
submitting answers. The final archive trial did not start. The owned server
stopped and GPU release was confirmed. Nothing is running from this campaign.

The strict standing-reference gate passed 12/12. Both fixed extraction
diagnostics passed with 100% precision, recall and event order (53 events per
style). That calibration did not establish end-to-end task completion.

| Method | Completed | Current answers | Historical answers | Cross-reference answers |
| --- | ---: | ---: | ---: | ---: |
| Quoted events | 6/6 | 46/48 | 7/48 | 0/48 |
| Model-written table/archive | 5/6 | 40/40 | 8/40 | 0/40 |
| Summaries | 5/6 | 22/40 | 38/40 | 20/40 |

These are partial-matrix descriptive counts, not a fair aggregate ranking across
unequal completed subsets. **The quality gate failed; no speed comparison qualifies.**
The original failed attempt must remain visible in any future result.

## What the traces establish

- All 48 original source batches remained byte-exact in each of the seventeen
  stores inspected, including the failed trial. This failure was not source loss.
- Quoted state matched the oracle at 287/288 batch checkpoints; the archive arm
  matched at 240/240 observed checkpoints. There is still one real quoted-state
  error, so the extraction/semantic problem is not declared solved.
- Every completed quoted/archive trial submitted only 8–11 of the 24 requested
  answer keys. Eight responses contained both partial `answers` and a request to
  keep searching. `pilot.py` checks for `answers` first and terminates; it therefore
  discarded the continuing retrieval action. This is a harness protocol defect.
- The failed summary trial searched `batch 2` nineteen times. Literal substring
  search also matches batches 20–29, and its snippets need not include the state
  updates. A direct batch fetch existed, but the model did not switch to it.

## Next revision

First fix and test the answer/retrieval protocol on development data: require
unambiguous actions, preserve partial answers while retrieval continues, expose
the unanswered IDs and remaining retrieval budget, and prevent repeated searches
from silently consuming the whole allowance. Keep unknown answers explicitly
scored as wrong rather than forcing invented answers. Test exact batch retrieval
and the full historical/cross-reference workflow, not extraction alone.

Keep this frozen implementation and its evidence unchanged. A revised system
needs a separate protocol identity, full development-task qualification and fresh
held-out seeds; the observed seeds are no longer unseen. No further GPU run has
been scheduled. Bigger streams and speed optimization remain deferred.

[Portable audit and native result copies](../data/2026-10-07-durable-pilot-result/audit.json)
record all eighteen planned trial statuses, category counts, source-preservation
checks, mixed final responses, original paths and copied-artifact hashes. Raw
call traces remain under the run path in that audit. These native pilot results
are separate from the legacy Harbor/site table.
