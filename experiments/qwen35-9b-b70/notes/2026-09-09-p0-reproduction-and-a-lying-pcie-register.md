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
