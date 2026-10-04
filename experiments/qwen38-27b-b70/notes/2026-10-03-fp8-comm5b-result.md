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

## Where the 27B's remaining speed could come from, sized (added 2026-10-04)

Written so the next agent does not have to redo the arithmetic. All figures are from the 2026-10-03 servers.

| | One card | Two cards |
| --- | ---: | ---: |
| No speculation: time per step | 51.5 ms (19.4 tok/s) | 29.5 ms (33.9 tok/s) |
| Depth-5 speculation: tokens per step | 2.98 | 2.98 |
| Depth-5 speculation: time per step | 55.1 ms (54.05 tok/s) | 33.0 ms (90.3 tok/s) |
| Cost of speculating (six verify rows, five draft passes) | 3.6 ms | 3.5 ms |

- **One card is limited by memory bandwidth.** A step reads all 25 to 27 GB of weights once: about 500 GB/s, which
  is most of what the card's memory can deliver. Speculation already gets nearly three tokens out of each such read.
- **Two cards lose 3.75 ms a step to the exchange** against the ideal of half the one-card time (25.75 ms). Tonight's
  test removed the allocations and gained nothing; the fused kernel was estimated at 1 to 2 %.
- **Acceptance is the model's, not ours.** First draft token 75 %, each later one about 67 %, the same with an INT4
  or a full-precision draft head.
- **A second guess per step (tree speculation) does not pay.** If the draft's second choice were right in 45 % of
  the misses (an assumption, not measured), a full second chain would add about 0.29 tokens per step (+10 %) and cost
  five more draft passes plus five more verify rows, about 3.5 ms (+10 %): a wash. A two-token second chain nets
  1 to 2 % at best. It would also need branch-aware attention masks and recurrent-state checkpoints in the GDN
  kernels, which is days of kernel work with exactness at risk.
- **Deeper drafts** were measured before: depth 6 is 2 % slower over whole answers.

**Conclusion: the lossless 27B recipes are within a few percent of what this hardware and this model's own draft
module allow.** One card about 54 tok/s, two cards about 90 tok/s. Nothing left on the list is worth more than 1 to 2 %.
