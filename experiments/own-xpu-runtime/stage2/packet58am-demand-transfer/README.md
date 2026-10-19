# Packet58am: one-card demand transfer

Only `bcs-demand-retained32x2` is built. Its parent is **packet58ah chain b**,
the full **31.66271941826957 tok/s** composition, not packet58ad or the
resident-lookup change in packet58aj. Packet58aj supplies additional cold-wait
evidence only. This packet claims no device result or speedup.

Coordinator review 38 explicitly authorizes CPU building before the census
verdict. The original [preregistration](../packet58al-demand-transfer-prep/DECISION.md)
is unchanged; its original bytes are also retained in `lineage/DECISION.md`.
`READY-FOR-DEVICE.json` must remain false with the exact release condition
`packet58ai census bound >= 1.000 ms/token`. A predecessor census does not
establish a bound for this full composition.

The private source closure comes from packet58ah's retained 58ag build receipt,
including generated async source, kernel dependencies and checked link objects.
`lineage/source-closure.json` records original/resolved paths and before/after
hashes. Relocation changes include paths only. No active compilation dependency
may resolve to a mutable sibling. Intel libraries remain normal dependencies.
The unchanged packet49 oracle binding is copied without repinning.

The real router precedes a descriptor kernel. A dedicated copy-only BCS list
returns that descriptor while resident gate/up runs. Actual eligible misses
are copied into a fixed 126,156,800-byte pool. Original-slot maps select staged
bytes; the 512-expert pointer resolver never receives a 32-entry table. The
missing-slot consumers have explicit copy-completion barriers, including the
prepared submission path. Resident and missing projections write their
original slots, and activation and ordered combination stay unchanged.

The 64 entries have independent leases. Prior-position cache policy may use a
retained entry for the same later fill, after revocation; the real maintenance
terminal event releases that D2D lease. A retained entry is never used for
later-token expert compute. Both parity selections, empty-cache view changes,
request reset, retirement, error drain and teardown retain separate demand,
foreground and maintenance ownership. Pool exhaustion, unknown pointers and
maintenance-selected misses use the original path. Counters retain unused
stages and repeated demand bytes.

`proposals/smoke.json` and `proposals/v5.json` are inert coordinator command
specifications. They contain fresh job/output names, exact native argv, K1
commands, environment, admission requirements and reader policy. They are not
live queue entries. The coordinator must apply its existing whole-host hold,
drained-lane, fresh fault-review, memory-sensor, fault-polling and graceful-stop
protocol to these commands; `admit.py` performs read-only proposal checks and
cannot launch anything. Gate identity is read from the proposal.

Smoke runs K1a, a 90-second gap, K1b, a 90-second gap, then one model load with
S0 (instrumented full parent) and S1 (candidate): all twelve 64-token requests
in each view. The old mixed kernels are labeled as mixed, not as resident-only
service. Device event streams must prove eligible demand and actual overlap.
Its 2..64 intervals are screening, never the census's 2..100 bound.

V5 is one load: A0/B0/A1/B1/A2, twelve 128-token requests per view. A0 remains
exact and reported, excluded only from speed and drift. Both B views must beat
both A1/A2 by 0.5%, control drift must stay within 3%, and the strict gain must
reach 2%. Detailed diagnostics and event profiling are disabled in every v5
view. Every view retains the maximum allocation, unchanged weights, 4096
context, full BF16 KV and target-only greedy decoding. This diagnostic bracket
cannot replace the fresh chains and publication gates.

`check_streams.py` checks the first completed request using its proposal's
identity, complete streams and unchanged oracle, with no elapsed-time verdict.
`analyze.py` replays actual parent streams, including the first prefill row and
generated token 1. `read_run.py` reads completed smoke/v5 evidence and rejects
missing/edited identities, tokens, bytes and events. In-run data checks have
no elapsed-time verdict; offline same-duration checks use
`max(0.001 ms, 0.02 * max(abs(a), abs(b)))`. Different scopes are not equated,
and overlapping event intervals are unioned before accounting.

The initial per-operation wait is **879 seconds**, at least four times the
largest retained enclosing cold stage across the inspected 58ah/58aj/58ai
evidence. It is not a claimed individual-operation measurement. See
`wait-budget.json`, `storage-budget.json` and `allocation-plan.json`. Device
storage admission keeps 25 GB plus planned writes; CPU preparation stops below
27 GB. The maximum build/preparation footprint is 300 MB. No reserve or cache
capacity is reduced.

All Python preparation commands run with `nice -n 19`,
`taskset -c 8-15,24-31`, `python3 -B` and stdin from `/dev/null`.
`build_engine.py` and CPU native gates take turns through the existing
`ops/compile_turn.py`. Run `prepare.py`, `proposals.py`, `build_engine.py`,
`byte_gate.py`, `ownership_gate.py`, `preparation_gate.py <fresh-suffix>`,
`checks.py`, `budgets.py` and `seal.py` in that order.
`preparation_gate.py` invokes the actual device binary plus
`--cpu-preparation-probe`; only backend/storage/kernel execution are mocked.
It retains the real parser, normalization, allocation ledger, preparation and
first-decode issue path. `strace` receipts check that no model/device path opens.

Ignored object files, native binaries, RoPE data and scratch remain local.
The source manifest and parent hashes specify restoration; they are not public
release assets. Parent evidence is referenced as lineage and is never relabeled
as a measurement from this packet. Full device quality, event-clock consistency,
actual allocation peaks, overlap and speed remain to be checked by smoke/v5.

The retained original link objects and historical source archives are private
copies verified against `lineage/source-closure.json`; they are excluded from
Git to avoid duplicating large existing artifacts. Restore those exact bytes
from the recorded parent paths with `prepare.py`, then rebuild. Active source
and generated source text are committed in full. This is a lab handoff, not a
publicly reproducible release package.
