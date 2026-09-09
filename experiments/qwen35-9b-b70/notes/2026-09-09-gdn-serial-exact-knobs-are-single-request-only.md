# The GDN serial-exact knobs cannot serve concurrent traffic (2026-09-09)

`b7all` set all three GDN speculative serial-exact knobs and the engine refused to start:

```
RuntimeError: serial-exact GDN convolution requires one pure-spec request with two to nine
verifier rows and one state-cache column per row
```

`VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT` is a **single-request** construct. It is a tool for
reproducing one request's arithmetic exactly, not a serving mode, and it fails at engine
initialisation rather than degrading under load.

## Why this closes the line of attack rather than just the arm

The divergence being hunted appears **only at concurrency** - 0 divergences in 630 no-speculation
requests up to 32 users, and nothing at all below 32 users at any depth. A knob that requires a
single pure-spec request therefore cannot be its fix, whatever it does to the arithmetic: the regime
where the problem exists is the regime where the knob refuses to run.

That is worth stating plainly because the naming invited the opposite conclusion. These read as
"make the speculative GDN path exact", and the evidence pointed squarely at the speculative GDN
path, so they looked like the obvious candidates. They are diagnostics for a different question:
*does this kernel reproduce a reference value for one request*, not *can this server hold identity
across a batch*.

## Consequence for the mechanism hunt

Five interventions are now excluded, four by measurement and one by construction:

| candidate | outcome |
| --- | --- |
| Serialised RMSNorm rows | 8/254 against 10/254 - not a fix |
| Graph capture ceiling 64 -> 256 | 10/254 - not a fix |
| lm_head batch invariance | 8/254 - not a fix |
| Row-stable RMSNorm | 13/254 - not a fix |
| GDN serial-exact conv (and any set containing it) | **cannot run at concurrency at all** |

`b4rec` (recurrent only) and `b6delta` (delta only) remain queued and may start, since only the
convolution variant names this constraint in its error. If they do run, they are still measuring
whether an arithmetic change to one stage moves a batch-level property, which the evidence so far
suggests it will not.

**The honest position:** the divergence is a property of how the server batches and schedules
speculative work, not of any single kernel's arithmetic that a knob can serialise. Nothing reachable
from this lane's environment has moved it. Establishing the actual mechanism needs instrumentation
of the verify/accept path under a batch - which is a project, not a knob, and is where this thread
should be picked up rather than continuing to sweep flags.

**What this does not change:** the operating recommendation stands on measurement rather than on
mechanism. No speculation is exact to 32 users over 630 requests and faster in aggregate above 16;
speculation is worth up to 75% below that and costs 3-6% divergence above it. A user needing strict
determinism under concurrent load turns speculation off, and that answer does not depend on knowing
why.
