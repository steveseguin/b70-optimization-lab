# Packet 21 prepared windows

CPU preparation only. No device ran and no device speed is claimed. The host
remains in FAULT HALT. These commands are sealed preparation, not authorization
to launch. The owner must authorize reboot/recovery and subsequent device work.
The build seal requires `fault_halt_boot_id`; every window refuses that exact
boot before loader inspection or any device child launch. A changed boot is
necessary but does not grant permission by itself. PID 183867 is untouched. No window queues its successor or retries a failure.

Run each command separately from the repository root after admission. Each
creates its own systemd user unit, with idle CPU/I/O priority and two numeric
threads. Every command explicitly sets `ExitType=cgroup`, so the unit stays
running while a retained child remains after the watcher exits. `KillMode=process`
limits a service-stop signal to the watcher main process; `SendSIGKILL=no`
disables escalation, and `Restart=no` forbids automatic restart. `Type=exec`
keeps the watcher as the known main process. These properties are supported by
the installed systemd 255.4. Preserve the owning unit if a cooperative drain
retains its child. Do not stop or kill the whole cgroup to clean up a retained PID.
Never add an external timeout, RuntimeMaxSec, cgroup kill, or restart policy.
The same closed, NEO-free native environment must be used throughout. Loader
preflight refuses missing runtime libraries before launching any device child.

## Admission and coverage

K1 runs both the GEMV and non-GEMV fixture components on one card, twice each
in four distinct processes. The GEMV component creates one owner per process;
the non-GEMV component creates two sequential owners on the same card, first
for the retained prototype and then for the actual runtime adapter. K1 therefore
checks six complete owner teardowns across its two invocations. It compares fused/unfused v2 on
that card, checks `output.bin` against the sealed host fixture hash, and requires
safe teardown. The second K1 receipt binds the first receipt and all four native
outputs. Its binary hash, host fixture hash, runtime binary hash, boot, card and
environment are rechecked before admitting a model window. W1 requires K1 on
its card. W2 and W3 require K1 on a member of cards 2+3, W1 on that same boot,
prompt, binary and K1 receipt, plus W0 on the same boot, binary and card pair.

W0 uses this packet's runtime binary and packet18's hardened canary: 100 peer
round trips, the tiny real owner/adapter boundary path, and 1,000 chained kernels
per card. It requests 1,344 device bytes across both cards. No cross-card native
event dependencies are allowed; every crossing has a host completion fence.

W1 streams one layer at a time on card 3. Its 87-position prompt produces the
first token and continues to eight generated tokens. All eight tokens and all
384 retained layer fixtures must equal the v2 CPU oracle. W2 and W3 use cards
2+3 with resident weights, 64 generated tokens and 384 layer fixtures; frozen
and R5 dispatch respectively. Native commands always include `--fusion on`.
All oracle comparisons are byte-exact, with no tolerance. Native model receipt
schema remains `own-runtime.iq3.packet18.run.v1`, adding `fusion: on`.

The timing rows preserve packet18's definition: generated token index, token
ID, wall milliseconds, GEMV/non-GEMV device milliseconds, kernel submissions,
host waits and transfer wall time. Whole-span decode covers tokens 2 through N;
it excludes prefill and first-token time. Packet18 and packet21 W2 can therefore
be compared directly after device qualification; none has been run here. GEMV
device time includes the work folded into each GEMV launch. The total device
time and wall time remain comparable; category subtotals now contain different
amounts of elementwise work.

## Commands — prepared only

### K1 first owner

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 systemd-run --user --collect \
  --unit=packet21-k1-card3-a --working-directory=/home/steve/llm-optimizations \
  --property=Type=exec --property=ExitType=cgroup \
  --property=KillMode=process --property=SendSIGKILL=no --property=Restart=no \
  --setenv=OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 \
  /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet21-fused/window.py \
  --authorized-device-window --window K1 --card 3 --seconds 10800 \
  --output experiments/own-xpu-runtime/stage2/packet21-fused/build/k1-card3-a
```

### K1 second fresh owner

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 systemd-run --user --collect \
  --unit=packet21-k1-card3-b --working-directory=/home/steve/llm-optimizations \
  --property=Type=exec --property=ExitType=cgroup \
  --property=KillMode=process --property=SendSIGKILL=no --property=Restart=no \
  --setenv=OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 \
  /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet21-fused/window.py \
  --authorized-device-window --window K1 --card 3 --seconds 10800 \
  --repeat-of experiments/own-xpu-runtime/stage2/packet21-fused/build/k1-card3-a/window.json \
  --output experiments/own-xpu-runtime/stage2/packet21-fused/build/k1-card3-b
```

### W0 canary

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 systemd-run --user --collect \
  --unit=packet21-w0-cards23-a --working-directory=/home/steve/llm-optimizations \
  --property=Type=exec --property=ExitType=cgroup \
  --property=KillMode=process --property=SendSIGKILL=no --property=Restart=no \
  --setenv=OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 \
  /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet21-fused/window.py \
  --authorized-device-window --window W0 --card 2 --seconds 600 \
  --output experiments/own-xpu-runtime/stage2/packet21-fused/build/w0-cards23-a
```

### W1: streamed frozen

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 systemd-run --user --collect \
  --unit=packet21-w1-card3-a --working-directory=/home/steve/llm-optimizations \
  --property=Type=exec --property=ExitType=cgroup \
  --property=KillMode=process --property=SendSIGKILL=no --property=Restart=no \
  --setenv=OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 \
  /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet21-fused/window.py \
  --authorized-device-window --window W1 --card 3 --seconds 10800 \
  --input experiments/own-xpu-runtime/stage2/packet21-fused/build/input \
  --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective \
  --k1 experiments/own-xpu-runtime/stage2/packet21-fused/build/k1-card3-b/window.json \
  --output experiments/own-xpu-runtime/stage2/packet21-fused/build/w1-card3-a
```

### W2: resident frozen

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 systemd-run --user --collect \
  --unit=packet21-w2-cards23-a --working-directory=/home/steve/llm-optimizations \
  --property=Type=exec --property=ExitType=cgroup \
  --property=KillMode=process --property=SendSIGKILL=no --property=Restart=no \
  --setenv=OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 \
  /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet21-fused/window.py \
  --authorized-device-window --window W2 --card 2 --seconds 10800 \
  --input experiments/own-xpu-runtime/stage2/packet21-fused/build/input \
  --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective \
  --k1 experiments/own-xpu-runtime/stage2/packet21-fused/build/k1-card3-b/window.json \
  --w0 experiments/own-xpu-runtime/stage2/packet21-fused/build/w0-cards23-a/window.json \
  --w1 experiments/own-xpu-runtime/stage2/packet21-fused/build/w1-card3-a/window.json \
  --output experiments/own-xpu-runtime/stage2/packet21-fused/build/w2-cards23-a
```

### W3: resident R5

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 systemd-run --user --collect \
  --unit=packet21-w3-cards23-a --working-directory=/home/steve/llm-optimizations \
  --property=Type=exec --property=ExitType=cgroup \
  --property=KillMode=process --property=SendSIGKILL=no --property=Restart=no \
  --setenv=OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 \
  /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet21-fused/window.py \
  --authorized-device-window --window W3 --card 2 --seconds 10800 \
  --input experiments/own-xpu-runtime/stage2/packet21-fused/build/input \
  --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective \
  --k1 experiments/own-xpu-runtime/stage2/packet21-fused/build/k1-card3-b/window.json \
  --w0 experiments/own-xpu-runtime/stage2/packet21-fused/build/w0-cards23-a/window.json \
  --w1 experiments/own-xpu-runtime/stage2/packet21-fused/build/w1-card3-a/window.json \
  --output experiments/own-xpu-runtime/stage2/packet21-fused/build/w3-cards23-a
```

## Refusal and retained evidence

`build/fusion-fixtures` is retained K1 input, not disposable scratch. Every
fixture member is hash-bound by the final source manifest; keep those bytes
with the sealed build and do not delete them during scratch cleanup.

Build, CPU tests, input manifest, source hashes and binary hashes must match
`build-receipt.json` before any child is started and are rechecked afterwards.
K1 additionally requires `artifacts_sha256` entries for `device/fused-fixtures`
and `device/nongemv-fixtures`, plus `fused_fixture_host_sha256` and
`nongemv_fixture_host_sha256`. Each component writes into `run/gemv` or
`run/nongemv`. Both fixture programs write
`own-runtime.iq3.packet21.fixtures.v1`, byte hash, exactness flags, submission
maximum and owner teardown; missing evidence fails closed.

The inherited memory admission accounts for owned device buffers, host-backed
weight tables and a 12 GiB reserve; `GPUActive` is recorded separately from RSS.
W2/W3 refuse insufficient available host memory. No memory/swap setting changes.
Any NEO debug key, including an empty value, is refused before creating output
or a fault latch. Sources, native receipt hashes, oracle fixtures, timing rows,
closed native environment and kernel journal are retained for every admitted
window. A fault or expiry requests one cooperative SIGTERM to the captured child,
then waits at most 60 seconds before returning a retained PID to the owner.
There is no hard kill, automatic recovery or retry.

See [DEADLINES.md](DEADLINES.md) for reported expectations, separate submission
budgets and watchdog margins. Fused device runtimes, local-memory pressure,
compiler behavior and per-submission durations remain unqualified until K1.
