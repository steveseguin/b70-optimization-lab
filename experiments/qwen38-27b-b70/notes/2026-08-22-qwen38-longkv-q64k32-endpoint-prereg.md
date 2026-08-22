# Qwen3.8 MTP5 Q64xK32 long-KV endpoint campaign (longkv1) preregistration

Date: 2026-08-22

Status: **preregistered and launch-ready.** This is the successor campaign
the [endpoint closure](2026-08-22-qwen38-mtp5-q64k32-endpoint-campaign-closure.md)
reserved: it measures the r4-qualified Q64xK32 integration DSO where the
operator saving is large (the ~75 us/call qualification is a KV1300 figure),
and it removes the prompt-6 stochastic early-EOS pathology **structurally**
rather than by retrying against it.

## Design deltas vs the closed endpoint series (everything else identical)

1. **Suite**: a deterministic 25-row long-KV synthesis suite
   ([tracked copy](../data/2026-08-22-qwen38-longkv-q64k32-suite.json), tiers
   8/8/9 targeting chat-templated prompt lengths ~1250/1550/1850) built by
   [the builder](../scripts/build_qwen38_longkv_q64k32_suite_20260822.py)
   from the frozen 25-prompt short suite (`292dea6a…`), with per-row frozen
   prompt-token bands and tokenizer identity embedded. The strict 100-event
   metric window therefore sits at KV ~1300/1600/1900. Row count stays 25 so
   the sealed TP2 gate checker (which pins exactly 25 prompts) is untouched.
2. **ignore_eos on benchmark requests only**: the bench requests carry
   `{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}`
   through the existing sealed `REQUEST_EXTRA_JSON` channel
   (`VALIDATION_REQUEST_EXTRA_JSON`, newly allowlisted in the sealed
   runner). The quality battery hardcodes its own template kwargs and the
   smoke phase uses a separate script; both were verified untouched by this
   value. With `ignore_eos`, every row decodes exactly `max_tokens=512`
   events, so the 100-event window exists on every row by construction —
   the prompt-6 failure class (58/68/168-token stochastic families, three
   campaign stops) cannot occur.
3. **Mechanical engagement gates in the driver, per arm**: recorded
   `request_extra_json` must equal the campaign value; all 25 bench rows
   must report exactly 512 completion tokens and 0 cached tokens; each
   row's server-reported prompt tokens must land inside its frozen band.

Everything else — sealed compile-cache contract, stages (stock
`604f1b32…` control vs candidate DSO `979e91c1…`, graph manifest
`0642e029…`), model gates, per-rank engagement-marker counts (2 for
candidates, 0 for controls), quality battery on a1/b1, report-only parity,
predecessor regating, fresh never-reused roots — is byte-inherited from the
endpoint6 driver.

## Frozen identities

| Input | SHA-256 |
| --- | --- |
| suite (deployed 0444 + tracked copy, identical bytes) | `abacf86537446f503b683e60bcf690aede9efd12234e6e2b318a9b4860bd2082` |
| suite builder | `62aa2b84c5c20f868316435865136f3c279cc7b29d93d14eed2a2e78ecda4fa4` |
| campaign driver `run-20260822-qwen38-mtp5-q64k32-longkv-abba.sh` | `1842983390e4e5c14c7ae5ea0e9d0bff2b1da2e1bf62bfaf42cbf4600e338d18` |
| sealed runner `run-arm.sh` (adds `VALIDATION_REQUEST_EXTRA_JSON` to the allowlist; no other change) | `d6588154f8eaaab2880c6ea18bb29a8bd0df829bc3d015e65d2c96b75cbea1c5` |

The deployed suite lives at
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-longkv-q64k32-suite-20260822/validation-suite.json`.
All other pins (cache manifest `f3582440…`, quality baseline `45424f1d…`,
model manifest `731d851b…`, target-token bench `045fd8b4…` — sha-verified,
snapshotted, and dormant because the parity peer is empty) are unchanged in
the driver source.

Arm roots: `qwen38-q64k32-longkv1-{a1,b1,b2,a2}-20260822` under the raw
bench-results tree; all fresh, never reused after any stop.

## Metric and decision rule (frozen before launch)

Primary metric per arm: the suite conventional rate
(`summary.tok_s_1_100_intervals_after_ttft`, 99-interval accounting across
the 25 rows). Per-tier medians are recorded report-only.

Order: a1 (control) -> b1 (candidate) -> b2 (candidate) -> a2 (control),
each arm refused until the predecessor passed every sealed + longkv gate.

Pair effects: `e1 = (b1 - a1)/a1`, `e2 = (b2 - a2)/a2`, both on the primary
metric. Conjunctive PASS requires:

- all four arms valid (sealed gates, marker counts, longkv gates, quality
  battery pass on a1 and b1);
- `e1 > 0` and `e2 > 0`;
- `(e1 + e2)/2 >= +1.0%`.

The `+1.0%` hurdle is anchored to measurement resolution, not to the
operator arithmetic: same-config anchors reproduced within ~0.1-0.2%
throughout the endpoint series, and the two completed short-KV pairs
resolved `+0.53%`/`+0.33%` cleanly. The closure note's KV-mix expectation
for long-KV is roughly `+2.5-3%`; if that materializes it clears this
hurdle with wide margin. A result with both pairs positive but a combined
effect below `+1.0%` is a report-only positive, not a pass. Any negative
pair rejects the lever for this suite. No tolerance, seed, suite row, or
hurdle may change after any observation.

PASS qualifies the Q64xK32 policy as the lane's recommended configuration
for long-context serving (recorded in CURRENT.md); it does not by itself
authorize any LocalMaxxing submission (the suite is new, so there is no
comparable public row) and does not change the short-KV default, where the
measured effect remains small.

## Stop and relaunch rules

- Any gate failure stops the campaign at that arm; the root is preserved;
  no same-root retry; no later arm runs.
- Numerical/identity-class failures (oracle, marker, identity, cache,
  band, 512/0 contract) close the campaign with no relaunch.
- Infrastructure-class failures (host/GPU health, server crash before the
  bench, storage) permit at most **one** full-campaign relaunch as
  `longkv2` on entirely fresh roots, after the cause is documented.
- The prompt-6 stochastic budget from the endpoint series does not carry
  over; that failure class is structurally removed here, and its
  reappearance (any row with fewer than 512 completion tokens) would be an
  identity-class stop, since it would mean ignore_eos was not in effect.

## Addendum — longkv1-a1 pre-launch refusal and relabel to longkv2

Before any server start or GPU work, arm longkv1-a1 was refused by the
sealed runner's suite-identity jq, which pinned the historical
`suite_id` string in full mode; the long-KV suite carries its own id. The
root `qwen38-q64k32-longkv1-a1-20260822` (containing only the copied suite
and suite-build log) is preserved and never reused. Fix: the runner's gate
now admits the long-KV suite id alongside the historical one — content
remains bound by the exact suite-SHA gate on the line above — and the
campaign is relabeled **longkv2** on entirely fresh roots
(`qwen38-q64k32-longkv2-{a1,b1,b2,a2}-20260822`). This consumes the
preregistered single relaunch: any further stop of any class closes the
design. Refrozen identities: runner `run-arm.sh`
`522b0954ef752ff05f3afad29ab3c47378f22201bfeb5ee912edd7efb24ed2a3`,
campaign driver
`8dd3b57edbfd8f68f06036694fc1630c30c9221a82c7569227d19ffe51c01d71`.
All other pins, the metric, and the decision rule are unchanged.

## What this campaign cannot show

It measures one integration lever on one suite at KV 1.3-2.0k with MTP5 on
GPUs 2,3. It does not test other context regimes, concurrent load, the
mtp.fc INT4 operator (separate, unintegrated), or quality beyond the
existing battery; and its absolute tok/s values are not comparable to the
short-suite ~101 anchor because the workload is different by design.
