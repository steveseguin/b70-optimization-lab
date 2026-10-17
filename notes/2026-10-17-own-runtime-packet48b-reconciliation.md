# Packet48 control reconciliation for packet49

The dimensions and expert formats match production. Ordinary layer4 has
IQ2 gate/up, IQ4 down and Q6 QKV/Z, with the same row counts, K and split1.
The IQ3 exception was reported separately, so an IQ2/IQ3 mix-up does not explain
the failed control check.

Two differences are established in source. Packet48's IQ2 and down controls
call the actual P39 production kernels, but its dense controls wrap the P33
lane function in a different, compile-time non-routed kernel. Production uses
the generic P33 submission closure. Equal arithmetic and SG32 geometry do not
make those compiled programs equal. Packet46 also measures the kernel inside
a complete layer with a generator that repeats 32 blocks per tensor; packet48
uses isolated calls and independently generated row values. Its warmup/pair
counts differ as well. The retained evidence cannot attribute the entire
expert timing difference to one of these causes without new device evidence.

| Primary class | Packet46 current, µs | Packet48 current, µs | Ratio |
| --- | ---: | ---: | ---: |
| IQ2 gate/up | 81.875 / 81.771 | 106.927 / 106.667 | 1.306 / 1.304 |
| IQ4 down | 91.875 / 91.875 | 93.542 / 93.594 | 1.018 / 1.019 |
| Q6 QKV | 100.105 / 100.104 | 63.490 / 63.698 | 0.634 / 0.636 |
| Q6 Z | 39.740 / 39.791 | 31.875 / 31.875 | 0.802 / 0.801 |

The down kernel is the strongest follow-up: its exact P39 control is within
2% of the production class, and the candidate saved about 37 microseconds in
both isolated owners. This is still a candidate, because packet48 explicitly
required full-layer confirmation after any primary control missed 15%.
The approximately 1% exceptional IQ3 gate gain is closed for this integration;
Q8 and M=2 production performance remain unqualified.

[Packet48b](../experiments/own-xpu-runtime/stage2/packet48b-production/README.md)
provides that full-layer comparison. Its current arm is the actual packet45
Engine execution on packet46's fixed layers and fixtures. Its candidate changes
only the four primary GEMVs. It preserves all outputs/state, launch counts,
formats, row arithmetic, 4K context and timing protocol. The coordinator runs
two fresh exactness windows and then two fresh timing windows. Until then,
no packet48 kernel is enabled in packet49 production and no 52-microsecond
production saving or full-model speedup is claimed.

CPU preparation passed: both host/device program builds, two fresh full-layer
CPU fixture processes with 1,824 comparisons each and matching complete output
identities, eight coordinator/parser tests, and the final seal admission.
Seal SHA256: `9f93a517c370f151bc59529e12eecece21488b869935b097b27860a2f73dae2e`.
The build/evidence tree is about 54 MiB outside the repository. No device binary
ran. The first CPU fixture caught a rank-3 expert descriptor mistake during
repacking; its rejected source and receipts are preserved in packet48b's
geometry repair closeout.

The machine, protected packets and old SPEED6 record are unchanged. No GPU,
model payload, sudo, service or host-setting operation was used in this review.
