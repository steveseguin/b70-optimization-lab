# Packet58p coordinator launch

Prepared only; not executed. The chain itself rechecks all three packet58n
receipts, the 0.5% rule, screen/chain selection and native binary identity,
and the validated fault capture before any child starts. See README.md.

```bash
systemd-run --user --unit=packet58-onecard-58p-a --property=Restart=no --property=SendSIGKILL=no --property=TimeoutStopSec=infinity --property=Nice=0 --working-directory=/home/steve/llm-optimizations /usr/bin/taskset -c 0-3,16-19 /usr/bin/env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" /usr/bin/python3 -B /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58p-onecard-record/queue_runner.py --authorized-device-window --card 0 --view down-tile16 --output-root /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58p-onecard-record/evidence/card0-58p-a --fault-review /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58p-onecard-record/evidence/fault-review-58p.json < /dev/null
```

The coordinator must first create `evidence/fault-review-58p.json` using the
local fault_review.py helper. The derived window boundary is captured newest
kernel timestamp minus exactly two seconds. The unit starts at nice 0 on
cores 0-3,16-19; K1 and KD children lower themselves to nice19 on helper cores.
All seven stages reserve the whole host; lane B must not overlap. The output
`evidence/card0-58p-a` must remain absent until that authorized launch.
