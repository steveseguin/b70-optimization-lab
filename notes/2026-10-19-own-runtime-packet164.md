# Packet164: route fusion checked on CPU

The saved timing does not show the requested 0.4 ms per half of removable
latency. Route already runs as one kernel per layer. Its 24 calls total
0.792448 ms; the visible gaps before them total only 0.003073 ms. Sorting,
normalization, publication and shared activation are inside those calls, so
their individual costs remain unknown.

Packet73's deferred work was partly done later: packet78 combined the route
stages, packet109 added shared activation, and packet112's shorter sorting
network missed its speed gate. A fusion between the router GEMV and the whole
route remains a separate, unqualified idea. The original packet141 analyzer
refusal is preserved; these are diagnostic readings, not a new speed result.

Both compilers pass the CPU arithmetic checks twice:2,304 byte comparisons,
including ties and nonfinite inputs, plus 18 invalid bindings and five invalid
selected routes per run. All four output hashes agree. This checks the route
epilogue after rounded logits; it does not certify the GEMV, device completion
scheme or model output. Ten tests check the saved timing parser and refusals.

At the requested 20% transfer assumption, removing all route work would give
about+1.03% on the one-card line. Removing both route and the entire fused
router class gives only+1.73%. Those are optimistic scenarios, not forecasts.
Full-removal ceilings exceed 2%, so the requested one-card build brief is
retained with explicit gates. No implementation is selected for a device
screen and no READY marker or live queue entry was written.

Next is evidence for a distinct producer-completion mechanism worth at least
0.613 ms/token after added costs. The brief requires the full packet58aj line,
real engine arm/reset tests, the analyzer on real evidence, proper lanequeue
rows, no proof timeout while frozen,25 GB device disk headroom and READY last.
This closes the unsupported latency inference, not the optimization lane.

[Packet and reproduction](../experiments/own-xpu-runtime/stage2/packet164-route-fusion/README.md),
[measurements and pricing](../experiments/own-xpu-runtime/stage2/packet164-route-fusion/ANALYSIS.md),
[prior citations](../experiments/own-xpu-runtime/stage2/packet164-route-fusion/PRIOR.md),
[conditional brief](../experiments/own-xpu-runtime/stage2/packet164-route-fusion/briefs/onecard.md),
[closeout](../experiments/own-xpu-runtime/stage2/packet164-route-fusion/CLOSEOUT.md).

The initial pull refused another worker's local ops edit. A fresh fetch then
confirmed HEAD=origin/main at 4d0edc0884b462df99779fc3e1a90b7163258b5d.
Other workers continued committing on main; their dirty files were preserved.
Only this new packet and this note are committed. CPU work used nice 19,
CPUs 8–15/24–31, Python `-B`, stdin `/dev/null`, and a 4 GB address-space cap;
the compiler peak stayed below 300 MiB. No model/full-shape reads, GPU, service,
sudo, host setting or frozen-tree changes. CURRENT.md's existing edits remain
untouched because live device state and ownership did not change.
