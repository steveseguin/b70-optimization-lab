# Qwen3.8 MTP5 Q64xK32 long-KV endpoint campaign v3 (longkv3) preregistration

Date: 2026-08-22

Status: **preregistered and launch-ready.** Fresh design succeeding the
closed longkv1/2 series
([closure + finding](2026-08-22-qwen38-longkv2-closure-and-chunk-corruption-finding.md)),
incorporating exactly the two changes its closure evidence forced. This
is a new campaign identity, not a relaunch of the closed design.

## Changes vs longkv2 (everything else byte-inherited)

1. **Tiers refit under the `max_model_len=2048` wall**: 25 rows
   (8/8/9), builder targets 1250/1375/1500 with ±35 bands; measured
   build lands 1233-1497, so worst-case prompt+window = 2009 < 2048.
   Metric windows sit at KV ~1300/1425/1550 — tier 1 is the exact
   operator-qualification point (KV1300, ~75 us/call).
2. **Both arms run `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0`** — the
   chunkdiag-established mitigation (d5: dose-8 multi-chunk exposure
   fully green with scratch off; scratch on fails byte-identically at
   dose 8 in two independent arms). All 25 rows here are multi-chunk
   (min prompt 1233 > 1024), i.e. dose 25: beyond tested dose, and
   **gated by a1's own quality battery** — if scratch=0 corruption
   emerges at higher dose, a1 stops the campaign before any candidate
   runs and the failure is itself a valuable dose-escalation datum.
   The A-B lever remains the Q64xK32 policy alone; scratch=0 is held
   identical across all four arms.

ignore_eos on bench requests only, the mechanical per-arm gates
(identity `request_extra_json`, 25x512 completions, 0 cached, in-band
prompt tokens), report-only parity, predecessor regating, and fresh
never-reused roots are inherited from the longkv2 driver unchanged.

## Frozen identities

| Input | SHA-256 |
| --- | --- |
| suite (deployed 0444 + tracked copy) | `9a5c4a4e54762aa22e772fb5c6e5fd170c3428e97556f7565a2b1cd8af6d2a6e` |
| suite builder (now parameterized: --tier-targets/--band-half-width/--suite-id) | `d7231619d12dd5536c7fd819fc15c9c4b95391dd56b64b73926d553871211b61` |
| campaign driver `run-20260822-qwen38-mtp5-q64k32-longkv3-abba.sh` | `74b678ed5fd29a1288b91e180128091af328ff4698b3539dd1833886a08d7bcc` |
| sealed runner `run-arm.sh` (admits the longkv3 suite id literal; no other change) | `3e263fa99f53a04dfbb8e24cb1e1de4baec33f37cd6d27cb2b9c95132341bb0f` |

Deployed suite:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-longkv3-q64k32-suite-20260822/validation-suite.json`.
Arm roots `qwen38-q64k32-longkv3-{a1,b1,b2,a2}-20260822`, all fresh.
Stage/cache/model/quality/target pins unchanged from longkv2.

## Addendum — pre-root flag-identity refusal and the scratch pin

The first a1 invocation was refused pre-root (rc=2, no arm root
created, no GPU work) by the sealed flag-identity gate, which hardcoded
`GDN_SPEC_PERSISTENT_SCRATCH=1`. Rather than loosening the gate, the
flag became an explicit campaign pin:
`VALIDATION_EXPECT_GDN_SPEC_PERSISTENT_SCRATCH` (allowlisted, must be
0/1, defaults to 1 so every historical campaign's identity is
preserved), and the actual flag must equal it. This driver pins 0.
Since no root existed, the a1 label is unburned and reused. Refrozen:
runner `db0f910c4a1cafa3621bbddf30179b40fa8a49892bbeff68a6c0b876fe0c42a5`,
driver `162fc6bc5177083568aad3506cafa72c0e596562eefd73acbd2e1e64d509b00c`.

## Metric and decision rule (frozen before launch; identical to longkv2)

Primary: `summary.tok_s_1_100_intervals_after_ttft` per arm; per-tier
medians report-only. Order a1 -> b1 -> b2 -> a2, predecessor-gated.
Pair effects `e1=(b1-a1)/a1`, `e2=(b2-a2)/a2`. Conjunctive PASS:

- four valid arms (sealed + longkv gates, markers 2/2/0/0 by role,
  quality battery pass on a1 and b1);
- `e1 > 0` and `e2 > 0`;
- `(e1+e2)/2 >= +1.0%`.

PASS qualifies the Q64xK32 policy as the lane's recommended
long-context serving configuration **together with scratch=0** (the
pair was measured jointly; no claim separates them), recorded in
CURRENT.md. No LocalMaxxing submission follows from this suite. Report-
only positive and negative-pair outcomes as in longkv2. Nothing may be
tuned after any observation.

## Stop and relaunch rules

Identical structure to longkv2: any gate failure stops the campaign at
that arm with its root preserved and no same-root retry;
numerical/identity-class failures close the design; infrastructure-
class failures permit at most one full relaunch as longkv4 after
documented cause. A scratch=0 corruption signature at dose 25 (needle
degeneration in a1's battery) is a **finding, not an infrastructure
failure**: it closes this design and routes back to the corruption
investigation with the dose bound tightened.

## Result — CLOSED at a1 (2026-08-22): 31/32 repeat divergence

a1 ran to completion with a perfect bench (25/25 rows, all gates,
cached 0, conventional suite median **85.63 tok/s** at KV ~1300-1610 —
the first complete incumbent long-KV baseline, under scratch=0) and a
**passing needle at dose 25** (the mitigation scales to 25 multi-chunk
rows). But the quality battery's 32x same-boot repeat-stability probe
failed **31/32**: repeat #1 emitted `blue,green,red` (6 tokens) against
31 identical `blue, green, red, yellow` (8 tokens). Under the frozen
rule this is a numerical-class stop: **longkv3 is closed**; root
preserved; no candidate ran; no A-B evidence exists.

Unified mechanism theory (now with two presentations of one bug): some
GDN spec-decode scratch field is **read before it is written** in a
code path exercised after multi-chunk prefills. With the persistent
pool (scratch=1), stale poison accumulates deterministically across
requests — the dose-dependent needle kill. With per-call allocation
(scratch=0), buffers usually recycle clean but occasionally land on
memory churned by 1024-token chunk tensors — the rare transient
divergence, observed at the first probe after the long-row bench.
Neither environment is quality-clean for long-context serving; the env
door mitigates the persistent presentation only.

Consequence: **the critical path to any long-KV campaign is a C++ fix**
in the GDN spec path, not another environment permutation. Bounded
source audit so far: `select_accepted_state_indices`,
`select_state_column`, and `copy_conv_base` write unconditionally
(clean); remaining suspects are the fixed-shape (graph-captured,
6-token) gather/recurrent/store kernels reading tail rows or fields the
gathers conditionally skip. Next preregistered step: a poison-fill
instrumented debug build (never deployable) that fills every spec
scratch buffer with NaN/sentinel per call in both branches — the
write-before-read contract test — then bisects the violating field via
chunkdiag-style arms.

## What this campaign cannot show

One lever, one suite, KV 1.23-1.6k, MTP5, GPUs 2,3, scratch=0
environment. Absolute rates are not comparable to the short-suite ~101.9
anchor (different workload) nor to longkv-family rates under scratch=1.
