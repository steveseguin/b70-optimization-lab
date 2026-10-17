# Packet49 CPU oracle

This is the new full-model CPU arithmetic authority `iq3-p49-split32-v1`.
It keeps the frozen packet17 model graph, deterministic nonlinear functions,
packed-weight dequantization and exact GEMV order. Its QSA equation is an
independent scalar implementation of `iq3-p47-qsa-split32-v1`. Full BF16 state
and KV remain unchanged. Device qualification is pending.

The oracle uses the exact twelve registered prompt input bundles, with128 output
tokens and capacity4096. It retains every layer at steps1–8 and97–104 and all
output-token records. The first prompt's128 tokens cover W2m's64-token prefix.
The incident prompt repeats in a fresh CPU process; this is one-prompt CPU
repeat coverage, not a substitute for whole-suite fresh device owners. The
incident job also captures150 full target stream states for KD's prefill and
64-token draft replay. KD recomputes its host draft reference under its actual
measured dispatch before comparing two fresh device owners.

Two CPU model processes run at most, each with two OpenMP threads, nice19 and
cores4–15,20–31. Only the admitted Unsloth IQ3 path is read, inside these jobs.
One GNU compiler and one composite arithmetic mode are used. The binary has
no accelerator dynamic dependency. No device access, cache dropping, memory
setting or service beyond the requested user unit is involved.

The historical oracle cost is about20 seconds per consumed position. The new
suite has2,386 consumed positions; dividing by two workers gives6.63 hours,
plus roughly1.19 hours for the fresh214-position repeat. The initial estimate
is **6–12 hours**, centered near8 hours. This is an estimate, not a measurement.
Every prompt has a bounded10,800-second CPU deadline. A failed prompt stops new
launches; the other already running CPU prompt drains normally. No automatic
retry occurs, and the campaign refuses an existing campaign directory.

All raw results/build outputs live under
`/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/`.
The tracked `results` symlink points to that directory's `results/` child.
`build-receipt.json` binds frozen source inputs, generated source and the binary;
`arithmetic.json` is immutable before the device seal. Completion creates a
separate receipt and never alters the seal.

From repository root, the coordinator checks completion with:

```bash
nice -n19 taskset -c4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet49-integrate/oracle/oracle_job.py \
  status --require-complete
```

Exit0 requires the complete hash-bound suite, source/binary identities, all
required fixtures, the CPU repeat and KD capture input. Pending/failed runs
return nonzero. The completed manifest is `oracle/results/suite-manifest.json`;
W2m uses `oracle/results/incident-retrospective`. `old-v-new.json` reports every
changed token position against the retained historical outputs, informational
only. The old record and oracle are never rewritten.

The native oracle/independent scalar proof compiled successfully. The scalar
proof checked135,168 FP32 pre-gate values bit for bit against packet47, including
M=1/M=2, split tails and selected contexts. Six negative admission tests pass.
The first compilation failed because generated include relocation treated an
include-path header as source-relative; the corrected generator preserves
ordinary include-path lookup. That initial raw log was overwritten accidentally;
a labeled reconstruction from tool output is retained externally as
`build-attempt1-diagnostic.txt`.

The durable unit is `own-iq3-p49-oracle-20261017b.service`, started at
**2026-10-17 03:44:10 UTC**. Its exact launch is in `unit-receipt.json`.
It has no restart policy and continues independently of the agent session.
The initial unit refused both children before any model bytes were read because
idle IO was missing. Its entire result tree is retained as
`attempt1-io-admission`; the corrected one-off launch added `ionice -c3` with no
source or binary change.

```bash
systemctl --user status own-iq3-p49-oracle-20261017b.service
journalctl --user -u own-iq3-p49-oracle-20261017b.service --no-pager
```

Native progress is in each prompt's `positions.jsonl`, `progress.jsonl` and
`result.json`. Unit output is also retained in external `unit-b.log`. The initial
estimated completion window is October17, 09:44–15:44 UTC; early position timings
should refine this estimate before interpreting it as a deadline.
