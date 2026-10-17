# Coordinator: at most four screens

CPU preparation does not authorize a device window. The coordinator owns the
cards and fault review. Use cards 0+1, the same screen wrapper, conditions,
23/25 target split, rank1 draft and twelve cold 128-token prompts plus the
64-token incident check used for the supplied controls. Stop each screen
cleanly before starting another. Do not overlap another lane or auto-retry a
failed screen. Each screen is about 3.5 minutes under the owner's observed
conditions; four are about 14 minutes. Those durations are planning estimates.

The control is `screen/evidence/p56-ctl-b`: 46.795746939 class-balanced tok/s,
18.342310385 ms median hit cycle, acceptance median 0.787401575. Keep the first
control (`packet56-a`) alongside it. The all-on endpoint is already measured
as `p59-a`; no fifth all-on screen is requested.

## Ordered plan

Each JSON starts from packet56 and enables only the listed, disjoint block.
The four blocks cover every packet59 swap and fusion exactly once. This is a
four-way partition of the regression, avoiding the cancellation that two
half-sets could hide. It identifies winning/regressing **groups**; four screens
cannot resolve 40 independent effects and their interactions individually.
The per-swap selectors allow later finer bisection without another build.

| Order | Selection file | Packet59 changes enabled | What the contrast isolates |
| --- | --- | --- | --- |
| 1 | `selections/screen1-attention.json` | Qgate, K/V/indexer projections, split32 attention, output projection and its combine fusion | Attention block, especially extra short-context launch and serial combine tail |
| 2 | `selections/screen2-hc.json` | Three low projections, three gates, both injects, three low activations and three gate/mix fusions | HC schedules and fusions, with original norm trees |
| 3 | `selections/screen3-experts-route.json` | Expert gate/up and down, router/route, shared gate/up/down/router, both activation fusions | Expert/routing block, including virtual-lane register pressure |
| 4 | `selections/screen4-norm-merge.json` | Five norm trees, embedding/hidden projections, hidden merge fusion | Fixed256 trees and the embedding/hidden prelude |

Require all 13 exact checks on every screen. Compare class-balanced throughput,
per-class rates, hit/miss cycles, TTFT and both median/mean acceptance. For
this diagnostic decision, call a block a throughput winner only above the
higher control by 0.05%, and a regressor only below the lower control by 0.05%;
otherwise call it unresolved. This is five times the observed control rate
spread, not a claim about all future host drift. Report cycle improvements
separately if acceptance changes. Never sum isolated group deltas into a
claimed combined result. Keep production for unresolved or losing blocks;
a union of winners still needs its own measured screen/full chain later.

If a screen is inexact, preserve its evidence and reject that selection;
continue independent exactness-safe coordinator work under the existing fault
rules. A GPU fault instead invokes the coordinator's fault/recovery rules.
No screen is a final benchmark, submission or device-determinism qualification.

## Use a prepared selection

The checked-in `selected/screen1-attention` through `selected/screen4-norm-merge`
lineages are ready once their ignored build hardlinks exist. To create a **new**
lineage, or restore them on a clean checkout after rebuilding the same binary,
run the fast reseal command with a fresh output name. Never overwrite a seal.

```bash
P=experiments/own-xpu-runtime/stage2/packet59c-draft-select
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 \
  python3 -B "$P/p59c_seal.py" --fast-reseal \
  --selection "$P/selections/screen1-attention.json" \
  --output "$P/selected/screen1-attention-next"
```

The command validates source/build/CPU bindings, hardlinks the same binaries
and seals the selection. It does not compile or touch a GPU. Custom valid
JSON combinations get two fresh CPU mini runs before sealing. A fusion needs
its candidate producer. Use the returned lineage path below.

```bash
P=experiments/own-xpu-runtime/stage2/packet59c-draft-select
S=experiments/own-xpu-runtime/stage2/screen
L="$P/selected/screen1-attention"
: "${REVIEWED:?set the actual coordinator fault-review UTC timestamp}"
systemd-run --user --unit=screen-p59c-attention-a --collect \
  --working-directory=/home/steve/llm-optimizations \
  nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 \
  python3 -B "$S/screen.py" --profile tp2 --lineage "$L" \
  --binary "$L/build/device/own-rt-iq3" \
  --dispatch "$L/dispatch-speed6.json" --seal "$L/build-receipt.json" \
  --output "$S/evidence/p59c-attention-a" \
  --faults-reviewed-through "$REVIEWED" --authorized-device-window
```

For screens 2–4 change `L`, the unit and evidence names to HC, experts-route
and norm-merge in that order. There is no unattended launch loop here; the
coordinator's existing window ownership governs each screen. The default
packet root is separately sealed with every draft entry at production.

For a CPU-only admission check, run the Python screen command directly with
`--plan` in place of `--authorized-device-window`. It writes no screen output
and opens no device. Saved `screen-plans/*.json` are syntax/seal checks only;
the timestamp used for those plans is not an actual coordinator fault review.
