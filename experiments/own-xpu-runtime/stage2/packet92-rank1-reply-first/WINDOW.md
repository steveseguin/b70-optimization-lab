# Packet92 coordinator handoff

CPU preparation is complete; no device window was run. The two sealed views
use the original pinned shared v4 wrapper. Its 64-token incident gate precedes
twelve cold 128-token requests, each checked against packet49. These are screens,
not the full 512-token final performance gate or record-chain qualification.

Either lane can run production / reply-first / production, with fresh owners
and 90-second gaps. The opposite lane confirms the same exact improving
candidate between fresh controls. Every prompt's hit/guess counts must match;
the candidate must beat both controls on both lanes. A first-lane result alone
never qualifies a win. No retries, service restoration or live queue edits.

| Direction | Grid proposal | Confirmation proposal |
| --- | --- | --- |
| B first | [proposed-p92-B-grid.txt](../../ops/lane-queue/proposed-p92-B-grid.txt) | [proposed-p92-A-confirm.txt](../../ops/lane-queue/proposed-p92-A-confirm.txt) |
| A first | [proposed-p92-A-grid.txt](../../ops/lane-queue/proposed-p92-A-grid.txt) | [proposed-p92-B-confirm.txt](../../ops/lane-queue/proposed-p92-B-confirm.txt) |

Choose one direction. Insert its confirmation only after that grid passes the
winner gate. `run_screens.py --direction B-grid` (or `A-grid`) rechecks this
before launching. The coordinator supplies its normal fresh fault review and
owned systemd unit through the lane queue. Both directions were planned on a
temporary queue directory. Output names include direction, lane and choice.
`compare.py --direction B-grid` or `--direction A-grid` reports the matched
screen verdict. The compatibility directory name is required by the unchanged
shared placement validator; it is still packet92, not an edit to packet64.

CPU recheck from repository root, with stdin from `/dev/null`:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet92-rank1-reply-first/final_check.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet92-rank1-reply-first/queue_plan.py </dev/null
```

Inspect `rank1/p92-host.jsonl` inside each request's rank output along with
`timings.jsonl` and the native command trace. Compare complete token intervals,
not just the shorter half reply: reporting moves into the next draft command.
A smaller half duration alone is not a win. The current bookkeeping remainder,
device exactness, acceptance and end-to-end savings remain unmeasured.
