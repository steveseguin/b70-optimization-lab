# Packet103 CPU preparation and manual handoff

`decision.py` reads current source evidence and writes `decision-dry-run.json`.
It can run before the packet build or seals exist. Source qualification needs
one exact winning lane, and any completed lane-A loss excludes that source.
The first CPU dry run happened before any proposal or launcher was armed.

After the exhaustive packet CPU gates pass, run `prepare_views.py` to seal
the control, candidate, leave-one-out, largest-allocation and all-dimensions views. This keeps disk
space for the chain. It freezes the source decision. Run `orchestrate.py` to use
an immutable decision and write the six composite jobs in
`ops/lane-queue/proposed-p103-composite-A.txt` and `-B.txt`. Planning uses a
temporary queue copy. These files are proposals; no live queue is changed.
Tile16 changes storage, so this preparation uses fresh v4 control/candidate/
control lifetimes on each lane. The packet98c hot-switch wrapper is not used.

Every matching completed bracket counts. Selection, binary, seal, dispatch,
memory plan, placement, profile and timing must match. Every A bracket must
clear +0.5%; B needs a qualifying +0.5% bracket and cannot lose to both controls.
All thirteen prompts must be exact with unchanged per-prompt acceptance.
The chain policy also needs +1.5% on both lanes or two qualified source arms.
Every source is reread for a later A veto before proposal, readiness and launch.
A source win or a microbenchmark is never a composite performance claim.

After coordinator-run composite evidence arrives, evaluate the frozen decision:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/packet103-orchestration/orchestrate.py \
  --decision experiments/own-xpu-runtime/ops/packet103-orchestration/decisions/DECISION.json \
  --chain-output device-cards01-a </dev/null
```

`ready.json` stays false until the evidence and CPU checks pass. The command
recorded there is for a later manually authorized coordinator run; preparation
never executes it. `verify_ready.py` rechecks all bindings and refuses a used
chain folder. A new attempt uses a new suffix and the same frozen selection;
there are no automatic retries. All eleven startup paths, including KD's
host reference, already have to pass on CPU before any view can be sealed.

All CPU commands use nice19, cores8–15/24–31, Python -B and /dev/null. Compile
commands take the copied packet94 lock. Packet build has a 300 MB cap and CPU
processes an 8 GiB address-space cap. Full model exactness, fresh-device repeats
and speed remain device gates against iq3-p49-split32-v1.
