# K=2 acceptance probe closeout — diagnostic only

Owner directive: 2026-10-15. Source baseline is the SPEED6/SPEED7 runtime at
`b94bbde80` (the closed-lever ledger). This is an acceptance experiment, not a
speed repair or a qualifying build. No device program was run during preparation.
The coordinator reported the queue stopped before these edits.

## What the second draft consumes

The [publisher model card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)
specifies one MTP layer trained over multiple steps, with four residual branches.
The precise chaining reference is the retained
[MTP implementation](../../../qwen38-flash-next-fp8-b70/reopen-20261008/overlay/vllm/models/qwen4_exp/nvidia/mtp.py),
lines 294–347, SHA256
`d1ba61dd9843e536fff1933b2dca18d92a308d6d7516f0c6ff73ce1b56ea963c`.
It embeds the supplied token, normalizes all four hidden streams jointly before
projection, reuses layer `spec_step_idx % num_mtp_layers`, and returns both the
single-stream sampling hidden and the materialized multistream hidden for the
next draft step. The retained autoregressive proposer advances the input token,
hidden and position together. See also [the accepted wiring review](../packet31-mtp-acceptance/wiring-review.md).

For a normal guess g1 at emitted position p+1, `DraftRuntime::probe_second`
(`mtp.hpp`) saves the draft **after g1 completes**. The extra `compute` takes:

- hidden: the first MTP step's private `streams` buffer, four BF16 streams,
  **before its final mixer**, copied into `merge.hidden`;
- embedding: the same existing target `token_embd.weight` row decoder, indexed
  by **g1**, through the same MTP embedding norm and projection;
- state: the first draft's committed private KV/QSA history, with the draft
  position incremented by one for the extra append and RoPE application;
- head: the same full shared target output head, producing **g2 at p+2**.

It never uses the later actual target token or later target hidden to make g2.
A runtime hash check verifies that `merge.hidden` received the saved first-draft
multistream bytes. Reusing `final.mix` or the original target hidden would be
wrong; neither is used. This probes the existing official-checkpoint-derived
MTP representation: dense BF16 and draft-only group16 INT8 expert requantization
from authenticated official FP8 tensors, with the IQ3 lane's shared embedding
and output head. It does not claim original-FP8 draft arithmetic or change any
of the existing arithmetic.

## Isolation, safety and identity

`rank.hpp` takes the existing synchronous DRAFT path **only with the probe on**.
It computes the normal g1, runs the private transaction, then publishes that
same g1. The native/Python controller and verification code are unchanged; g2
is written only to `rank1/mtp-k2-probe.jsonl`, never to the publication mailbox.
Prompt-only draft steps are not probed. The normal asynchronous path stays in
place with the flag off. This deliberately delays publication and removes its
usual overlap during diagnostics; the resulting suite speed is unusable.

The transaction saves every mutable private draft allocation in host RAM,
including invalid cache tails, scratch, outputs, counters and errors. It restores
all bytes plus the host position and prepared-QSA context extent. It then reads
back and compares every saved allocation before allowing publication. An extra
step's sticky error aborts the diagnostic instead of being cleared by restore.
The same Engine drain owns event profiling/retirement and the four-second event
limit. CopyEngine's 128 MiB, live-owner and extent guards, watchdogs, fault latch,
teardown, storage and memory admission, and all oracle checks are unchanged.

There are **zero new device allocations**, so the 23/25 dr1 rank-1 arena headroom
remains **85.224 MiB**. The retained SPEED6 WS rank-1 census has **27,410,742 bytes**
of mutable private draft allocations excluding the untouched publication and
half-staging slabs. Those bytes become a temporary host backup; one largest
readback and bounded upload staging add temporary host working space. No model
weights are copied into the backup. All new state copies use the existing waited
4 MiB readback/upload helpers; the hidden handoff is 20,480 bytes at production
shape. No wire protocol, shared-memory layout, kernel ABI, dispatch or arithmetic
changes.

Both `window.py` and the direct pipeline/rank entry points refuse the probe
without `--diagnostic-unsealed`. It is limited to 4K, split23, draft rank1 MTP
windows (mini CPU tests use small geometry). Fault-injected draft modes and
non-MTP windows are refused. Qualifying exactness companions must match the
probe flag as well. Diagnostic prerequisites still require the same actual
artifact hashes and boot/configuration. Receipts are marked diagnostic-unsealed,
nonqualifying, and ineligible for speed; the existing submission/promotion
refusals remain active. The flag is `--mtp-k2-probe`.

## CPU evidence

- **26/26 unit tests**: probe admission, qualifying refusal, incompatible
  configuration/provider/window refusal, diagnostic publication/submission
  refusal, exact analyzer denominators, token-position checks, missing/duplicate
  logs, failed-provider coverage, restored-state markers and forecast accounting.
- **8 fresh mini executions / 4 equal pairs**: native and Python controllers,
  five-token and 31-token prompts, five generated tokens. The latter crosses a
  32-position QSA prepared-command boundary. Probe on/off has identical emitted
  tokens, g1 guesses, controller decision counters, all retained layer bytes,
  full target state and full private draft state. **20 second-step samples**.
- **2 fresh persistent mini suites, 2 requests each**: warmup, request reset,
  per-request trace reopening and final draft-state equality. The real analyzer
  processed two classes and **10 samples**, with eight paired outcomes and two
  end-of-request g2 outcomes correctly excluded. The latest analyzer was replayed
  against all **30 measured mini samples** without rerunning arithmetic.
- Actual window CLI and GNU rank CLI both refuse an unqualified probe before
  creating the requested output directory. No device binary was used for tests.

Evidence: [unit tests](evidence/k2-probe/unit-tests.json),
[mini comparisons](evidence/k2-probe/mini-gates.json),
[persistent requests](evidence/k2-probe/mini-suite-gates.json),
[analyzer replay](evidence/k2-probe/analyzer-recheck.json).
The two initial harness failures are retained: wall-clock `stats.redo_ms` was
mistakenly included in equality, and a mini suite requested unregistered storage
context64. The first had equal tokens and model state already; the second was
correctly refused. Only harness accounting/context changed. Exact text and
state hashes are archived before deleting the gate's scratch directories.

GNU host and device targets linking the changed model entry were rebuilt with
at most two jobs, nice19/ionice3, cores4–15,20–31, OMP2: about 33/41 seconds.
No ASAN, compiler matrix, real-model CPU run or reseal. The old final seal stays
untouched and **does not qualify the new binaries**. Fresh mode-build receipts
and `evidence/k2-probe/build-{gnu-host,device}.json` record the actual artifacts.
All five device-linked artifact hashes changed. Device `own-rt-iq3`:
`5ae37c084deb887e7718f43e0223afbaac51c2ab79062eb4d3fdbb3c8d3691a2`.
Build receipts: GNU `552dbe672a84d2eb2133148597c4f2e1f61017d9654937b6754ee1b3371ce102`; device `c410e7e21930f890f2afe9bffe17c7adb307c60daa5c3d5b32b9235bee10c6f0`.

## Analyzer definitions and decision model

Run `k2_probe_analyze.py` on the diagnostic WS directory. It reads measured
`repeat-*/*` requests only, excluding the synthetic warmup. Each g1 is checked
against the normally published draft row at that global token position.
The first generated token's global position is `prompt_tokens`. Every emitted
position must have a valid first draft and log; provider failures or incomplete
coverage refuse analysis instead of silently changing its denominator.

The output gives P(g1 correct) over all samples and over the paired subset,
P(g2 correct | g1 correct), P(g2 correct) unconditionally, sample counts,
per-class statistics and measured extra-step median milliseconds. g2 is compared
to the actual next emitted target token even when g1 was wrong; only joint
correctness earns the second accepted draft in the forecast. The last g2 of each
request has no reference token and is reported as censored, never as a miss.

`extra_step_ms` measures the actual second MTP compute including its embedding
read/upload, normal queue waits and single-owner event accounting. Host backup,
restore/check and total diagnostic delay have separate fields and are excluded
from the projected production schedule. The current probe's speed and CPU mini
acceptance are **not** forecasts of real-model throughput.

For p=P(g1), q=P(g2|g1), D1/D2 the measured first/second draft costs, and T3 the
complete recurring three-target-position verify/recovery budget:

`projected tok/s = 1000 * (1 + p + p*q) / (T3 + D1 + D2)`.

The analyzer reports the T3 break-even against **39.422009** and scenarios at
40/45/50/55 ms. T3 remains unmeasured. Preserve the prior **42.52 ms** screen for
two-position verification, but label it correctly: it was the **k=1** block
budget for `1+p` emitted tokens with a 2.8 ms draft. A k=2 block's bonus token
needs three target distributions. Acceptance alone cannot establish a speed win,
and consecutive one-step acceptance is not substituted for q. These are cycle
projections, not a class-balanced benchmark claim; positions within each prompt
are correlated, and the twelve-prompt suite is not an independent-token sample.

## Coordinator commands (not executed during preparation)

Run from the repository root in the existing admitted **nice-0 device systemd
unit**, on cores0–3,16–19, using the approved LD_LIBRARY_PATH. The dedicated
helper reads `PACKET45_DIAGNOSTIC_UNSEALED=1` before `env -i`; every child window
receives `OMP_NUM_THREADS=2` inside that clean environment. K windows remain
nice19; W0p and WS keep their existing nice0 requirement.

```bash
P=experiments/own-xpu-runtime/stage2/packet45-merged3
OUT="$P/build/k2probe-c4096-dr1-s23-cards01-gpu"
PACKET45_DIAGNOSTIC_UNSEALED=1 bash "$P/coordinator_k2_probe.sh" \
  --mtp-k2-probe 0 "$OUT"
```

This is the minimal admitted **K0 → K1a → K1b → K2 → W0p → KD → WS** chain.
WS runs the same full fixed realistic **12-prompt × 128-token** suite and every
emitted-token oracle comparison, with early layer fixtures retained. It needs
no speed-only WS128 companion, W2m or WSs. The chain must be fresh: old qualifying
SPEED6/SPEED7 prerequisites cannot feed these diagnostic artifact identities.
The actual suite command inside the helper is:

```bash
ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 \
  LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$P/window.py" \
  --authorized-device-window --diagnostic-unsealed --mtp-k2-probe \
  --window WS --card 0 --context 4096 --draft-rank 1 --target-split 23 \
  --output "$OUT/WS" --k0 "$OUT/K0/window.json" --k1a "$OUT/K1a/window.json" \
  --k1b "$OUT/K1b/window.json" --k2 "$OUT/K2/window.json" \
  --w0p "$OUT/W0p/window.json" --kd "$OUT/KD/window.json" \
  --dispatch "$OUT/K2/run0/dispatch-measured.json" \
  --suite-manifest experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json \
  --controller native --repeat 1 --retain-steps 1-8
```

After it completes, CPU analysis only:

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 \
  python3 -B "$P/k2_probe_analyze.py" "$OUT/WS" \
  --output "$OUT/k2-acceptance.json"
```

Reproduce CPU proof with `k2_probe_gate.py`, `k2_probe_suite_gate.py`,
`k2_probe_recheck.py` and `python3 -B -m unittest test_k2_probe test_diagnostic_unsealed`
under the same CPU nice/affinity/OMP restrictions. No device run is part of these
commands. Device acceptance and the resulting numeric forecast remain pending.

Final free disk: **24,987,238,400 bytes**, about 11 MB root usage growth since the first retained disk check, below the 1.5 GB bound. All own mini scratch directories are removed; twelve verified archives retain exact text and binary-state hashes (1.63 MB total). No write/delete command targeted any protected result, incident or record directory.
