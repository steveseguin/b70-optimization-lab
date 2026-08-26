# Qwen 3.6 embedded-Q8 Q8KV MTP1/2/3/4 expansion R1

State: preregistered, not launched.

This bounded packet expands the four routes admitted by the successful Q8KV
8K screen. It uses one fresh MTP0 control lifetime followed by independent
MTP1, MTP2, MTP3, and MTP4 lifetimes. Every arm covers exact active depths
0/2K/4K/8K/16K/24K/32K with target and draft KV both fixed to `q8_0`, TP1,
graph off, and an exact 128-token completion. The displayed x=0 cell is one
ordinary prompt token with zero prior active context.

Each candidate cell must match both its fresh control output and the sealed
target hash, report zero cached tokens, and show positive conserved draft
counters. Each candidate lifetime then runs its own complete quality battery:
four exact canaries, two identical repeats, and the established long-context
needle, with all seven requests uncached. A candidate failure is route-local so
later routes still run and preserve evidence; any control failure invalidates
the whole comparison.

The packet binds both the certified F16 expansion receipt and the successful
Q8KV route-screen receipt. Runtime identity, source/build hashes, DSO closure,
environment, cleanup, and create-only output rules are inherited unchanged
from the accepted F16 lifecycle. Loader parsing remains whitespace-tolerant for
real `ldd` output. The default `--check` path is inert and performs no GPU,
network, or output action.

No speed floor is preregistered. A passing result is family research evidence
only: it does not authorize site publication, graph claims, LocalMaxxing
submission, headline changes, or replacement of any F16 or protected speed.
