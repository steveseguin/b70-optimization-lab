# Packet47: QSA decode attention

Built and sealed with passing CPU gates. **No GPU ran.** Device exactness,
fresh-process determinism and the preregistered speed bars remain coordinator
work. Packet45, packet46 and their historical record oracles are unchanged.

- [Results and limitations](../../../../notes/2026-10-17-own-runtime-packet47.md)
- [Root-cause analysis, floors and suite estimate](ANALYSIS.md)
- [Fixed trees and separate oracle identity](ORACLE.md)
- [Preregistered matrix and 3x/5x bars](PREREGISTRATION.md)
- [Exact card-0 coordinator commands](WINDOW.md)
- [Independent review](REVIEW.md)
- [CPU evidence](cpu-gates.json) and [final seal](seal.json)

The ordered candidate retains the old arithmetic. The alternative split32
candidate defines a new CPU-reference identity; neither is integrated into
the engine. Both retain full BF16 KV. At M=2 the attention control executes
the old kernel twice in sequence, while candidates batch the two rows.
Selection and qgate are timed without changing their arithmetic.

CPU preparation commands, from repository root:

```bash
P47=experiments/own-xpu-runtime/stage2/packet47-qsa-attn
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P47/cpu_gate.py" build
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P47/cpu_gate.py" test
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P47/build.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P47/cpu_checks.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P47/seal.py"
```

Never run the device binary to check its build. Rebuilding changes the seal
and requires new device windows. CPU raw evidence directories are write-once;
[retention instructions](ARTIFACT-RETENTION.md) cover the larger byte streams.
No model payload is used. The suite CSV is a conditional estimate and must
not be promoted as measured performance. Full-engine quality and timing
qualification follow only after passing operator windows.
