# Comm-5b result: reusing the exchange buffers is exact and worth nothing; the two-card exchange lane is closed (2026-10-03)

## In plain words

The idea was to stop allocating a fresh buffer for each of the 155 card-to-card exchanges in a decode step. It
works, it changes no output, and it makes no measurable difference to speed. By the rule written down before the
run it is not shipped. With it, the last cheap idea on the two-card exchange is used up, and the two-card recipe
stays where it is: about 90.3 tokens a second.

## Numbers

Runner [`../scripts/run-20261003-fp8-comm5b-campaign.py`](../scripts/run-20261003-fp8-comm5b-campaign.py),
[preregistration](2026-10-03-fp8-comm5-prereg.md), 23:16-23:40 EDT, kernel 7.0.0-38, no resident server before or
after. Receipts: [`../data/2026-10-03-fp8-comm5b/`](../data/2026-10-03-fp8-comm5b/).

| Server | Strict run 1 | Strict run 2 | Exact vs no-MTP reference |
| --- | ---: | ---: | --- |
| control (shipped allgather overlay) | 90.128 | 90.238 | 12/12, 12/12 |
| candidate A (`b70-allgather-pbuf`) | 90.072 | 90.184 | 12/12, 12/12; ladder 64/64 in all three sections; 2K/8K/16K context screen exact |
| candidate B (`b70-allgather-pbuf`) | 90.264 | 90.326 | 12/12, 12/12 |

Control median 90.183, candidate median 90.224: **+0.05 %**, against a bar of +1.0 % and a run-to-run spread of
about 0.3 %. **No-go.** The overlay stays in the repository as a tested, exact, neutral change.

One gate did not complete: candidate A's chat-quality suite. The research launcher's memory guard stopped that
server (available host memory fell to 2.39 GiB, guard floor 2.5 GiB) while the suite was running, so the suite's
client got a closed connection. No GPU fault line was logged this time. It does not change the verdict, which fails
on speed alone, but it is the second guard kill of the night at the same margin.

## What this closes, and what it leaves

- **Closed: the two-card exchange lane.** The memo's remaining idea, fusing the gathered add into the following
  add-and-norm kernel, was estimated at 1 to 2 % for one to two days of kernel work. Under the owner's rule of not
  chasing one-or-two-percent levers it is not started.
- **Not obtained: the clean one-rank profile.** It needs more free host memory than a resident two-card server
  leaves on this machine while an agent session is also running.
- **A measurement worth keeping from tonight's one-card servers:** the draft head's precision is not what limits
  speculation. Over identical strict-plus-ladder workloads the INT4 shortlist draft head had 1.978 accepted draft
  tokens per step and the full-precision one 1.968. The first draft token is accepted 75 % of the time and each
  later one about 67 % of the time, which is the model's own MTP module, not our quantization.
- **A host limit worth fixing before more 27B research:** a two-card server leaves about 3 GiB of the 15 GiB
  free, half a gigabyte above the launcher's guard. Either the guard floor comes down (earlyoom is the backstop at
  1.2 GiB) or research runs happen with nothing else in memory.
