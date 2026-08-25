# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R5 result

State: **passed as bounded mechanism and exact-output-parity evidence**.

R5 completed model verification, the GPU0 compute gate, graph-off control,
graph-on candidate, exact raw-output parity, cleanup, idle-state verification,
and the frozen local packet/artifact postflight. Both arms generated 1,293
identical bytes with SHA `cc12d7e...` and cache-zero input state.

The graph-off control reported device 0 and zero for every graph, cache, and
rejection counter. The graph-on arm handled 66 graph requests: it recorded and
created four graphs, served 62 direct cache replays, ended with four entries
under cache limit eight, and reported zero compatibility rejection, device
unsupported, cache-full, update, or recreation events.

The sealed terminal receipt has SHA
`99d05f4fbd84b678e0ad3333025ea529ee71684e260afa826aeb7836b6b7ddad`;
the parity receipt has SHA
`3efb01f7c0cb7145808d754ace73faf1af58c43114b4cfc76178e0749fc1f914`;
and the postflight seal has SHA
`9c97654be4aaedf8e574f2cf54e992d1e8ba2e058992fb5dbbd82cda4bf1a6e8`.

This pass authorizes only the graph mechanism and exact-output-parity claim for
the sealed target-only Q8/F16 TP1 sentinel. The historical build's exact private
dirty source delta is not completely reconstructable, so it authorizes no
seven-cell context curve, site publication, speed floor, record, or submission.
All featured speeds remain immutable.

Next: build a graph-enabled sibling from the clean exact-depth source without
modifying the proven graph-off build, then run a separately preregistered
seven-depth graph curve before filling any graph cells.
