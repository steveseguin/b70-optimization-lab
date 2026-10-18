# Packet144 — exact miss-path study

CPU study closed at the +3% ranking gate. No new mechanism has sufficient
supported transfer; no device proposal is admitted.

[Ranked table and analysis](ANALYSIS.md) · [closeout](CLOSEOUT.md) ·
[DO-NOT-REPEAT](DO-NOT-REPEAT.md) ·
[work note](../../../../notes/2026-10-18-own-runtime-packet144.md).

Reproduce the saved-receipt calculation without model reads:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet144-miss-path/analyze.py --check </dev/null
```
