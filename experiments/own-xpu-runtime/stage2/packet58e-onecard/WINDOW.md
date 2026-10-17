# Packet58e coordinator chain: card 0

Fresh output: `evidence/card0-58e-a`. Start at K1a; old receipts have another
seal and cannot be imported. No fallback card. The order is
K1a → K1b → KD → W2m → WS → WS128x → WS128.

Run in a coordinator-owned `packet58-*.service` with `SendSIGKILL=no`,
cooperative SIGTERM and no restart policy. These commands do not create a
service. The coordinator supplies the actual past UTC `REVIEWED_THROUGH`
boundary after reviewing the retained lineage stops; never substitute the
current time. All original latches remain untouched.

From the repository root, plan without creating queue output:

```bash
P=experiments/own-xpu-runtime/stage2/packet58e-onecard
OUT="$P/evidence/card0-58e-a"
nice -n 19 taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/queue_runner.py" --plan --card 0 --output-root "$OUT" \
  --faults-reviewed-through "$REVIEWED_THROUGH" < /dev/null
```

Coordinator device execution, after the existing ownership/fault review:

```bash
nice -n 19 taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/queue_runner.py" --authorized-device-window --card 0 \
  --output-root "$OUT" --faults-reviewed-through "$REVIEWED_THROUGH" < /dev/null
```

| Window | Host scope | Initial available-memory floor | Work allowance / watchdog |
| --- | --- | ---: | ---: |
| K1a / K1b | lane A, exact fixture/path selection | 12 GiB | 120 / 600 s each |
| KD / W2m | lane A, exact 8-token layer checks | 85.57 GB | 600 / 1,800 s each |
| WS | lane A, 12 prompts with early-layer checks | 85.57 GB | 1,200 / 3,600 s |
| WS128x | lane A, 12-prompt exact repeat | 85.57 GB | 1,200 / 3,600 s |
| WS128 | whole host, exact/timing repeat | 118.31 GB | 1,200 / 3,600 s |

Later exactness floors may rise with the preceding full post-load observation.
All six gaps are **90 seconds**; drains and fault polling are unchanged.
The original 8 GiB live reserve applies throughout. These work allowances
are not speed measurements. Time waiting for admission is additional.

The private adapter uses the existing shared
`/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1` protocol.
Lane A stays leased through each window's complete teardown and postflight.
The lane queue waits on its active marker. Between windows the lease releases.
WS128 publishes `hold-lane-B` under `protocol.lock` before waiting for B's
existing lease. A compatible B wrapper stops admitting new screens until the
hold clears. Inaccessible clients still require coordinator ownership review.

The shared v3 teardown permit is held across autonomous native exits, as in
packet70. Compatible B screens may compute but their teardown waits for the
permit and its existing 60-second drain spacing. Uncooperative screens must
not overlap. Device masks remain the original single physical card 0; the
native index is 0. Every observed owned Xe FD must map to 0000:23:00.0.
Foreign lane-A clients block exactness; any foreign Xe client blocks timing.

Failures never retry. STOP prevents the next stage. SIGTERM requests graceful
stop; expired drain budgets retain the busy child and coordination markers.
Only successful native teardown, clean journal postflight and absent owned
processes release the lease and drain permit.

K1 selection remains the original 12.5 GB/s path threshold and exact-byte gate;
under shared load its timing is diagnostic. Model windows retain all unchanged
packet49 oracle and request-reset checks. WS128x is no longer a speed-repeat
qualification; a second whole-host timing run is needed before a speed verdict
or external submission. The strict 512-token promotion gate remains false.

The queue still admits 2,952,790,016 output bytes above the existing 8 GB packet
storage floor. Preparation uses a bounded 500 MiB write allowance; the general
50 GiB repository storage floor is not met or claimed. No cleanup made space.
The saved plan's 2026-01-01 review date is only a CPU command-generation fixture,
not a fault review or authorization.
