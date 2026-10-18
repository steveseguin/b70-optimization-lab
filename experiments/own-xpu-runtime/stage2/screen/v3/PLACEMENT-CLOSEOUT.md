# Packet 61x placement preparation — closeout

<!-- campaign-closeout -->

## Question and identity

October 17, 2026. Prepare four placements of the unchanged sealed
`packet61x-spin-hcfusion-wait` engine for screen v3, on lanes A (cards 0+1)
and B (cards 2+3). The [packet62 timing analysis](../../packet62-miss-path/DESIGN.md)
puts rank 1's half at 15.21–15.49 ms, versus rank 0's speculative half at
13.73 ms. Those are prior observations, not new placement measurements.

The target remains the quantized compressed IQ3 version, arithmetic
`iq3-p49-split32-v1`, full BF16 KV at context 4096, the same 91,392-row draft
prefix, and the same full-head target verifier and packet49 oracle. No model,
weight, native binary, sealed packet, or running chain was changed.

## Outcome

All four names pass the lineage's own `memory_gate.configuration()` and sealed
`memory-plan.json`. **Memory admission does not establish runtime support.**
Only two placements are supported by this exact engine:

| Placement | Draft rank | Native target-split argument | Target layers on ranks 0/1 | Runtime support | Lane A/B plan exit |
| --- | ---: | ---: | --- | --- | --- |
| `1-split23` | 1 | 23 | 23/25 | Supported control | 0 / 0 |
| `0-split23` | 0 | 23 | 23/25 | Unsupported: resident prefix head | 2 / 2 |
| `0` | 0 | 0 | 22/26 | Unsupported: resident prefix head | 2 / 2 |
| `1` | 1 | 0 | 24/24 | Supported | 0 / 0 |

Native split 0 means the engine's placement-dependent default, not zero
layers. All eight `--plan` invocations completed with the expected status.
The four supported plans are ready for coordinator admission. Do not queue
the four unsupported jobs as GPU screens. No GPU, native model program,
service, journal query, or device discovery ran during preparation.

## What worked

`--placement` resolves to a hash-bound identity containing the draft rank,
split argument, actual layer boundary, both rank budgets, dispatch hashes,
and the admission-code and policy hashes. The worker recomputes that identity
before making an adapter or child, then passes its rank/split fields into the
fixed packet56 transport. Both prelaunch admission and live allocation census
use the selected lineage's memory gate. Its bytes must match the wrapper's
sealed controller ABI. Lean directories without that module use the bound
packet56 gate; only their historical control is enabled without a new audit.

The [policy](placements.json) pins the exact packet61x seal and source evidence.
The K2 policy in [p49_dispatch.py](../../packet61x-spin-hcfusion-wait/p49_dispatch.py)
replaces recommendations with the pinned `dispatch-speed6.json` bytes;
[window.py](../../packet61x-spin-hcfusion-wait/window.py) copies those same bytes
into **both** `dispatch-rank0.json` and `dispatch-rank1.json`. Thus no per-rank
dispatch generation is needed. This checks dispatch compatibility, not a new
K2 measurement, and never reads the running chain's K2 output.

The full input plan/identity is shared; [rank.hpp](../../packet61x-spin-hcfusion-wait/rank.hpp)
filters block ownership at the chosen boundary, keeps embedding/streams on
rank 0 and final/head operations on rank 1. Moving the boundary preserves the
same class dispatch and kernel arithmetic. The native controller and reverse
hidden-state path already expose the draft-rank argument. The supported
rank-1 arms keep their existing resident output head and draft inputs.

All 32 CPU tests pass. Default control plans also still pass for packet56w,
packet60 and packet59c screen1-attention. Tests cover admission failure, rank ownership, changed
identity fields, unknown names, an audit bound to the wrong seal, refusal
before adapter creation, plans without launches/journal/discovery, crossover
argument propagation, and the entire fake-transport request/reset flow. The
64-token incident request plus all twelve 128-token requests remain unchanged.
Saved request receipt bytes match v1, and both supported split arguments reach
the transport. **13/13 exactness against packet49 is still a device gate**, not
an assertion based on the CPU fixture. Diagnostic screens cannot be promoted.

## What failed or remains uncertain

The rank-0 draft arms are memory-admitted but fail the production prefix-head
precondition in [mtp.hpp](../../packet61x-spin-hcfusion-wait/mtp.hpp):
`packet56 production requires the shared resident head`.
The draft constructor requires `e.weights[0]` to contain `output.weight`
before its fallback allocation branch. Rank 0's filtered target plan has no
output head, and `Engine::initialize()` in
[main.cpp](../../packet61x-spin-hcfusion-wait/main.cpp) loads resident weights
only from that local plan. The ledger reserves 839,321,600 duplicate-head
bytes, but this engine does not reach that duplicate-head allocation in
production. Changing dispatch cannot repair that missing resident weight.
Neither arm may reach a device merely because the memory ledger admits it.

The control's reduced 8 MiB scratch is scoped to rank1-draft split23; the other
placements retain legacy scratch. Their own ledger rows include those larger
allocations. Minimum arena headroom across ranks is 89,364,320 bytes for the
control, 1,458,960,930 for `0-split23`, 2,067,718,028 for `0`, and 945,091,894
for `1`. Driver residency and current host admission remain device-window
checks. These are calculated budget margins, not measured free VRAM.

## Evidence and patches

- [Eight job lines](placement-jobs.txt), in exact
  `out|lineage|seal|binary|dispatch|placement` format. Paths are relative to the
  repository root. Lane is the final `-A` or `-B` in `out`.
- [All commands, exit statuses and plan hashes](placement-validation/plans/commands.json).
- [New wrapper seal](placement-validation/wrapper-seal.json),
  [CPU tests](placement-validation/cpu-tests.log), and
  [byte comparison](placement-validation/byte-fixture.json).
- Implementation: [placement.py](placement.py), [common.py](common.py),
  [screen.py](screen.py), [worker](tp2_worker.py), [crossover](ab.py).

CPU-only plan replay, from the repository root:

```bash
V=experiments/own-xpu-runtime/stage2/screen/v3
nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/cpu_seal.py" --verify
while IFS='|' read -r out lineage seal binary dispatch placement; do
  case "$out" in ''|'#'*) continue ;; esac
  lane="${out##*-}"
  nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/screen.py" \
    --output "$out" --lineage "$lineage" --seal "$seal" \
    --binary "$binary" --dispatch "$dispatch" --placement "$placement" \
    --lane "$lane" --plan
  status=$?
  case "$placement" in 0|0-split23) test "$status" -eq 2 ;; *) test "$status" -eq 0 ;; esac || exit 1
done < "$V/placement-jobs.txt"
```

The one-time [plan recorder](plan_placements.py) produced the saved plans and
refuses to overwrite them. Planning never creates the proposed run output.
Actual device commands require the existing coordinator window, lane affinity,
fault review, unit, memory and device admission from the [README](README.md).
Pass `--placement` through the coordinator's job reader; do not silently discard
the sixth field. Crossover also accepts `--x-placement` and `--y-placement`.

V1/v2 and all prior v3 results, root-level wrapper seal, build receipt, test log
and byte fixtures retain their original bytes. The new seal lives only under
`placement-validation/` and binds its predecessor hash. Historical v3 source
is available at commit `55fff8638`; old evidence retains its original source
hashes, rather than being relabeled as a placement run. All retained new
artifacts total about 240 KiB; no model or large raw device files were copied.

Initial `git pull --rebase` refused an unrelated unstaged edit. `git fetch`
confirmed HEAD and origin/main matched; that shared edit was left alone.

## Integration record

Commit `a20f40e40` contains this placement work and the concurrently staged
packet63 preparation. The commit command incorrectly continued after the
shared-index scope check failed. Packet63 source was not edited or validated
by this placement task; the CPU tests and plan outcomes reported here cover
screen v3 only. The pushed history is preserved. The follow-up documentation
commit uses an explicit path so it cannot capture another writer's staged work.

## When to revisit

The coordinator can compare `1-split23` and `1` within each lane, requiring
13/13 exact requests against packet49 before considering speed. No device
result is claimed here. Rank-0 drafts require a **separate sealed candidate**
that supplies the prefix head on rank 0 and proves its expanded-head arithmetic,
allocation and exact output; then this policy needs a new seal-specific audit.
Keep the running packet61x chain and its sealed packet untouched.
