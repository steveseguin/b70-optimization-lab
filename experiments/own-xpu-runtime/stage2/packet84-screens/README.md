# Packet84 composed lane-B screen

CPU preparation only. The four proposed jobs run control, candidate A,
candidate B, control on lane B. No screen or service was started here, and
the live queue was not edited. Actual device exactness, acceptance and speed
remain pending. These 128-token screens cannot qualify a record.

The exact job file is
[`experiments/own-xpu-runtime/ops/lane-queue/proposed-p84s-B.txt`](../../ops/lane-queue/proposed-p84s-B.txt).
The coordinator can use its four JSON lines in that order. Each has a distinct
fresh output under the shared v4 evidence directory, named
`p84s-B-0-control`, `p84s-B-1-candidate-a`, `p84s-B-2-candidate-b`,
and `p84s-B-3-control`.

| View | Recurrence | Route |
| --- | --- | --- |
| control | production | production |
| candidate A | rec-parallel | production |
| candidate B | rec-parallel | fast |

All three use hc-wide, wide64 experts, ordered host cleanup, production dense
and norm, production draft head, draft-HC, batch rollback, placement 1
(draft on rank 1; 24/24 target layers), and full BF16 KV. The control's
selection equals packet80's pinned active selection after removing only
packet84's explicit production `head_format` and `head_prefix` fields.

All views share packet84's device binary, SHA-256
`8b615a0c74db57ab3ceab3cd4a56524d07bc9cf1cb78da2178a947e3918e294a`.
[Composition pins](composition-pin.json) bind the original packet80 selection,
three view seals, packet84 entry points and this preparation's code.
The existing control view is reused. The two new candidate views were created
through packet84's `prepare_packet.seal_view`, then checked by its
`prepare_selections.py` and `screen_seal_support.py`. Packet84's active
selection and all existing root files retain their original bytes.

`screen_job.py` supplies the explicit `--plan` parser required by lanequeue
and delegates to packet84's unchanged `run_screen.py`, which uses the pinned
shared v4 wrapper and packet84 worker. This preserves the lane lease,
fault review, drain, full thirteen exact checks and memory admission.
No source in packet80, packet84, the shared screen tree, or ops was changed;
only the allowed proposed file and new prepared views were added there.

## CPU evidence and commands

[Validation](evidence/validation.json) retains six full-size post-load startup
checks, using packet84's hash-bound CPU mock binary. Both ranks exercise the
selected operation types, allocation extents and draft prefix. They do not
read model payloads or execute device code. Raw censuses and operation captures
remain beside the receipt. [Queue plans](evidence/queue-plan.jsonl) show all
four jobs passed using `lanequeue.py plan --lane B --directory <temporary-copy>`.
Separate `screen-plan-0.json` through `screen-plan-3.json` retain the actual
packet84 worker commands and lane-B placement identities.

The real worker import and screen planning follow packet84 `screen_plans.py`'s
selected rehearsal. Its chain-wide entry point is not run here because it
writes the frozen packet's selected evidence; this preparation retains its
screen checks in this new folder instead. The unchanged packet84 cached CPU
proof is verified by its own preparation tools.

From the repository root, CPU-only recreation and checks are:

```sh
P=experiments/own-xpu-runtime/stage2/packet84-screens
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/prepare.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/validate.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/test_compare.py" </dev/null
```

Preparation requires the original packet84 build and cached proof; see its
[retention instructions](../packet84-record-bundle/RETENTION.md).
View binaries are hard links to that build. Fixture gzip files are retained
with the new views. This is a lab screen, not a standalone published recipe.

After all four device screens complete, run:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet84-screens/compare.py </dev/null
```

The helper rejects missing/failed screens, wrong lane/composition/wrapper,
changed receipts, non-cold or incomplete suites, non-BF16 KV, token mismatches,
bad timestamps and acceptance inconsistent with hit/guess counts. It requires
all thirteen exact checks in all four screens, on one boot in the proposed
order. For each candidate it reports gain over the arithmetic mean of the two
controls' class-median rates, acceptance and its difference from the controls,
whether it beats both controls, and control drift. Each rate is recalculated
over the 99 intervals between token events 1 and 100. Passing this comparison
does not authorize a record chain or promote a speed result.

The [comparison tests](evidence/comparison-tests.log) cover the control-mean
calculation and refusal of bad tokens, missing prompts, caching, changed KV
precision, altered rates, invalid timestamps, bad acceptance and failed exactness.
