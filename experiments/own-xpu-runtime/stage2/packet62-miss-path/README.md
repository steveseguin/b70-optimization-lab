# Packet 62: reduce miss recovery work

Separate CPU-prepared candidate built from packet61. The coordinator owns all
GPU windows. Packet61's running record chain and packet61x remain untouched.

**Screen `batch` against `control` first.** Current packet61 receipts show
rank1 finishing last in 1,573/1,574 cycles on lane A and every cycle on B.
Capture work is therefore mostly hidden. The exposed rollback takes about
0.74 ms, followed by a 12.51 ms corrected half. The old packet57 rank0 bottleneck
is no longer the current diagnosis. [Source-bound analysis](evidence/diagnosis.json).

One host build and one device build contain all five immutable selections:

| Selection | Change from packet61 |
| --- | --- |
| `control` | Existing two-bank state and 32-descriptor copy batches |
| `batch` | One uploaded descriptor table and one flat copy kernel |
| `banks` | Third recurrent destination bank; keep the former spare untouched |
| `banks-batch` | Both choices |
| `banks-batch-overlap` | Both, plus host restore bookkeeping while device copies complete |

The selection lives in each `selections/<name>/selection.json`, is SHA256-bound
at engine startup and sealed with the same device executable. No environment
toggle or rebuild selects an arm. The inherited route/recurrence/HC choices,
250 us spin, HC fusion, target arithmetic, BF16 state/KV, 91,392-row draft head
and packet49 target oracle are unchanged.

The third bank removes **29,601,792 capture bytes** per speculative half,
leaving **18,743,058 bytes**, and removes the same bank copies for a terminal
rollback. Confirmed redo already omitted those restore copies in packet61.
The ordinary redo restore payload therefore stays **18,743,058 bytes**. The
flat transport reduces 31 capture / 30 redo-restore submissions to **two each**:
one descriptor upload and one kernel. Those are source accounting, not device
measurements. [Design and memory proof](DESIGN.md).

The complete old rollback envelope is only a **0.74 ms/miss optimistic ceiling**
(about 0.16 ms averaged across tokens). There is no defensible pre-device point
estimate for the new copy kernel. Bank-only capture savings are expected to
have little exposed effect under the current rank1-limited timing. The final
choice overlaps only host bookkeeping; the first corrected-half read still
waits for required restored bytes. Controller dispatch itself is already a
few microseconds, so it was not reordered.

Preparation commands, all from repository root, after the fresh-build bootstrap
in [RETENTION.md](RETENTION.md):

```bash
P=experiments/own-xpu-runtime/stage2/packet62-miss-path
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/prepare_selections.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/build_engine.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_gate.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/diagnose.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal_packet.py"
```

These are fresh-build instructions, not permission to overwrite a sealed
packet. Build scripts refuse existing selection seals. Build dependencies are
packet61's hash-bound retained objects and generated rope header; see
[retention](RETENTION.md). Other inherited helper files are dependencies or
historical interfaces, not additional entry points.

- [Coordinator commands, both lanes and all selections](WINDOW.md)
- [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md)
- [Do not repeat](DO-NOT-REPEAT.md)
- [Task note](../../../../notes/2026-10-17-own-runtime-packet62.md)

No device exactness or speed result is claimed for packet62. A screen is
nonqualifying; any record still requires the coordinator's full chain and the
unchanged packet49 oracle.
