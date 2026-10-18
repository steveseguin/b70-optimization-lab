# Packet99 artifact retention

The approximately 165 MB build is local and ignored, as are the seven hardlinked
screen-view binary directories. Nothing under any other packet is modified or
deleted. Parent sources and inherited objects are hash-pinned. Rebuild requires
the frozen packet97 local objects plus the recorded compiler paths; this is a
lab research packet, not a portable published model package.

Retained source/evidence includes compact CPU byte archives and case transcripts,
all full-size arena/native-plan archives, linked asm/vISA including the failed
IQ4 arm, compiler logs and receipts, queue plans and seals. Full-shape scratch
is archived then removed after each positive/negative gate; CPU output scratch
is likewise removed after byte verification. See `evidence/fixture-cleanup.json`.

`rope.bf16` is the only new non-build artifact exceeding 1 MiB (4 MiB). It is
an unchanged deterministic runtime lookup fixture, copied byte-for-byte from
packet97 and required by the source closure/startup path, not model weights.
Its hash is in `parent-source-manifest.json` and `build-device-receipt.json`.
Restore by copying the pinned packet97 file and verifying that hash. Retaining
this closed dependency is intentional for repository hygiene review.

Build commands, with `nice -n 19 taskset -c 8-15,24-31`, `python3 -B` and stdin
`/dev/null`, are `build_engine.py`, `cpu_gate.py`, `inspect_registers.py`,
`full_shape.py`, `memory_plans.py`, `build_microbench.py`, `python_gate.py`,
`cleanup_fixture.py`, `seal.py`, `propose_jobs.py`, `queue_plan.py` in that order.
Run in a fresh packet copy; sealed artifacts deliberately refuse overwrite.
Only compilers serialize through the unchanged packet94 compiler-turn lock.
Build and gate processes set the 8 GB address-space ceiling.
