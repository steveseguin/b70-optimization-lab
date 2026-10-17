# CPU preparation

Run from the repository root, one compiler at a time. No device entry runs.

```bash
P=experiments/own-xpu-runtime/stage2/packet59c-draft-select
cpu59c() { nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$@"; }
cpu59c "$P/build.py" gnu-host --jobs 1
cpu59c "$P/p59c_cpu_gate.py"
cpu59c "$P/p59c_operator_gate.py"
cpu59c "$P/test_selection.py"
cpu59c "$P/build.py" device --jobs 1
cpu59c "$P/p59c_seal.py"
cpu59c "$P/p59c_seal.py" --verify
```

The fixture commands create evidence and refuse an existing per-choice/output
folder. Preserve prior receipts before deliberately repeating a gate. Do not
rebuild a sealed packet in place; hardlinked selection binaries must remain
immutable. On a clean reproduction checkout the retained evidence can be
reviewed against a new separately named preparation, rather than overwritten.

GNU host and Intel device compilation use the inherited precise flags, one
job and the packet-local 1 GB cap / 8 GB remaining-space floor. Existing
packet56 metadata links are read-only; no full model payload scan or download
is needed. `rope.bf16` remains a link to the unchanged parent. The CPU mini
fixtures and synthetic operands are small and every subprocess inherits
nice19 and the requested affinity. Builds do not use sudo or services.

The default target arithmetic is verified through source hashes and the same
96 retained target layer fixtures plus 24 generated tokens per mini run.
The route/split32 checks are explicitly separate because the mini engine
bypasses those production-only dispatch paths. Their checks are CPU exactness /
determinism evidence, never GPU speed or device qualification.
