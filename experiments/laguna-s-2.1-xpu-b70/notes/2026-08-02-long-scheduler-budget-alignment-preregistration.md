# Laguna long-context scheduler-budget alignment

Date registered: 2026-08-02 America/Toronto

Status at registration: host-only harness support is implemented; no service,
device probe, recovery action, or candidate run has started.

Execution update: the separately authorized recovery gate passed and is sealed
at `device-recovery-scheduler-gate-20260802T231513Z`. No scheduler service has
started. The following audit amendment was frozen after recovery but before
control A so the original underspecified phrases cannot be resolved after
seeing a result.

Execution freeze: harness/recovery/oracle commit
`ff1a2b05c9cbb2214690da0352b7d7072af82489`; non-self-referential execution
lock `tools/scheduler-alignment-lock.json`. The lock's own SHA-256 is recorded
by the pair wrapper in its external identity packet. No arm had started when
the lock was created.

## Pre-execution audit amendment

The fixed request order is:

1. `laguna-lc-01024-early`, used as the one first-live warmup and still subject
   to every intrinsic, cache-zero, retrieval, and repeat-output gate;
2. all three 8,192-token placements;
3. `laguna-lc-16384-middle` and `laguna-lc-24576-middle` as the preregistered
   representative 16K and 24K rows;
4. all three 32,640-token placements, each followed automatically by its
   unique sentinel.

The 1K row is excluded from performance comparisons. The 8K and 32K medians
contain three placements each. The 16K and 24K checks are explicitly single-
row ratios; they are not post-result selections.

Control A must match the frozen repeat oracle at
`data/laguna-scheduler-alignment-repeat-oracle-20260802.json`. It is assembled
only from sealed earlier rows. The 8K/16K/24K values come from the prior q12
long-context candidate. The 1K, 32K, and sentinel values come from the existing
exact-prefill selector-on evidence. The known first-32K selector-on output is
accepted as a repeat identity only because it reproduced token- and text-exact
in two independent selector-on services; both source rows failed solely
against the older speculative-candidate oracle, not an intrinsic, retrieval,
cache, or repeat gate. The oracle builder requires both concordant sources for
that exception, including distinct artifact paths, packet hashes, and
`run_identity.created_at_utc` values. The rebuilt 12-row oracle SHA-256 is
`f493347a9cf94125096ac62033f5210922f16e2ae0092687717c1a32c49b4d8d`.
This does not relabel the long output as q1-exact.

Candidate B uses A's fresh `bench.json` as its oracle. The pair analyzer also
requires equality of prompt hashes, output hashes, text hashes, token IDs, and
the complete speculative counters for every matched row.

The only executable entry point for this pair is:

```bash
experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_scheduler_alignment_pair.sh \
  20260802-first-valid \
  data/laguna-scheduler-alignment-repeat-oracle-20260802.json
```

It freezes the source trees, cases, GPU utilization, memory guards, A-before-B
order, and analyzer. It starts B only after A has a complete oracle-exact PASS;
any topology, cleanup, or device-journal failure stops the pair after A. It
creates fresh A, B, and pair artifact roots and refuses existing paths.

Before invoking it, enable exactly one non-persistent 16 GiB
`/swap-laguna-longctx.img` alongside the ordinary 8 GiB `/swap.img`, after
proving the path is absent. Do not add it to `fstab`. The runner now requires
the exact active `/swap.img:8388604 kB` plus
`/swap-laguna-longctx.img:16777212 kB` layout, totaling `25,165,816 kB`; no
substitute or extra swap device satisfies the gate. Disable and remove the
validation swap after the pair or after any stopped arm. The normal 8/16 GiB
available-RAM guards and 4 GiB free-swap guard remain unchanged.

The frozen operational sequence is:

```bash
test ! -e /swap-laguna-longctx.img
sudo /usr/bin/fallocate -l 16G /swap-laguna-longctx.img
sudo /usr/bin/chmod 600 /swap-laguna-longctx.img
sudo /usr/sbin/mkswap /swap-laguna-longctx.img
sudo /usr/sbin/swapon /swap-laguna-longctx.img

# Run the one-shot pair command above, then always remove only this temporary file.
sudo /usr/sbin/swapoff /swap-laguna-longctx.img
sudo /usr/bin/rm -- /swap-laguna-longctx.img
```

The local sudo credential may be supplied from the outside-Git password file
described in `docs/local-ops.md`; it must never enter a command log or artifact.

The runner captures a bounded per-arm kernel journal, fails on the registered
GuC/queue/reset/wedge/device-error patterns, and propagates cleanup or journal
failure to its exit status. A per-rank topology gate, A-only validator, full
common-identity check, fixed-oracle lock, runtime verification audit, and
sealed-recovery/current-boot preflight all run before B is permitted. The live
preflight also rechecks the exact four BDF/`xe`/DRM-node bindings, zero kernel
taint, absence of foreign DRM openers, and the kernel journal since the sealed
recovery gate. It verifies every model file against the frozen NVMe manifest
once before A. The execution lock requires an exact, nonempty dependency set
and hashes; it deliberately does not hash itself. The analyzer applies every
original performance threshold, including each 32K row's `0.95x` decode
floor. This is still the first complete valid pair; no rerun is allowed.

## Premise

The q12 long-context launcher requests `max_num_batched_tokens=8192`, but vLLM
reserves ten additional DFlash slots for a depth-11, one-request service. The
actual scheduler budget is therefore 8,182. Exact 8,192-, 16,384-, and
24,576-token prefills end with 10-, 20-, and 30-token chunks. In contrast, the
32,640-token case ends with a still-wide 8,094-token chunk.

This matches a strong prefill sawtooth in the frozen q12 artifacts:

| prompt tokens | median prefill tok/s | median TTFT s |
| ---: | ---: | ---: |
| 8,192 | 4,129.894 | 1.993 |
| 16,384 | 5,111.214 | 3.228 |
| 24,576 | 5,053.233 | 4.883 |
| 32,640 | 7,345.070 | 4.478 |

The target-only q1 service, which retains a full 8,192-token budget, is smooth
at about 7,089--7,505 prefill tok/s over the same ladder. This is evidence for
a scheduler-tail problem, not a claim that prompt placement or the exact-
prefill source selector causes the sawtooth.

The existing exact-prefill selector can accelerate the 20- and 30-token tails,
but its authenticated range begins at 13 tokens. It cannot activate on the
decisive 10-token 8K tail. The candidate therefore changes no source or model
arithmetic: allocate 8,202 total token slots and explicitly retain 8,192
schedulable tokens.

## Frozen arms

Both arms use:

- main harness support following `d69593cd5`;
- exact-prefill vLLM `4ddb915284d4442885f72bed48311fd04640977c`;
- XPU kernels `99886d783372e621941228250091dc8ebdc1595d`;
- q12 target / DFlash depth 11, TP4/EP4, BF16 KV, exact-prefill selector on;
- `max_model_len=32768`, GPU utilization 0.80, temporary 24 GiB total swap,
  the 8 GiB available-RAM guard, and the normal 4 GiB free-swap guard;
- the unchanged prompt suite, one 1,024-token warmup, cache-zero policy,
  repeat-oracle hashes, retrieval checks, graph topology, and teardown gates.

Control A uses `max_num_batched_tokens=8192` with automatic scheduling, which
must log an effective budget of 8,182. Candidate B uses
`max_num_batched_tokens=8202` and explicit `max_num_scheduled_tokens=8192`.
The harness rejects 8,202 unless it is paired with the explicit 8,192 budget,
q12, and the exact-prefill selector. B must additionally contain vLLM's own
`non-default args` record with both values; the wrapper's launcher echo is not
accepted as runtime proof by itself.

Run a fresh A service before B. Select all 8K placements, representative
16K/24K rows, all 32,640 placements, and the automatic post-32K sentinels. No
request retry is allowed. The device must first be freshly recovered from the
separately recorded `0000:47:00.0` reset-loop failure; this preregistration does
not authorize a reboot, reset, driver reload, FLR, or probe in the current bad
device state.

## Gates

Correctness and identity require:

- every intrinsic, retrieval, cache-zero, and repeat-oracle check passes;
- candidate output hashes and accepted/drafted/cycle counters equal control
  for every matched row;
- control and candidate logs prove their respective 8,182 and 8,192 effective
  budgets;
- all four ranks retain target 146/145 and draft 14/13 capture/replay topology;
- no memory guard, service error, device error, residual process, or teardown
  failure occurs.

Performance uses Prometheus prefill and client TTFT, with conventional decode
as the protected metric:

- the 8K median candidate prefill must be at least 1.35x control and median
  TTFT at most 0.75x control;
- 16K, 24K, and 32K candidate prefill medians must each be at least 0.98x
  control and TTFT at most 1.02x control;
- the 32K conventional decode median must be at least 0.98x control, with no
  matched long row below 0.95x; and
- the sentinel decode median must be at least 0.98x control.

The first complete valid A/B pair is the result. A failed identity, exactness,
memory, device, or cleanup gate stops the lane. This is a non-scored prompt-
processing experiment and cannot produce a LocalMaxxing submission.
