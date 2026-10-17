# Packet58 coordinator windows

These commands are prepared for the coordinator. Preparation ran CPU tests
only. No command here authorizes its own GPU work. Choose physical card 0,
or card 2 when 0 is occupied. Each native process sees only the chosen card,
as visible index 0. The wrapper checks visible ownership, the 54/56 memory
fence, exact memory admission, storage, CPU seal and the kernel journal.
Other-card clients are recorded; their memory still reduces admission.

The coordinator supplies `REVIEWED_THROUGH` as the actual past UTC ISO time
through which faults on the current boot were reviewed. Do not substitute
an automatic current timestamp. Future timestamps and non-UTC timestamps
are refused. The reviewed boundary does not suppress faults after it.

Run inside a coordinator-owned `packet58-*` systemd user unit with
`SendSIGKILL=no`, cooperative SIGTERM, and no restart policy. The commands do
not create or change a service. Keep the approved `LD_LIBRARY_PATH`.
From the repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet58-onecard
OUT="$P/evidence/card0-a"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/memory_plan.py" --admit-current-host
nice -n 19 taskset -c 4-15,20-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/queue_runner.py" --plan --card 0 --output-root "$OUT" \
  --faults-reviewed-through "$REVIEWED_THROUGH"
```

After reviewing the printed commands, the coordinator runs the same queue
without `--plan`, adding the explicit window flag:

```bash
nice -n 19 taskset -c 4-15,20-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/queue_runner.py" --authorized-device-window --card 0 \
  --output-root "$OUT" --faults-reviewed-through "$REVIEWED_THROUGH"
```

For physical card 2 change both `--card 0` values to `--card 2` and use a new
output such as `evidence/card2-a`. No automatic fallback to another card runs.
The serial order is **K1a → K1b → KD → W2m → WS → WS128x → WS128**.
K1a/K1b are two fresh native owners. The final two suites also use distinct
fresh model owners; immutable weights persist across requests inside each
suite, while KV, recurrent state and prompt/response data reset per request.

| Window | Work | Conservative expected allowance | Watchdog |
| --- | --- | ---: | ---: |
| K1a / K1b | Same production expert on VRAM, pinned host and streamed/mixed locations; 20 iterations | 120 s each | 600 s each |
| KD | Fixed prompt, first 8 tokens and layer state against packet49 | 600 s | 1,800 s |
| W2m | Fresh-process repeat of the first 8 tokens and layer state | 600 s | 1,800 s |
| WS | All 12 prompts, 128 tokens, first 8 layer captures | 1,200 s | 3,600 s |
| WS128x | All 12 prompts, exact tokens, no captures | 1,200 s | 3,600 s |
| WS128 | Fresh 12-prompt exact/timing repeat, no captures | 1,200 s | 3,600 s |

These are planning allowances, not measured durations. The queue waits 90 s
after each K1 window and 305 s after model windows. A failed stage ends the
queue without retry, launch cycling or overwriting evidence. The STOP file in
the queue output prevents the next stage; SIGTERM requests graceful stop of
the current window. Expired drain budgets retain the busy child for the
coordinator. PF_EXITING distinguishes a task dropping its memory map during
exit from a broken memory sensor.

Both K1 passes must prove exact bytes, safe teardown and the same exact output
hash across fresh processes. A device without accessible host USM currently
fails closed at K1; it does not reach full-model pinning. Zero-copy is chosen only when both
fresh runs sustain at least 12.5 GB/s of useful expert bytes, half packet55's
measured 25 GB/s copy floor. Otherwise the full chain selects copy-before-use
streaming. Timing never waives byte equality. This is a preregistered path
choice, not a one-card model performance claim. Full-model comparison always
uses the unchanged `iq3-p49-split32-v1` oracle and official retained suite.

The metric matches the existing two-card 128-token scope: conventional
99 intervals from generated timestamps 1 through 100 after TTFT, class medians
then the median across classes, plus p10, mean, all-prompt median, TTFT and
whole-response rate. All 12 prompts run once per fresh suite and report
`cached_tokens=0`. The strict 512-token promotion gate remains false.
Cold load/pin and empty-cache filling are recorded separately; cache traffic
and waits during decode remain included in per-token timings.

The queue reserves 2,952,790,016 output bytes above the unchanged 8 GB free
storage floor; each window rechecks its own allowance. Build contents must
remain below 1.5 GB. No prior packet, protected tree, oracle, or packet57 file
is edited by these commands.
