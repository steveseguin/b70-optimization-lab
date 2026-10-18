# Packet90 coordinator handoff

CPU preparation is complete. Device execution is pending and was not performed
by this task. Use the frozen [preregistration](PREREGISTRATION.md) to interpret
packet86's verdict before selecting subsequent designs. Two candidates and the
record-line control are already built and sealed: `exp-halfcache`,
`hc-weightcache`, `production`. Their fixed control is hc-wide / wide64 /
ordered / rec-parallel; fast routing is not included.

The proposed queue files are
[proposed-p90-A.txt](../../ops/lane-queue/proposed-p90-A.txt) and
[proposed-p90-B.txt](../../ops/lane-queue/proposed-p90-B.txt).
They were planned in a temporary queue, with the exact pinned shared v4 wrapper.
These retain the default `A-grid` direction. For B first, use
[proposed-p90-B-grid.txt](../../ops/lane-queue/proposed-p90-B-grid.txt), then
[proposed-p90-A-confirm.txt](../../ops/lane-queue/proposed-p90-A-confirm.txt).
Both new proposals explicitly set `--direction B-grid`. The coordinator owns
live queue insertion and waits for the source grid to complete before admitting
the other lane's confirmation. Never queue both without that dependency.

A runs production / expert / HC / production, each in a fresh owner, with the
shared 64-token startup oracle gate before twelve timed requests. B refuses
unless all A requests are exact, each prompt's target/draft acceptance counts
are unchanged, and a candidate beats both controls. B then runs production /
that winner / production. A alone is screening evidence; do not call a lone
candidate's A run a two-owner performance verdict. B and final analysis still
must pass both quality and speed requirements. All outputs are fresh, no
retries, fixed 90-second inter-screen gaps, no resident service. In `B-grid`
the same rules apply with A and B exchanged. Outputs are named
`p90-<direction>-<lane>-<index>-<choice>`; neither direction reuses old outputs.
Run `compare.py --direction A-grid` or `compare.py --direction B-grid` under
the CPU restrictions below for final interpretation. It refuses a different
confirmation choice, changed acceptance, inexact output, or failure to beat
either confirmation control.

CPU-only verification from repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet90-expert-hc/final_check.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet90-expert-hc/queue_plan.py </dev/null
```

Device jobs must use the ordinary lane-queue coordinator with its fresh fault
review, lane lease, owned systemd unit and fixed environment; the proposal
contains the complete argv. Do not launch a bare engine or reuse another job's
review. A changed pinned dependency is a refusal, not permission to edit a seal.
The compatibility path name is required by the unchanged shared placement
validator; the views remain packet90 identities and do not edit packet64.

Rank-1 actual 30-GiB arena headroom is 630,519,094 bytes for expert and
502,723,894 for HC. Both pass unchanged admission, but device allocation and
driver residency still need the real startup gate. The layouts are separate;
combining them is explicitly refused. No K2 or submission integration is
claimed: those legacy consumers refuse the new choices until a future bundle
qualifies them. No headline or public package follows from these screens alone.
