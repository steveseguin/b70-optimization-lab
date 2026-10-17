# Packet 63: draft HC and the rank-balance decision — October 17, 2026

The draft HC option is built and sealed with a control, using packet61x as the
base. Both are ready for the coordinator's screens. I skipped the 22/26 split:
rank 1 is already slower in the current packet61x receipts. No GPU, service,
model load or host-setting change ran; packet61x's full record chain was untouched.

The CPU gates pass: each selection has two fresh runs whose 96 target layer
fixtures and 24 tokens equal packet56. All 27 draft proposals and five draft
state files agree between fresh runs. Control also equals packet61x. Synthetic
production-width draft bytes agree, eleven native parser checks pass, and v3
plans pass on lanes A and B for both selections. Device quality and speed are
still pending. Build and selected views occupy 167.38 MB logically, 127.00 MB
across unique inodes, below 400 MB.

## Measured current halves

These are medians of the twelve fixed suite prompts' individual generated
intervals from completed packet61x screens A, B and B2. Incident64 and prefill
are excluded. Each screen has 1,524 intervals (1,197 hits, 327 misses); 1,512
have a following speculative half. Rank 1 finishes last in **all 4,536** complete
cycles across the three screens. This replaces the old packet57 rank0 diagnosis
for this exact configuration.

S is rank0's speculative HALF command envelope, including capture work. B is
rank1's target HALF command envelope, including its full head. D is the draft's
recorded wall time. The last column reports the median of each paired B+D sum,
so the requested rank1 budget **including head and draft** is visible. Because
the draft is asynchronous, this sum is a work-budget approximation, not an exact
GPU-time partition. Even B alone exceeds S, so the split decision does not
rely on adding D. Host `wait_ms` is not GPU idle time.

| Screen | Outcome | S, rank0 ms | B, rank1 target/head ms | D, draft ms | B+D ms (approx.) |
| --- | --- | ---: | ---: | ---: | ---: |
| A | hit | 13.567479 | 15.454779 | 1.921000 | 17.375899 |
| A | miss | 13.565667 | 15.377495 | 1.896024 | 17.307623 |
| B | hit | 13.638275 | 15.250929 | 1.887859 | 17.140751 |
| B | miss | 13.642461 | 15.452203 | 1.892167 | 17.365560 |
| B2 | hit | 13.606950 | 15.203182 | 1.874717 | 17.078460 |
| B2 | miss | 13.608204 | 15.301276 | 1.876280 | 17.199841 |

Corrected rank0 work on misses is 12.452427 / 12.511037 / 12.487094 ms for
A / B / B2. Median hit cycles are 17.414514 / 17.181170 / 17.117333 ms;
miss cycles are 28.514337 / 28.660379 / 28.490804 ms. These attribution numbers
are not a new benchmark and do not use the headline's 99-interval aggregation.

The brief says to skip when B ≥ S, so **no 22/26 selection was built or sealed**.
Memory admission for it is therefore not applicable; no missing-byte amount is
asserted. Neither selection shrinks KV, state or the target head. Both keep
packet61x's 23/25 split and rank1 draft placement. A future split proposal needs
new timing evidence that clears this condition and then a fresh memory check.

[Source-bound diagnosis](../experiments/own-xpu-runtime/stage2/packet63-balance/evidence/diagnosis.json)
and [4,572 retained cycle rows](../experiments/own-xpu-runtime/stage2/packet63-balance/evidence/cycles.jsonl.gz)
come from the completed screen `run/*/receipt.json` rank timestamps, an equivalent
to the per-half timing logs. Raw receipt hashes and the packet57 extraction
method are recorded. The active full chain was not an input.

## What is selectable

`control` leaves every draft switch at production. `draft-hc` is exactly
packet59c's `selections/screen2-hc.json`: eight HC low/gate/inject choices plus
six low-activation and gate/mix fusions. Its selection bytes match that source
selection. Attention, experts/route and norm/merge groups remain production.
The target still verifies every proposed token. The old +0.5% HC screen is
motivation only; no combined speedup is assumed or claimed.

Packet61x's target/controller/wait code and linked target kernels remain
unchanged. One host and one device engine build include both selections. Only
the engine entry and selection parser are recompiled; unchanged objects and
selected device binaries share inodes. Read-only rope bytes link to the parent.
The CPU mini fixture bypasses production-only target HC; that source and its
linked kernels are inherited unchanged. Full device target-oracle parity and
fresh-process determinism remain the coordinator's gate.

[Packet and evidence](../experiments/own-xpu-runtime/stage2/packet63-balance/README.md),
[CPU gates](../experiments/own-xpu-runtime/stage2/packet63-balance/evidence/cpu-gates.json),
[retention](../experiments/own-xpu-runtime/stage2/packet63-balance/RETENTION.md),
[closeout](../experiments/own-xpu-runtime/stage2/packet63-balance/CPU-PREPARATION-CLOSEOUT.md).
Preparation used `nice -n 19`, `taskset -c 8-15,24-31`, `OMP_NUM_THREADS=2`,
`python3 -B`, serial compilation and GNU host-only fixtures. No sudo or services.

## Exact v3 commands per selection and lane

Set `FAULT_REVIEW` to the coordinator's fresh reviewed receipt. Run each
command inside its separately admitted nice0 `screen-*` user unit, with the
v3-required properties and approved `LD_LIBRARY_PATH`. These are device
commands for the coordinator; CPU preparation executed only `--plan`.
Do not schedule lane A while packet61x's record chain owns cards 0+1. Use new
output paths for later attempts; never overwrite or automatically retry.

```bash
P=experiments/own-xpu-runtime/stage2/packet63-balance
V=experiments/own-xpu-runtime/stage2/screen/v3
```

**control, lane A, physical cards 0+1:**

```bash
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane A \
  --lineage "$P/selections/control" \
  --seal "$P/selections/control/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet63-control-A"
```

**control, lane B, physical cards 2+3:**

```bash
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane B \
  --lineage "$P/selections/control" \
  --seal "$P/selections/control/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet63-control-B"
```

**draft-hc, lane A, physical cards 0+1:**

```bash
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane A \
  --lineage "$P/selections/draft-hc" \
  --seal "$P/selections/draft-hc/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet63-draft-hc-A"
```

**draft-hc, lane B, physical cards 2+3:**

```bash
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane B \
  --lineage "$P/selections/draft-hc" \
  --seal "$P/selections/draft-hc/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet63-draft-hc-B"
```

The lineage seal selects the binary and dispatch; both selections use the same
executable bytes. V3 applies lane masks; both native ranks address masked cards
0 and 1. The current 23/25 placement and default `token` timing are retained.
Require all 13 exact checks. Screens are nonqualifying; no result here replaces
the full chain or the unchanged packet49 oracle.

For a CPU-only plan, replace the entire `taskset ... env ...` prefix with
`nice -n 19 taskset -c 8-15,24-31 python3 -B`, retain the script and selection/lane
arguments, add `--plan`, and omit `--authorized-device-window --fault-review ...`.
The four retained plans live in each selection's `plan-A.json` / `plan-B.json`.

## Git handoff

Packet63's staged source/evidence/note files were included by the concurrent
shared-index commit `a20f40e4013a6ddc3dbfe872dd1b2ddc7d2fcc63`, together with
the coordinator's v3 placement work, and pushed to `main`. That commit is
preserved. The immediate packet63 follow-up records its `CURRENT.md` entry and
this handoff; no history was rewritten. Repository hygiene over the combined
commit passes with zero warnings and zero errors. The packet's four plans were
independently rechecked and match their retained bytes; seals and binaries are
unchanged ([final verification](../experiments/own-xpu-runtime/stage2/packet63-balance/evidence/final-verification.json)).
