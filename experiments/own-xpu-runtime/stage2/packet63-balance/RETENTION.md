# Retention and CPU reproduction

This is a local research candidate, not a portable release. Retain packet61x,
packet59c and their hash-bound source/build dependencies. No model weights
were copied. `rope.bf16` is a read-only relative link to packet61x's same bytes.
The new code is the packet61x source snapshot plus packet59c's draft implementation
and selection parser; [parent manifest](parent-source-manifest.json) records
unchanged input identities. `pipeline.py` also accepts the sealed selection in
mini CPU runs. The target/controller/wait source is byte-identical to packet61x.

The build recompiles only the engine entry and selection parser for host and
device, then links the unchanged retained objects as hardlinks. It separately
compiles a small CPU-only synthetic draft fixture. [Object identity](evidence/object-identity.json)
and [compile commands](engine-commands.json) capture that boundary. The parser's
extra map changes its object layout; both consumers (entry and parser) are
rebuilt together. Other linked objects do not instantiate that selection class.

The build is 108,077,064 logical bytes before CPU runs. Including CPU gate
outputs and both selected views it is 167,380,138 logical bytes, 127,004,378
unique-inode bytes, below the owner's 400 MB cap. Root free space before work
was 18,324,611,072 bytes. No old output was removed. An initial CPU build attempt
found the missing inherited `prototype/snapshot` headers before compilation;
they were copied and pinned, and the next build completed. Both logs remain
in the ignored build tree.

Retain the two engine executables, generated checked include closure, compile
objects/commands, mini-run raw fixtures/state and logs. The compact CPU identities
and production-width byte fixtures are tracked. `evidence/cycles.jsonl.gz`
retains the 4,572 extracted generated intervals without model tokens. Its hash
and the original completed-screen receipt hashes are in the diagnosis. Those
original receipts remain under the existing ignored v3 evidence directories;
the running packet61x full chain is not an input.

For a fresh **unsealed** preparation at this packet's canonical path with its
parent builds restored, first restore the tracked source tree (including
`p28/` and `prototype/snapshot/`). Use a separate retained preparation identity
if the canonical packet is already sealed. Never delete a seal to rebuild it.
The helpers below are this packet's entry points; inherited fixture sources
are dependencies, not alternate build recipes.

```bash
P=experiments/own-xpu-runtime/stage2/packet63-balance
cpu63() { nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$@"; }
cpu63 "$P/prepare_selections.py"
cpu63 "$P/build_engine.py"
cpu63 "$P/diagnose.py"
cpu63 "$P/cpu_gate.py"
cpu63 "$P/seal_packet.py"
```

The commands assume fresh generated selections/build/evidence destinations,
not the retained sealed outputs of this run. A source reconstruction elsewhere
needs the path-bound parent objects restored and a new seal; it is not certified
by these old hashes. The retained device executable is
`57b505fd0e821890fac6c7e0fdec000e1d9cc625604ff944ab5aa04c175cffe0`.
