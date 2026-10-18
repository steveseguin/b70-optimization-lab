# Packet58g coordinator launch

Fresh output: `evidence/card0-58g-a`. Order:
K1a → K1b → KD → W2m → WS → WS128x → WS128. Gaps remain 90 seconds.
No prior K1 receipt is reusable under the new seal. No retries or resident service.

The coordinator supplies its actual reviewed past UTC `REVIEWED_THROUGH` boundary
and `LD_LIBRARY_PATH`. The CPU plan uses January only as a non-launch fixture.
Never replace the reviewed boundary with the current time. Prior frozen latches
and any unresolved shared coordination remain for the coordinator; this packet
never clears someone else's marker.

One-line launch from the repository root (not executed by CPU preparation):

```bash
systemd-run --user --unit=packet58-onecard-58g-a --property=Restart=no --property=SendSIGKILL=no --property=TimeoutStopSec=infinity --property=Nice=0 --working-directory=/home/steve/llm-optimizations /usr/bin/taskset -c 0-3,16-19 /usr/bin/env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" /usr/bin/python3 -B /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58g-onecard/queue_runner.py --authorized-device-window --card 0 --output-root /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58g-onecard/evidence/card0-58g-a --faults-reviewed-through "$REVIEWED_THROUGH" < /dev/null
```

The coordinator parent starts at nice 0 on lane-A cores. All W windows inherit those
cores and priority all the way to the native owner; receipt validation checks
`cpu_affinity=[0,1,2,3,16,17,18,19]` and `observed_nice=0`. K1 and KD start at
nice 19 on helper cores. No child tries to raise its own priority.

CPU-only runner dry run:

```bash
P=experiments/own-xpu-runtime/stage2/packet58g-onecard
nice -n 19 taskset -c 8-15,24-31 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$P/queue_runner.py" --plan --card 0 --output-root "$P/evidence/card0-58g-a" --faults-reviewed-through 2026-01-01T00:00:00Z < /dev/null
```

K1 requires 12 GiB available. Exact model windows retain 85,565,068,816 bytes;
WS128 holds the whole host and retains 118,308,908,048 bytes. All windows retain
the 8 GiB live reserve, memory fence, native mask, host-shadow accounting,
18 GB expert cache, BF16 KV and journal checks. Shared teardown spacing is 60 s.
The queue admits 2,952,790,016 output bytes above the existing 8 GB storage floor.

A proven refusal before compute releases only its own drain and lane reservation
after complete native shutdown, no remaining owners and clean kernel postflight.
It stays failed and stops the chain. Unknown shutdown, live processes, foreign
card owners or faults retain coordination. No shared `screen/v3` implementation
was edited. All device exactness and speed evidence remains pending.

WS128x is exactness under possible shared load, not a timing qualification.
A second whole-host timing run is still required for a speed verdict; the strict
512-token promotion gate remains false. This task does not publish a result.
