# P0 passed, and the PCIe link registers on this host are a misreport (2026-09-09)

## P0: the re-fetched checkpoint reproduces the published identity

Both Qwen3.5-9B checkpoints were absent from `steve-b70s` at campaign start and were re-fetched at
their pinned revisions; the R276 image was re-pulled and verified equal to its pinned digest. P0
asked whether that restored the identity the published w1 headline was measured on. It did.

| stage | this run | published w1 | delta |
| --- | ---: | ---: | ---: |
| mtp0-a | 64.152265 | 64.332 | -0.28% |
| mtp0-b | 64.158181 | 64.338 | -0.28% |
| mtp3-a | 110.703734 | 113.627 | -2.57% |
| mtp3-b | 110.628907 | 112.904 | -2.02% |

Gates, all on card 0 with the host otherwise quiet (load 1.02):

- **G1** mtp0-a vs mtp0-b: **12/12**
- **G2** mtp3-a vs mtp3-b: **12/12**
- **G3** mtp3-a vs mtp0-a: **12/12**
- **G3** mtp3-b vs mtp0-a: **12/12**

Depth-3 speculation is byte-identical to no speculation on this checkpoint: lossless, on two fresh
servers, against a same-configuration oracle. The MTP0 pair reproduces to 0.28% and the two fresh
servers agree with each other to 0.009%. The MTP3 pair sits 2.3% under its published pair median,
inside this host's ~3% back-to-back drift but nearer its edge than the MTP0 pair - worth watching in
P3's quiet-host confirms rather than explaining away now.

## The PCIe registers lie on this host

While the gate ran, sysfs reported every B70 at PCIe **2.5 GT/s x1** - Gen1 x1, about 32x below the
`16.0 GT/s, width 16` this host's own deployment doc records. The parent bridges reported the same,
and `max_link_speed` agreed, which idle downtraining does not explain because that is a capability
register. Card 0 was in D0 and actively serving at the time.

```
GPU 23:00.0  cur=2.5 GT/s x1   parent 22:01.0  cur=2.5 x1  max=2.5 x1
GPU 27:00.0  cur=2.5 GT/s x1   parent 26:01.0  cur=2.5 x1  max=2.5 x1
GPU 43:00.0  cur=2.5 GT/s x1   parent 42:01.0  cur=2.5 x1  max=2.5 x1
GPU 47:00.0  cur=2.5 GT/s x1   parent 46:01.0  cur=2.5 x1  max=2.5 x1
```

Measured instead of believed, on an idle card with pinned host memory and 512 MiB transfers:

```
H2D: 28.59 GB/s      D2H: 28.39 GB/s
```

That is 91% of Gen4 x16's 31.5 GB/s. **The links are healthy and the registers are wrong.** Do not
diagnose a bandwidth problem on this host from `current_link_speed` / `max_link_width`; run a
transfer. Had this been taken at face value it would have produced a large, confident, entirely
fictional host-health finding, and any later attribution resting on it would have inherited the
error.

This is the same discipline as the torch-profiler and expandable-segments distortions already
recorded for this hardware: check what a diagnostic actually reports against a direct measurement
before letting it steer a campaign.

## Correction (2026-09-09, same day): the published w1 pair is a DIFFERENT HOST

The comparison table above is a cross-host comparison and must not be read as a reproduction.

No artifact in this lane records a measuring hostname, which is why this was not caught before P0
ran. The evidence that `w1` was measured elsewhere is in the 2026-09-07 harness itself:

- `run-20260907-qwen35-campaign.sh:54` - "Weight loading needs about 10.7 GiB for the 9B on a
  **15.5 GiB host**".
- `2026-09-08-serialnorm-single-request-cost.json` - "the 9B checkpoint is 10.65 GiB, the host has
  **15.5 GiB**", explaining a server death as cgroup OOM under the container's 12g cap.

`steve-b70s` has **125.7 GiB of RAM and four B70s**. The published `w1` campaign ran on a two-card,
15.5 GiB machine. Per this repository's own rule - a result keeps the hardware identity on which it
was measured - the published `113.627 / 112.904` pair is not a target this host is obliged to hit,
and the -2.3% is the expected shape of a cross-host difference rather than an anomaly to chase.

Note which half moved. MTP0 reproduces across four independent fresh servers to **0.0096%**
(64.152265 / 64.158181 / 64.158439 / 64.154632), while only the speculative path differs from the
published figure. That is consistent with different silicon showing up in the draft/verify step
rather than in plain decode, and it is a reason to re-sweep depth and capture geometry here rather
than inherit choices made on the other machine.

**What P0 does establish, all of it on this host:** the checkpoint is hash-identical to the pinned
revision on both the O_DIRECT and ordinary read paths; the runtime is digest-identical to pinned
R276; MTP0 is stable to one part in ten thousand across four fresh servers; and depth-3 speculation
is byte-identical to no speculation on two fresh servers against a same-configuration oracle
(G1/G2/G3 all 12/12).

**Consequence:** this host gets its own baseline, and P0 is it. Every lever is ranked against
`64.155` (MTP0) and `110.666` (MTP3 pair median) measured here. Any submission carries this hardware
identity and does not inherit the other machine's.

### This host's baseline, as it accumulates

| depth | tok/s (class-balanced median) | source |
| ---: | ---: | --- |
| 0 | 64.152265 / 64.158181 | p0 |
| 0 | 64.158439 / 64.154632 | d1 |
| 1 | 93.074862 | d1 |
| 3 | 110.703734 / 110.628907 | p0 |
