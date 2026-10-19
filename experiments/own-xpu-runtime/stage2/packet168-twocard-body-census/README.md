# Packet168: partial two-card body census (packet168b)

**v3 (current).** The B-v2 run failed because of a control-pass sticky error.
The probe ran at the unadmitted position 128 (benchmark-analysis) against a
qsa launch extent of 128. v3 makes two changes. First, `probe()` admits the
device position before its passes. Second, attention has no arm and is part of
the residual. Five classes are measured. The jobs are
`packet168-body-census-{B,A}-v3`. The six-class text below is the historical
v2 design. See `DO-NOT-REPEAT.md` and `lineage/v2-root-cause/`.

This is a diagnostic census of the bundle-8 two-card record line
(packet136, 58.798108759182306 tok/s, `iq3-p49-split32-v1`). It runs in one
load on lane B (cards 2 and 3); the lane-A twin is an alternative, not a second
load. **Its arms are never reported as speed.** `READY-FOR-DEVICE.json` gives the
final gate state, and `evidence/final-audit.json` lists each gate.

## What the coordinator decided (packet168b)

These six classes are measured. Each is skipped in an isolated body probe with
exact snapshot repair:

| Class | Native `classify()` code | Launches |
|---|---|---|
| attention | 1 | `qsa_*` |
| gdn | 2 | `gdn`, `conv`, `gdn_norm_gate` |
| router_shared_expert | 3 | route + shared activation, shared-down + mixture (**one fused class**; the fused launches are never split) |
| routed_experts | 4 | `expert_gate_up`, `routed_gemv`, `expert_gather` |
| dense_hc | 6 | remaining GEMV / HC stages |
| norms_glue | 7 | stage-0 norms and glue |

The cross-card transfer (`handoff*`) and the split head (`logits`, `argmax`)
have no skip arm. They are reported only as the **residual**:
exact native control ms/token minus the sum of the six class marginals. The
residual also absorbs controller/mailbox time, overlap and any difference in
passes per token. It is never called causally isolated, and negative values are
kept.

## The device sequence (`census_worker.py`)

The run uses one load of the unchanged packet136 engine. The only change is the
`--census-probe` flag, which enables native command 20 and gives rank 1 a
snapshot image.

1. A distinct, excluded warm-up runs first. It uses the 512-token prefill
   prompt, which is not one of the 12 census prompts.
2. The views run in the order C0, attention, gdn, routed_experts, C1,
   router_shared_expert, dense_hc, norms_glue, C2. Each view covers all
   12 prompts.
3. Every request starts with a complete native reset and decodes 64 tokens. The
   tokens must equal the oracle prefix in-run.
4. In a class view, the native rank runs command 20 on both ranks after the
   prompt's exact setup request. Each call does three repeats of the following:
   snapshot, then a control pass, restore, an arm pass with the class skipped,
   restore, a repair pass, and restore. The repaired bytes must equal the
   control bytes, and each restore must equal the pre-probe image. Otherwise the
   rank stops. No probe token is published.
5. Arm passes can change expert identities, because the router sees different
   inputs. The expert count and shapes stay fixed. Such changes are recorded
   (`route_identity_preserved`) and not hidden.

`analyze.py` (schema `packet168.census.v2`) refuses each of the following:

* a missing view, prompt, rank or repeat;
* changed chronology;
* a control or setup request that is not exact;
* a failed restore or repair;
* an empty class mask or partial class coverage;
* a published probe token;
* control-view mean drift above 1%.

The largest per-prompt drift is reported for information only. Each class
marginal is the median over prompts of (rank0 + rank1) median(control − arm),
in ms per isolated body pass. The top two classes also get 30% and 50%
conditional ceilings, which are sensitivities and not measured speed.

## CPU qualification (no GPU, no model payload)

* `build_engine.py`: the private SYCL entry, which reuses the parent kernel
  objects (compile turn).
* `prepare_cpu.py` and `run_cpu.py`: the native fixture on both ranks. It runs
  the registered order × 12 prompts × 3 repeats (324 probe rows per rank) with
  real snapshot byte copies and real host-memory sensors. Compute is
  marker-only, so the fixture proves the lifecycle, not arithmetic. It also
  dumps the production-arena census.
* `package.py`: writes `memory-plan-census.json`. This is the parent plan plus
  the measured rank-1 snapshot backing. The fixture's rank-0 image equals the
  real device rank-0 image from packet165's
  `device-warm512-B-a`, byte for byte. Parent margin rules still apply. The
  script also writes the budget, the identity, the v2 proposals and the seal.
* `worker_gate.py`: drives the real worker, `suite.reset`, NativeController and
  analyzer over a host transport. That transport replays the real native
  fixture probe rows, and the gate checks that a wrong token or a failed
  repair is refused.
* `test_analyze.py`, `replay_parent.py` (60 real parent streams; packet136
  reproduces 58.798109), `report_adapter.py`, `launch_checks.py` (every worker
  rank flag checked against the built `--help`; device-path imports, oracle
  binding and census memory plan checked under the real A/B environment) and
  `check_packaging.py` (`lanequeue plan` on temporary copies; shared
  rehearsal receipts).
* `finalize.py`: checks every gate and writes READY **last**.

There is no optional smoke. The single load opens with the excluded warm-up and
the exact C0 control on all 12 prompts. Chain-only K1a/K1b windows do not apply
to this one-window screen.

The [work note](../../../../notes/2026-10-19-own-runtime-packet168.md),
[retention](RETENTION.md) and [packet168 original receipts](evidence/packet168-original.json)
have more detail.
