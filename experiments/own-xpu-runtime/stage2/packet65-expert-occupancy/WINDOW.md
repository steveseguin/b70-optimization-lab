# Packet65 in-engine class screen

These are coordinator commands. CPU preparation did not open a GPU, create a
service, read the live kernel journal, or run any device window. The frozen
packet64 and screen trees are unchanged.

The local `screen/` copy keeps the v3-packet64 controller, full 13-request flow,
packet49 token checks, memory admission, device isolation, graceful drain,
shared fault latches and shared teardown spacing. Its placement adapter admits
the sealed packet65 24/24 selection views. The campaign obtains the chain's
whole-host reservation (A ownership plus hold-B and B lease), including when
the physical screen pair is B. Each screen holds both legacy v3 lane locks and
checks for foreign Xe clients at admission and during measurement. A class
screen cannot run beside the queued packet64 chain. The coordinator reserves
an idle window; exceptions leave crash-closed reservation markers for review.

## CPU plans

Run from `/home/steve/llm-optimizations`. Each command verifies hashes and prints
commands. It does not start a service or device process.

```bash
P=experiments/own-xpu-runtime/stage2/packet65-expert-occupancy
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/composition_campaign.py" \
  --lane A --candidates wide64 wg64 wg128 prefetch64 \
  --output "$P/screen/evidence/class-A-a" --plan </dev/null
```

Change `--lane A` to `--lane B` and use a fresh output name for lane B.
Single-screen admission uses the ordinary v3 arguments:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/screen/screen.py" \
  --profile tp2 --lane A --placement 1 --timing attribution \
  --lineage "$P/selections/wg64" --seal "$P/selections/wg64/screen-seal.json" \
  --output "$P/screen/evidence/wg64-A-a" --plan </dev/null
```

Live single-screen entry is refused without the campaign's current whole-host
lease. Use `composition_campaign.py` for device execution.

`production`, `wg64`, `wg128`, `prefetch64`, and `wide64` are independent sealed
views of the same executable. Only `choices.experts` changes. Both `token` and
`attribution` timing modes are admitted. `placement=1` means draft rank1 and
balanced target layers 24/24; its native `target_split` argument is zero.

## Coordinator execution

Inside the coordinator's already admitted **nice0 `screen-*` systemd user
unit**, use these properties: `Restart=no`, `SendSIGKILL=no`, `KillMode=process`,
`ExitType=cgroup`, and `TimeoutStopSec=infinity`. Retain the approved library
path. `FAULT_REVIEW` must name the coordinator's fresh boot-bound review.

```bash
P=experiments/own-xpu-runtime/stage2/packet65-expert-occupancy
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/composition_campaign.py" \
  --lane A --candidates wide64 wg64 wg128 prefetch64 \
  --output "$P/screen/evidence/class-A-a" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" </dev/null
```

For lane B, use `taskset -c 4-7,20-23`, `--lane B`, and a fresh B output. The
runner does not create services, retry failures, or restore a server. A signal
is forwarded only to its own current screen child. The existing wrapper owns
safe device draining and leaves uncertain children under the coordinator unit.

The preregistered sequence for each candidate is: unprofiled production screen,
unprofiled candidate screen, attributed production, attributed candidate,
fresh attributed candidate, fresh attributed production. Every screen loads
fresh rank processes and runs incident64 plus all twelve 128-token requests,
resetting request state between them. Profiling is never the first stage.
The campaign stops at the first candidate that passes the class gate in both
fresh matched pairs. Failure or a fault aborts immediately; there is no retry.

## What the gate measures

Attribution observes the existing real layer composition. It does not replay
an expert microbenchmark. It samples generated fixtures 9–16 on every target
layer. Packet57's routed class consists of exactly seven sites per layer:
`router`, `route`, `expsgate`, `expsact`, `expsdown`, `moe`, and `ffn.combine`.
Shared experts, draft work and norms are outside that class. Gate/down timing
is reported separately, never substituted for the larger class.

For each request and rank, take the median of eight complete-half sums of
actual GPU event durations. Sum the rank medians, then take the median within
each prompt class and the median of those class medians. Device timestamp
endpoints are subtracted only on their own device. The incident64 request is
checked for completeness and exact tokens but excluded from the speed ranking.
Cancelled speculative prefixes cannot count as fast complete layers; the last
complete attempt for each fixture is selected and every layer/site is required.
Matched screens must have identical positions and site/event counts.

The bar is **at least 30% lower class latency in each of two fresh matched
pairs**, with no rank regression. This means candidate latency is at most
70% of control, a stricter condition than merely 1.3 times the class rate.
The analyzer directly rereads packet49 oracle tokens, checks all 12 outputs,
and requires identical prompts, outputs, dispatch, topology, conditions and
nonexpert selections. The same candidate executable/seal is required in both
repetitions. It rejects reused screen directories and lifetime receipts.

Reanalyze existing completed screens on the helper cores:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/expert_composition.py" \
  --pair "$P/screen/evidence/class-A-a/wide64/control-1" \
         "$P/screen/evidence/class-A-a/wide64/candidate-1" \
  --pair "$P/screen/evidence/class-A-a/wide64/control-2" \
         "$P/screen/evidence/class-A-a/wide64/candidate-2" \
  --output "$P/evidence/wide64-composition-reanalysis.json" </dev/null
```

This remains diagnostic class-screen evidence. Profiling rates and the 128-token
screens are not public performance headlines. A class pass still needs the
lane's full packet49 quality/determinism and promotion chain; default selection
stays `production` until that work succeeds. No device result is available yet.
