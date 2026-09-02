# Flash-Next BF16 deterministic A4a result

Date: 2026-09-02
Status: complete bounded negative; global flag rejected

## Result

The complete component census ran all 112/112 fresh processes: 14 real BF16
dense families, two early/late sentinels per family, and native/deterministic
replicas in the frozen ABBA/BAAB ordering. All 112 cell records classified, all
112 parent postflights passed, the transient service exited zero, and there was
no technical, device, storage, memory, or swap failure.

`torch.backends.mkldnn.deterministic=True` produced one exact active-output
authority within and across both fresh processes in all 28 cells. It is not a
lossless global replacement, however. Only 24/28 cells passed the preregistered
native-support gate. Both sentinels in `hc_down_inject` and `final_hc_down`—the
four `K=10240` down-projection cells—varied natively and stabilized to a small
number of whole-row results not seen in 200 native sweeps at the same ordinal
rows. The misses affected 5, 3, 4, and 3 of 256 rows respectively. The
`hc_down_inject` synthetic columns 324:336 remained exact numeric zero.

Cost was favorable in aggregate but did not pass every frozen condition. The
multiplicity-weighted candidate/native ratio was `0.986054620`, a component
screening reduction of about 1.4%. Its one-sided family-cluster bootstrap upper
bound was `0.999405616`, and the ABBA/BAAB half ratios were `0.987891950` and
`0.984220714`. Two high-use sentinel points exceeded the local `1.020` cap:
`full_qkv` layer 47 at `1.025427024` and `router` layer 0 at `1.022041671`.
Timing remains component screening evidence and earns no endpoint speed credit.

## Decision and implication

The global provider flag is rejected and remains unapplied. No endpoint,
launcher, protected quality authority, or `5.515783 tok/s` result changed.
The useful mechanism is narrower: native variability occurred only in the four
`K=10240` down cells, while the deterministic provider made every family
cross-process exact. A future dedicated down-projection kernel must reproduce a
declared lossless authority rather than merely choose a different stable
rounding result. The active speed path remains the independently confirmed
W13-N32 MoE configuration and its frozen config-folder-selected qualification.

Raw evidence is retained outside Git at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/bf16-deterministic-census-20260902-a4a`
(`452M`). `summary.json` SHA-256 is
`a98b7c7f34df9795027e1e7b956fde8daef485986f9de31d96813b4c98c6d6d2`;
the service-log SHA-256 is
`fda3c09ce7759cd476bf35c26e0d26cc0b81280025de60a3bf769ced2970456a`.
The compact tracked result is
[`20260902-bf16-deterministic-a4a-result.json`](../data/20260902-bf16-deterministic-a4a-result.json).
