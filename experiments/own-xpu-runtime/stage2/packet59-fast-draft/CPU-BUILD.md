# CPU preparation

One compiler at a time, no GPU discovery or execution. Run from repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet59-fast-draft
cpu59() { nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B "$@"; }
cpu59 "$P/build.py" gnu-host --jobs 1
cpu59 "$P/p59_cpu_gate.py"
cpu59 "$P/build.py" device --jobs 1
cpu59 "$P/p59_seal.py"
```

The build uses the same compiler and precise flags as packet56. The device
binary is compiled only. Its target is the existing qualified Intel platform
library/compiler base; no runtime upstream refresh is relevant to this
independent engine and owner-specified packet56 base.

The local `build/` is ignored and capped at 1 GB. Its three read-only metadata
links (`input`, `fusion-fixtures`, `fusion-rope.hpp`) point to packet56's existing
build metadata. The builder creates and checks those links after packet56 metadata is
restored; it never runs a weight-scanning preparer. `rope.bf16` is a relative link
to the unchanged parent asset, avoiding another 4 MB tracked copy.

The CPU fixture uses tiny model tensors and at most a few MB of synthetic
production-width operands. No full-vocabulary head fixture is allocated.
The lean check takes seconds. The seal refuses to overwrite an existing seal;
a changed candidate needs a new packet and new CPU evidence.

Keep source/mirror hashes, compiler commands, receipts and binaries. Once both
builds pass, only this packet's `.o` and `.o.d` files may be removed to reclaim
regenerable scratch. No parent artifact is cleaned.
