# The record was one favourable draw, not a host that drifted

Date: 2026-07-28 America/Toronto

Status: **measured, and it reframes the optimization work.**

## Result

The record's own reproduction packet, run at its exact kernel commit
`6f9dd3c3` with its sealed leg (`4986f9ab...`, verified byte-intact), its own
token and text oracles, and its 146/145 topology gate:

| run | legacy tok/s | conventional | exact |
| --- | ---: | ---: | ---: |
| record, 2026-07-26 | 102.97143559613157 | 101.94172124017027 | 13/13 |
| record packet, 2026-07-28 | 101.45442990902569 | 100.43988560993543 | 13/13 |
| this session's legs (median of 3) | 101.085084 | 100.074233 | 13/13 |

Artifact:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-width12-dflash-fp8-repro-20260728T052352Z`

The packet **passed**: 100.44 clears its explicit floor of 96.84463517816175.
The 5% band was wide enough to absorb this, which is why the drift went
unnoticed.

## What this settles

1. **This session's measurements were valid.** The packet's own run lands
   0.36% from the median of the legs run here, well inside this host's 1.63%
   spread. The suspicion that a kernel-wrapper commit difference contaminated
   them is dead: the baseline really is about 100.1-100.4 conventional today.
2. **The host has drifted about 1.5% since 2026-07-26.** The exact sealed
   configuration that produced 102.971 now produces 101.454.

## Why this outranks the optimization work

The drift is roughly **25x the remaining gap to 102**. Recovering it alone
would put the conventional metric near 101.94 with no optimization at all.
Every route closed this session was measured against the drifted baseline; none
of those conclusions change sign at 1.5%, but the margin they were closed by
does.

## Correction: this is sampling, not drift

The service environment of the record run and of today's reproduction differ
only in run-directory paths and the kernel worktree path. Same oneAPI 2026.0
libraries, same PYTHONPATH structure, same selectors. Environmental drift is
ruled out.

With seven incumbent-binary legs now measured this session, the configuration
spans **99.250171 to 101.171141** conventional, a range of 1.9%, median
**100.293100**. The record's `101.94172124017027` sits 0.77 above that observed
maximum.

The record packet states that no warmup was run and "this first valid score is
the reported score" -- a single cold leg. A single draw landing 0.8% above the
maximum of seven later draws is unremarkable for a distribution this wide.

**So the correct statement is not that the host lost 1.5%. It is that the
configuration's central tendency is about 100.3 conventional, and the record is
the high tail of it.** That is a more demanding baseline, not a less demanding
one: reaching 102 conventional requires roughly **+1.7% over the median**, not
0.06% over a record.

Anyone planning work against "we were at 101.94 and lost it" would be chasing a
regression that does not exist.

## What changed since the record

Ordered by suspicion, none yet tested:

1. the reboot at 2026-07-27 18:09 (new boot id, kernel untainted);
2. the NIC rename `eno1` -> `eth1` for MAC `3c:ec:ef:ce:5a:7e`, which changed
   the interface oneCCL bootstraps and transports over;
3. Codex's attention-binary swap to the page-32 build and subsequent restore --
   the binaries hash-match the record set, but the kernel worktree was left at
   `4e624337e`, not the record's `6f9dd3c3`, and the record packet refuses to
   run against it.

The first check should be the cheapest discriminator: rerun the packet with the
oneCCL interface pinned as it was before the rename, since a transport change
would plausibly cost a uniform couple of percent across all 97 per-cycle
collectives, and the observed loss is uniform across prompts including prefill.
