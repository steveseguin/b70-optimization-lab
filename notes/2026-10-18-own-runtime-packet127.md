# Packet127 — exact target-head partition retune

CPU-only preparation started at about 11:32 UTC, with a two-hour limit.
Pull refused unrelated dirty files; fetch confirmed HEAD and origin/main at
`8b7394cfb106db3585b54f3766af1da99c4ac9b7`. Work stays on main. No GPU,
service, sudo, live queue, host setting or foreign process change is authorized.
Commands run nice19, CPUs8–15/24–31, Python -B, closed stdin, an 8 GiB cap
only in explicit CPU entry processes and packet94's serial compiler turn.
Root began with 33 GB free; stop below 25 GB. Build limit: 250 MB.

## Preregistered candidates

Copy packet124's repaired bundle7 line. Keep 24/24 placement, the fixed
80,128-row draft prefix, BF16 KV, target arithmetic `iq3-p49-split32-v1`,
and all other choices. Compare rank0 suffixes **46,080 / 81,920 / 122,880 /
46,080**. The two candidates leave rank1 prefixes of 166,400 and 125,440
rows, both larger than the unchanged draft prefix. These are aligned row
partitions, not approximations or truncated vocabularies. Every vocabulary
row still executes its original arithmetic. The lowest-index tie rule and
sticky nonfinite refusal are unchanged.

Packet87 predicted +1.07% for the original split; packet105b realised only
+0.36% B / +0.38% A. Thus linear scaling is a hypothesis, not a speed claim.
81,920 roughly doubles the transferred rows; 122,880 nearly balances head
rows while retaining the entire draft prefix on rank1. At 3,380 bytes per
expanded row, they add 121,139,200 / 259,584,000 weight bytes to rank0 over
the original split, plus private logits/workspace (34 bytes per added row).
Packet120's saved 24/24 census leaves 4,068,072,332 rank0 arena bytes and
786,269,478 rank1 arena bytes; a fresh real-allocation census must confirm
both candidates. More suffix rows reduce rank1's largest pressure.

Packet118/123's apparent 0.483 ms rank0 slack includes untraced suffix work;
it is not a usable idle budget. Packet120's B placement grid was incomplete
at preregistration (control complete, 25/23 running). Its complete results
will be read before final handoff, with missing evidence explicitly pending.
No candidate is chosen from benchmark outputs or acceptance patterns.

## Required handoff gates

GNU and Intel full-vocabulary byte checks twice at each split, forced boundary
ties, nonfinite refusal, old-reset negative control and repaired reset;
all eleven startup windows per view; actual allocation census; unchanged
native exec limits with inherited-cap negative control; fixed drain scan;
source-bound seals. Each candidate's 4,096-vector device micro must pass
before its v4 B grid. Device execution belongs to the coordinator.
The twelve cold prompts each generate 128 exact tokens. A winning candidate
must beat **both** B controls by at least 0.5%; choose the higher rate with
smaller suffix as deterministic tie-break. Only that candidate receives the
A production / winner / production confirmation, with the same threshold.
No strict512 promotion or speed claim follows from CPU preparation.

## CPU implementation and allocation milestone

The rebuilt executable accepts three sealed head choices; the two new views
change only row ownership. Engine loading, prefix matrix/argmax extents and
private suffix captures derive their bounds from the same registered choice.
The merge body is unchanged; its partition-bound check takes the selected
boundary. There is no mutable global split or environment override.

GNU and Intel each pass two fresh full-vocabulary checks per point (17 cases
per run), including cross-boundary ties, signed zeros and nonfinite refusal.
Both also pass the repaired reset's 21 cases twice at every point; the
old-code control detects six failures each time. All **33 startup windows**
pass, including both KD paths and the actual W0p CPU handshake. Peak startup
child RSS is 1,249,684 KiB. No real model or device output is claimed.

| Rank0 suffix | Rank0 arena bytes | Rank0 headroom | Rank1 arena bytes | Rank1 headroom |
| ---: | ---: | ---: | ---: | ---: |
| 46,080 | 28,144,182,388 | 4,068,072,332 | 31,425,985,242 | 786,269,478 |
| 81,920 | 28,266,540,148 | 3,945,714,572 | 31,304,846,042 | 907,408,678 |
| 122,880 | 28,406,377,588 | 3,805,877,132 | 31,166,401,242 | 1,045,853,478 |

The census executes real allocation/preparation paths with address-token device
storage and no weight payloads. It includes expanded weights and private
suffix logits/workspace. Driver residency remains a separate device gate.
The device micro compiled and has not run. It takes each registered candidate
as an explicit argument and binds the suffix row count into its result.

Sixteen policy/drain tests and a complete mocked-worker test pass. The latter
executes exactly twelve different 128-token requests and derives the legacy
64-token canary receipt from the first response, without a warmup request.
A read-only review caught the inherited shared-wrapper drain import: both
`DrainPermit` and `Teardown` now resolve to copied, clamped local files.
The recursive drain checker passes; original wrappers stay untouched.

[CPU bytes](../experiments/own-xpu-runtime/stage2/packet127-head-retune/evidence/cpu-byte-identity.json),
[allocation census](../experiments/own-xpu-runtime/stage2/packet127-head-retune/evidence/full-shape.json),
[startup proof](../experiments/own-xpu-runtime/stage2/packet127-head-retune/startup103.json).

Re-evaluating packet87's original equations with packet87t's measured transfers
reproduces +1.0685% for 46,080 rows, but gives +0.2272% for 81,920 and
−1.0156% for 122,880 **against that old unsplit control**. Neither predicts a
win over 46,080. These are historical-model sensitivity points, not bundle7
predictions. The grid explicitly tests whether the balance moved with the new
composition. Packet118's untraced suffix work cannot settle it. Packet120's
completed candidate is 3.7956% below its first control, so moving a whole layer
is evidence against abundant rank0 time, not evidence of spare GPU time.
The trailing control was still pending at this milestone.
