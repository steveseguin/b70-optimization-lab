# Packet 118 independent prelaunch review — BLOCK

CPU-only review of sealed manifest `cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6`.
No device work, model server, host changes or writes under `/mnt/fast-ai` or `reopen-20261008/runs/`.
The host fault halt remains binding independently of this verdict. Packet 118 must not launch.
Fixes below are an **unapplied author-source patch**, requiring a separately identified **118b rebuild**;
they neither repair nor authorize the sealed 118 packet. No GPU experiment is proposed here.

Evidence notation: `R/` = `experiments/ltx25-b70/recovery/20261009-continuation118-stream/`;
`S/` = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118/`;
`C/` = `experiments/ltx25-b70/stream/`. Lines refer to the reviewed, unmodified sources.

## Findings, highest severity first

1. **P1 BLOCK — decode-thread dual policy follows the wrong chunk.**
   `R/snapshot_fingerprint.py:211` resets `chunk_dual` and `near_floor` for the prompt thread;
   the concurrent P7 callback reads those same fields at `:347`. Chunk 20's stage-B precompute follows
   the successor's sampler start (`R/integration.py:575`), so `begin_request(21)` can suppress its required walk.
   CPU reproduction: begin 20, begin 21, invoke P7 with ample free memory: zero dual checks.
   P7 also rereads free memory separately for each role, ignoring P5's actual reading
   (`R/precompute_guard.py:109`, `R/snapshot_fingerprint.py:348`), and never makes its near-floor result sticky.
   A near/high/high sequence dual-checks only one of three roles; exactly 0.5 GiB is excluded (`:259`).
   Minimal conservative repair: always dual-check decode-thread P7, propagate the actual P5 reading,
   use an inclusive boundary, and preserve near-floor status from either four-card reading.

2. **P1 BLOCK — the advertised dual proof omits memory admission verdicts.**
   `R/snapshot_fingerprint.py:51` excludes free memory and allocator validity from `VERDICT_KEYS`;
   `:321` compares these selected fields and `:326` returns only the walk to the controller.
   CPU reproduction: fingerprint reports xpu:3 free = 0, walk reports healthy memory: controller admits,
   `agreements` increments, and no snapshot latch is written. Normal fingerprint-only snapshots DO retain
   the sealed floor checks; the defect is the claimed proof/latch coverage, not wholesale removal of floors.
   Repair: compare each sample's floor/counter **verdict** using that site's before/after floors, not raw
   byte counts from sequential readings. A disagreement must write the snapshot latch and raise.

3. **P1 BLOCK for off-mode control — `CAP=-` does not clear an inherited cap.**
   `R/launch-118.sh:31` only adds an explicit cap; `:36` inherits the caller's environment and `:41`
   inherits the unit environment. Thus the documented uncapped walk control can still be capped.
   A harmless env-child reproduction retained `1.0` with `CAP=-`. Repair both env commands with
   `-u LTX_DECODER_GRAPH_POOL_CAP_GB` before explicit assignments. Also reject unknown mode arguments:
   a misspelled tenth argument currently falls through to launch (`:6`, `:34`).

4. **P2 — timing is instrumentation, but not zero-cost or a literal 117 path.**
   New `health_lock` acquisitions occur twice per healthy call (`R/session.py:234`, `:244`), plus route
   locks (`R/integration.py:325`), dictionaries/timestamps, receipt JSON and validation. The receipt route
   adds a filesystem stat (`:2199`). There is no new tensor arithmetic/allocation, device synchronization,
   device-to-host tensor read or reordered model call attributable to timing alone. CPU locking, allocations
   and file metadata reads do add latency; “<1 ms” remains an estimate, not a test result.
   `first_served` means file observed before response construction, not first completed HTTP 200 (`:2199`,
   `:2211`); files become visible before fsync completes (`R/session.py:459`). `queued` is stamped after
   handler return and can be copied before it is populated (`R/integration.py:793`, `:2142`). Split sums
   close algebraically; that alone cannot prove accurate causal buckets. Preserve missing/negative values.

## Q1: every walk fact and snapshot site

| Walk fact | Fingerprint treatment and evidence |
|---|---|
| Parameter/buffer kind, name, order, object id, storage pointer, shape, dtype, device | Same facts enumerated; capture binds them to admitted rows; deviations run the walk (`S/source/scripts/native_adapter.py:312`; `R/snapshot_fingerprint.py:68`, `:110`, `:150`). |
| Tensor bytes, integer-buffer exception | Derived from shape/dtype, hence unchanged facts imply unchanged rows (`S/source/scripts/native_adapter.py:320`; `R/snapshot_fingerprint.py:80`). |
| FP32 constructor exception/source pin | Rechecked on every snapshot; changed exception falls back (`R/snapshot_fingerprint.py:154`). |
| Stride, storage offset, tensor values | **Neither walk nor fingerprint checks these** (`S/source/scripts/native_adapter.py:329`; `R/snapshot_fingerprint.py:74`); inherited limit, not a new omission. |
| Role→card, static patcher, loaded registry and full model size | Same checks or walk fallback (`R/snapshot_fingerprint.py:147`, `:158`). |
| Sampler owners/shard registration/load devices/no patches | Fact substitution; any deviation calls sealed placement check (`R/snapshot_fingerprint.py:164`; `S/source/scripts/ltx_layer_shard.py:186`). |
| Route/dispatch identity, host identity/layout, W1/B1, text capture/window/inventory | Same `_state` call (`R/snapshot_fingerprint.py:272`; `R/candidate_safety.py:330`). |
| Phase/active request/fault/latched flags | Same phase/controller checks (`R/candidate_safety.py:197`, `:209`, `:270`). |
| Admitted role ownership, both VAE safety bindings | Same controller (`R/candidate_safety.py:219`, `:228`); P7/P8 on decode thread (`R/precompute_guard.py:118`). |
| Encoder cache, anchor bytes, input/output ownership | Same conditioning guard (`R/conditioning_guard.py:222`); precompute own/foreign cache checks remain (`R/integration.py:423`). |
| Free floors 8/8/2/9 GiB before, 2 GiB after; valid allocation counters | Same controller (`R/candidate_safety.py:231`); P5/P6 on decode thread (`R/precompute_guard.py:109`). Dual-proof omission is finding 2. |
| Four-card synchronization | Same outer four syncs (`R/candidate_safety.py:199`), plus `_free` four syncs (`S/source/scripts/native_adapter.py:341`). Dual runs add another `_free` walk: **12 vs 8 sync calls**, not identical count. P7 remains xpu:3-only. |

All six prompt sites use the installed inspector (`R/integration.py:1478`): request-before `:800`,
A-before/A-after and B-before/B-after `:915`, mixed B `:1009`, request-after `:1290`.
All qualification request snapshots are dual after ledger capture; the gate checks labels and agreement
(`R/qualification_gate.py:320`). Initial preparation before ledger binding and observation-only inspections
deliberately walk (`R/snapshot_fingerprint.py:228`); they are not dual-proof evidence.
Prompt streaming selects sequence modulo 20 and sticky near-floor (`:211`, `:237`), subject to findings above.
Precompute before/after both call Xpu3Snapshot (`R/integration.py:429`, `:446`), with P7 injected at `:1634`.
Every detected disagreement calls `snapshot-118-refused.json` via `R/snapshot_fingerprint.py:328` and
`R/integration.py:335`; decode failures exclude that disagreement from the precompute latch (`:456`).
The latch plumbing exists at every site; the missing comparisons/scheduling prevent some detections.

## Q2: exhaustive sealed 117→118 difference classification

Regular-file comparison: **1,848 identical, 26 changed, 27 added, zero deleted**. No literal whole-path identity.
CandidateSafety, conditioning_guard, native_bindings, native_adapter/native_safety, stream_decode,
stream_preview, latent_anchor and underlying sampler/decoder/encoder code are byte-identical.
`R/conditioning_guard.py:29` retains the same CandidateSafety source pin, enforced at `:58`.
Below, paired copies mean `resolution/components/<name>` and its runtime copy under `source/scripts/` or `launch/`.

| Changed files (all 26) | Classification |
|---|---|
| runtime_packet.py / launch/encoder_runtime_common.py | Parent closure, provenance, identities, grammar, options and latches (`R/runtime_packet.py:380`, `:411`, `:689`). |
| session.py / ltx_resolution_session.py; integration.py (two) | Timing/wrappers/locks plus inspector, cap and gate wiring (`R/session.py:228`; `R/integration.py:1478`). |
| stream_contract.py (two); qualification_gate.py (two); stream_receipts.py (two) | Identities, launch parsers, option/snapshot/pool gates and timing schemas (`R/qualification_gate.py:257`; `R/stream_receipts.py:411`). |
| stream_decoder_graph.py (two) | Cap entries/accounting; uncapped capture/replay retained (`R/stream_decoder_graph.py:254`). |
| stream_anchor_decode.py (two); precompute_guard.py (two) | Documentation and schema/latch 117→118 only; computation/check bodies unchanged. |
| plan.py; qualify_client.py | Identity/declarative options; expected server-option refusal. |
| launch/serve-encoder.py; source/scripts/ltx_duration_guard.py; source/scripts/ltx_output_size_98.py | Messages/comments only; prewrite schema only; plan/QID/comparison identity literals only, respectively. |
| STATUS.txt; manifest.json; resolution/stream-plan.json | Metadata/identity/closure. |

Additions: two snapshot_fingerprint.py copies, parent 117 manifest, 24 exact archived predecessor files.
Walk dispatch calls the old inspector (`R/snapshot_fingerprint.py:228`, `:261`); cone/precompute are behaviorally,
not byte-for-byte, identical modules. Timing remains on, and finding 3 must be fixed for a reliable off control.

## Q4: cap correctness and memory

No cap-dispatch blocker found. Capped methods call the original inside the existing bounded-cache scope
(`R/stream_decoder_graph.py:284`), the same cached eager method used as the capture oracle (`:325`);
cache code is unchanged (`:570`). Graph qualification still compares complete output to **uncached** eager
(`R/integration.py:596`), and every cone compares its last frame (`:614`). This retains the 116b/117 gates;
CPU evidence does not itself certify capped XPU execution.
Each signature's choice persists (`R/stream_decoder_graph.py:260`); the same instance freezes after the gate
(`R/integration.py:1777`), and new signatures refuse (`R/stream_decoder_graph.py:262`). No capture-set switch
between qualification and streaming. Fresh servers can choose differently as allocator growth differs.
The cap is a threshold for the **next** method, not a hard memory maximum (`:461`).
The 11.0–11.8 GB estimate starts from 117's observed 9.59 GB **including** the cone transient, then adds
~1.9 GB saved capture growth (`notes/2026-10-09-continuation117-results-121.md:8`;
`notes/2026-10-09-continuation118-stream-design.md:136`). It does not omit another 1.8 GB subtraction.
Allocator reuse is still unproven. 9.66 GB is the admission floor; 10.16 GB is only a falsification threshold.

## Q5: launcher/client and validation

Mode grammar maps `fingerprint→smfp`, `walk→smwalk` (`R/runtime_packet.py:42`, `:452`);
sealed launcher verifies the env-derived name (`S/launch/serve-encoder.py:230`). Latches correctly cover
116 decoder graph, 117+118 cone/precompute, 118 snapshot (`R/runtime_packet.py:433`). Collision checks use
the **results root** output/validation/requests and `stream118-` (`:459`), not the packet directory.
Parent-chain verification recursively hashes 117→…111, every 118 file, inventory and semantic closure (`:689`).
Exact `--check-only` returns before locks/device work (`S/launch/serve-encoder.py:257`); not executed under FAULT.
Client mode/cap expectations refuse at preflight; `none` means uncapped, omitted means accept admitted value
(`C/ltx_continuation_client.py:571`, `:635`). Every receipt must retain admitted options (`:1001`, `:1450`).

Independent reruns used `/home/steve/.venvs/ltx25-baseline/bin/python3 -B` (client stdlib fake HTTP only).
Packet CPU suite: **289/289 passed** in 608.025 s, no skips. Command: `-m unittest discover -s R -p 'test_*.py'`, with
`PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2` (`R` expanded as above).
Client suites `C/tests/run_tests_{112,113,114,115,116,116b,117,118}.py`: **46/46, 11/11, 25/26, 20/20,
30/30, 8/8, 21/21, 15/15** respectively (**176/177**). Only failure: historical 114 X5 still expects
“build pending” refusal (`C/tests/run_tests_114.py:346`), but client 114 is already sealed (`C/ltx_continuation_client.py:126`);
it exits 5 after its bounded HTTP wait rather than 8. No 118 client failure; all fake servers stopped.
Read-only `R/runtime_packet.py --verify-manifest-sha256 <above hash>` passed full recursive source closure.
[review-fixes.patch](../recovery/20261009-continuation118-stream/review-fixes.patch) passes `git apply --check`;
CPU `/tmp` patched-copy checks: **20 fingerprint + 10 precompute tests passed**, four Python files compile;
launcher passes `bash -n` and four isolated environment checks. Five added regression tests cover findings 1–2.
The conservative P7 repair adds CPU work. Rebuild/rehash 118b and update its claims/pins; leave sealed 118 intact.
