# Packet103: record bundle 5

CPU-only descendant of committed packet97e. Adds packet100's exact 16-row
DOWN transpose and packet101's draft split32 attention to all packet97 choices.
One native binary per compiler selects 512 compositions at startup.

The draft geometry is exact to its own fixed reference; its internal arithmetic
is not claimed bit-identical to the previous draft tree. The unchanged target
still verifies every accepted token. Full device output must match
`iq3-p49-split32-v1`, with unchanged per-prompt acceptance and fresh repeats.
CPU operator proof and startup evidence do not replace that device gate.

The layout retains 360 bytes per DOWN row, so its device storage extent is
unchanged. Load time rearranges every code and half-scale byte without changing
weights. Half-cache still uses its separate 840-byte gate/up stride. The memory
gate runs actual arena allocation/capture on both ranks for every composition.

All eleven chain windows execute their actual startup/host-reference paths on
CPU, with full model shapes and only weight payload/backend mocked. Shared K
fixtures execute once because their command lines have no composition. Each
composition binds those same K results and executes the remaining native paths.
KD projects only target-only storage/report choices, retaining exact selected
draft geometry, route and recurrence. Its real host command stays below 8 GiB.

Prepare in order with nice19, taskset 8-15,24-31, python3 -B, OMP_NUM_THREADS=2
and stdin /dev/null: `build_engine.py`, `cpu_gate.py`, `full_shape.py`,
`prepare_chain.py`, `startup103.py`, `prepare_packet.py`, `queue_plan.py`,
`fast_reseal.py`, `dry_run.py --cached`, `dry_run.py`. All compilation takes
packet94's copied compile_turn lock. Preparation build must remain <=300 MB.

The new orchestration reads one-lane source wins and lane-A vetoes, then writes
fresh control/candidate/control proposals on both lanes. No live queue is edited.
Run `ops/packet103-orchestration/orchestrate.py`; then its immutable decision
with `--decision <file> --chain-output device-cards01-a` after composite results
arrive. `verify_ready.py` refuses until identical-selection brackets and every
chain gate pass. Records remain lane A. No launcher runs during preparation.

Submission receipt replay includes packet80's frozen `data=` fix, placement and
packed-head disclosure, DOWN and attention disclosure, and packet97e's strictly
bound KD projection before any seal. Parent metadata is snapshotted locally;
new screen seals do not pin mutable parent selection/readiness/evidence outputs.

Shared immutable 211 MB CPU fixture payloads use verified per-file symlinks in
a packet-owned directory. They are not copied or modified. The preparation cap
covers this packet’s new build bytes; inherited payload identity is checked.
