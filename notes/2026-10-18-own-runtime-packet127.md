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
