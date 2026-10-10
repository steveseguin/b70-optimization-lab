# MiniMax-H3 publication evidence — 2026-10-10

## Decision supported by the evidence

**No publishable lossless H3 headline exists today under the current rules.**
A substantial measured improvement is recorded: **800.8 → 396.625 seconds per
clip**, approximately **2.02× throughput / 50.47% less elapsed time per clip**.
The optimized result is one eight-clip batch at the base schedule; the baseline
is an older standalone-run figure. It is a historical workflow comparison,
not an isolated kernel A/B or matched fresh-process speed certification.

The lane ledger calls the optimization exact against its local reference. That
is meaningful evidence of scheduling work, but the target itself is pruned BF16
with an INT8 encoder. The [AdaLN study](../notes/2026-09-17-adaln-table-exactness.md)
establishes that pruning is approximate. Its old phrase “in practice lossless”
is not the owner's bit-equality definition. No official full-model equality gate
or owner publication acceptance was found. The current all-lanes rule forbids a
pruned-model headline.

**Does “confirmed significant improvement” exist per the lane decision? The
publication gate is not established.** A large observed gain exists; “significant”
has no registered numeric threshold, the owner has not accepted this publication,
and matched repeat/source closure is incomplete. This audit neither discards the
2.02× observation nor substitutes its judgement for the owner's review.

## Primary number and exact receipt paths

All paths below are relative to this draft directory unless written as historical
host locations. [evidence-audit.json](evidence-audit.json) hashes every tracked
lane input at audit commit `f88313e655f53fb6f10d2610cd43113baabf71aa`, parses all
45 lane JSON files and records the comparisons actually performed on CPU. It is
an audit of retained receipts, not a new GPU measurement or promotion attestation.

| Claim | Receipt / field | Scope |
| --- | --- | --- |
| 3173 seconds, 8 clips, exit 0 | [Soak session](../data/2026-10-04-soak8/session.log), first line | Whole batch, wall rounded to seconds; log's `per clip=396` is integer-truncated |
| 396.625 s/clip, displayed 396.6 | `3173 / 8` | Derived arithmetic mean per batch, not a median or single-request latency |
| 124 frames, 960×544, 24 fps; 32,000 Hz, 2 channels, 165600 samples | Each soak receipt: `resolved`, `settings`, `seed`, `batch` | Video duration `124/24 = 5.166666… s`; waveform duration `165600/32000 = 5.175 s` |
| 0.312638 generated fps (0.313 rounded); 76.7661 elapsed s/video s | `8*124/3173`; `(3173/8)/(124/24)` | Includes batch loading/tail; playback fps is a different quantity |
| 800.8 s/clip, repeat a/b exact | [Baseline ledger](../notes/2026-09-20-realtime-goal.md), Baseline; [older draft](../notes/2026-09-20-publication-draft.md), Gates | `repeat-20260920T023257Z-a/b`; raw receipts/logs absent from Git; original timer precision/boundary not independently recovered |
| 2.019036× (2.02×); 50.4714% reduction | `800.8 / (3173/8)`; `100*(1-(3173/8)/800.8)` | Historical comparison only; no invented run or confidence interval |
| 32 MATCH, 0 DIFFERS, 8 repeat passes | [Soak session](../data/2026-10-04-soak8/session.log), lines 2–4 | Reported against September soak `duet-20260920T064019Z`; older reference receipts missing from Git |
| Video decode 52.413 s first; 41.042–41.113 s later | Each soak receipt's `timings_seconds[decode.video.i]` | Per-clip decode phase, not full generation; exact list below |
| Lowest available host memory 5643 MiB; 0 fault lines; 0 H3 shared-memory leftovers | [Soak session](../data/2026-10-04-soak8/session.log) | Recorded 90-minute fault-query window; not a present-day health check or host-memory peak |
| 11264 MiB preflight / 2048 MiB watchdog floor | [smoke wrapper](../scripts/smoke_h3.sh), `MIN_HOST_AVAIL_MIB`, `WATCHDOG_MIN_AVAIL_MIB` | Configured safety thresholds, not benchmark measurements |

Soak receipts and video decode times, all from `duet-20261004T042838Z`:

| Clip | Receipt | Decode seconds |
| --- | --- | ---: |
| 00 | [clip-00-receipt.json](../data/2026-10-04-soak8/clip-00-receipt.json) | 52.413 |
| 01 | [clip-01-receipt.json](../data/2026-10-04-soak8/clip-01-receipt.json) | 41.073 |
| 02 | [clip-02-receipt.json](../data/2026-10-04-soak8/clip-02-receipt.json) | 41.065 |
| 03 | [clip-03-receipt.json](../data/2026-10-04-soak8/clip-03-receipt.json) | 41.042 |
| 04 | [clip-04-receipt.json](../data/2026-10-04-soak8/clip-04-receipt.json) | 41.070 |
| 05 | [clip-05-receipt.json](../data/2026-10-04-soak8/clip-05-receipt.json) | 41.093 |
| 06 | [clip-06-receipt.json](../data/2026-10-04-soak8/clip-06-receipt.json) | 41.113 |
| 07 | [clip-07-receipt.json](../data/2026-10-04-soak8/clip-07-receipt.json) | 41.042 |

The [eight prompts](../notes/h3-soak8-prompts.txt) match these receipts in order.
Every clip uses seed 42; it is not seed 42 plus the clip index. All receipts
record 51 grid points / 50 NFE, pruned denoiser, no LoRA, FP32 decode and split 25.
The file's SHA256 and each receipt's full SHA256 are in the audit inventory.

**Do not use `seconds_per_second_of_video` from the duet receipts.** It is
computed from timers that overlap and accumulate across clips. For example,
clip 00 stores 4271.269 there; that is not the session's elapsed/video ratio.
`sample.0` is 2771.623 seconds while the other seven sampling timers overlap it.
Summing them would count simultaneous work repeatedly. The batch log, not that
field or a sum of phase timers, is the retained 3173-second source.

## Base schedule and optimization history

This table preserves the ledger's progression without promoting missing raw
receipts. Every row is 960×544, 124 frames, base 50 NFE and FP32 decode unless
explicitly excluded below. [Source: realtime ledger](../notes/2026-09-20-realtime-goal.md).

| Run / change | Recorded wall result | Evidence strength |
| --- | --- | --- |
| `repeat-20260920T023257Z-a/b`, standalone | 800.8 s/clip | Ledger says both runs matched all four hashes; original pair absent |
| `duet-20260920T042549Z`, overlapped sampling | 930 s / 2 = 465 s/clip | Ledger, exact-output report; raw pair absent |
| `duet-20260920T052148Z`, add two-process decode | 881 s / 2 = 440.5 s/clip | Ledger, exact-output report; raw pair absent |
| `duet-20260920T054351Z`, four clips | 1717 s / 4 = 429.25 s/clip | Ledger displays 429; not an independent eight-clip repeat |
| `duet-20260920T061643Z`, split 25 | 853 s / 2 = 426.5 s/clip | Ledger, clip-00 equality report; raw pair absent |
| `duet-20260920T064019Z`, eight-clip reference | 3281 s / 8 = 410.125 s/clip | Ledger displays 410; eight original reference receipts absent |
| `duet-20261004T042838Z`, persistent decode + audio overlap | 3173 s / 8 = 396.625 s/clip | Eight current receipts and short session log retained; best recorded base-schedule batch |
| `duet-20261004T160259Z`, piecewise transfer change | No retained complete eight-clip wall time | Two-clip exactness gate only; do not assign the soak speed to this later source |

The improvement between the two recorded eight-clip totals is
`3281/3173 = 1.03404×`, or **3.29% less elapsed time**, rather than a new 2× gain
from the persistent decoder alone. The 2.02× comparison includes batching,
overlapped sampling and multi-process decode relative to standalone execution.
There is only one retained batch at the exact best-speed configuration; p10,
median clip latency, fresh-run dispersion and confidence intervals are not available.

Historical original locations to recover on the two-card host (not accessed in
this task): `/mnt/fast-ai/bench-results/minimax-h3/`, with
`repeat-20260920T023257Z-a/receipt.json`,
`repeat-20260920T023257Z-b/receipt.json`, and
`duet-20260920T064019Z/clip-00/receipt.json` through `clip-07/receipt.json`.
Names alone are not public evidence. Recover full source/run logs and timestamps
with these receipts, or perform newly authorized matched measurements.

## Exactness checks independently recomputed from retained receipts

The CPU audit compared stored digest strings; it did not rehash raw video,
waveforms or latent tensors, which are absent here.

- [Piecewise gate clip 00](../data/2026-10-04-piecewise-transfers/gate2-clip-00-receipt.json)
  against [soak clip 00](../data/2026-10-04-soak8/clip-00-receipt.json), and
  [piecewise gate clip 01](../data/2026-10-04-piecewise-transfers/gate2-clip-01-receipt.json)
  against [soak clip 01](../data/2026-10-04-soak8/clip-01-receipt.json):
  **8/8 tensor hashes and 2/2 MP4 hashes match**, same prompts, seed and 50 NFE.
  [Successful comparison log](../data/2026-10-04-piecewise-transfers/piecewise-gate2-20261004-summary.txt).
  The [first attempt](../data/2026-10-04-piecewise-transfers/piecewise-gate-20261004-summary.txt)
  failed the comparison because absolute reference paths were incorrectly joined
  to `OUT_ROOT`; it is not silently counted as a pass.
- Three runs `duet-20261004T034605Z`, `...035024Z`, `...035545Z`, each with two
  clips, have matching tensor and MP4 hashes per clip. All six
  [receipts](../data/2026-10-03-gates/determinism/) and their individual paths
  are indexed in the audit. **These are 8-NFE runs**, not the 50-NFE soak.
  Older narrative calls them turbo, but receipts say `lora:null`, and the current
  duet entrypoint rejects LoRA. Treat that as an unresolved identity discrepancy;
  neither those repeats nor their speed can certify the base schedule.
- [October 3 base gate](../data/2026-10-03-gates/receipts/duet-20261003T224727Z/clip-00-receipt.json)
  has the same four hashes as soak clip 00. The full run
  [failed](../data/2026-10-03-gates/run1/session.log) on clip 1 during the
  shared-file cleanup race. It is not a completed fresh repeat. The ledger's
  40.8-second decoder claim is not the receipt's `decode.video.0=52.734`;
  retain that distinction instead of mixing timer scopes.

The [piecewise-transfer note](../notes/2026-10-04-piecewise-transfers.md) and
[allocation probe](../data/2026-10-04-piecewise-transfers/size-probe-h3-venv.txt)
explain a 128 MiB transfer chunk change. Commit
`52c802a4fa7f0a351b155fb21c5f3df8f213f265` is its evidence/source anchor.
The earlier soak anchor is `34ec68887431c9d64a5688aa35a5e220ddaa5e69`.
No result-critical full source hash or immutable wheel identity is carried by
the original soak receipt; Git chronology alone cannot prove a clean runtime.

## Excluded speed/quality evidence

| Evidence | What it proves / why it cannot replace the best base-schedule result |
| --- | --- |
| [September first light](../data/2026-09-19-first-light/), [canvas ladder](../data/2026-09-19-canvas-ladder/) | Completed clips and repeat work at 8 NFE with LoRA; different schedule/target path |
| [September decode experiments](../data/2026-09-19-decode-experiments/) | Threaded two-card decode: 78.274 vs 79.308 s control; single-card FP16: 15.929 and 15.339 s; phase-only, same saved latents, lossy pixels |
| [FP16 difference receipt](../data/2026-09-19-decode-experiments/vs-control-fp16-a-20260919T233947Z.json) | Video differences; cannot describe half-precision decode as lossless |
| [October gate B, run 2](../data/2026-10-03-gates/run2/gateB.json) | False assurance: FP16 flag was ignored by workers; not a genuine FP16 pass |
| [October gate B, corrected run 3](../data/2026-10-03-gates/run3/gateB.json) | `pass=false`: actual two-process FP16 changes video across repeats; measured later-clip decode 8.996 / 9.010 s in the linked run receipts |
| [Single-card FP16 repeats](../data/2026-10-03-gates/fp16-single-repeat/) | 15.279 / 15.320 s decode; repeatable within that path, not equal to FP32 |
| [MP4 comparison reports](../data/2026-10-03-gates/) | Earlier compressed-file differences include nondeterministic encoding, so these are not substitutes for tensor equality |
| [Live-loop script](../scripts/h3_live_loop.sh), [stream sink](../scripts/h3_stream.py) | Playback/relay implementation, not measured real-time generation, continuation quality or sustained uptime |

The old notes contain estimates from FLOPs and substituted phase timings. None
is carried into a headline or graph here. The fastest lossy row is irrelevant
to a lossless publication decision. No reduced step count, cached embedding,
compressed cache or stored-output replay is adopted by this draft.

## Input, runtime and license provenance

[Lane README](../README.md), [disk audit](../notes/2026-09-18-disk-audit.md),
[stand-up record](../notes/2026-09-18-standup-prep.md),
[step/scheduler record](../notes/2026-09-18-steps-and-lora.md),
[environment.txt](../data/environment.txt) and each soak receipt support the
identity table in the draft guide. Model sizes in the old audit are size checks,
not full-file hashes. The rotation digest is full-file; the denoiser digest is
header-only; the encoder and VAEs lack complete retained hash bindings.

Metadata-only API reads on 2026-10-10 returned:

| Repository | Full revision | API lastModified | Interpretation |
| --- | --- | --- | --- |
| [Official MiniMaxAI](https://huggingface.co/api/models/MiniMaxAI/MiniMax-H3) | `42ed227ee7df40d41602854ae760620d6eb651fe` | 2026-08-13T01:46:29Z | Review-time official source candidate; not bound to historical bytes |
| [Comfy-Org](https://huggingface.co/api/models/Comfy-Org/MiniMax-H3) | `e5eb578a89295337b8ff433a035929ce0279e0b6` | 2026-09-29T11:11:09Z | Review-time derived-weight source; not a run pin or permission to download |

The official model card identifies the MiniMax-H3 Community License. The owner
must review the [license at the observed revision](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/LICENSE)
and derived-weight/runtime terms before choosing download-only instructions or
redistribution. No legal clearance or permission is inferred from a public URL.

## Coverage and remaining evidence

This audit covered the full tracked lane inventory: README, all dated notes,
prompt lists, JSON receipts, text/log evidence and the runtime/wrapper sources.
There is no lane `HANDOFF.md`, `DO-NOT-REPEAT.md` or `results/` directory. The
README, realtime ledger, [CURRENT.md](../../../CURRENT.md) H3 entries and
historical notes provide the handoff. No H3 promoted row exists in
[scoreboard](../../../results/scoreboard.md). MiniMax M2.7 rows are unrelated.
The existing complete [LTX repro guide](../../../repro/ltx25-continuation-stream-b70-145f-20261010/README.md)
was the video schema example, not a source of H3 numbers or quality acceptance.

To close publication: recover missing originals, bind every weight/runtime/source,
register a matched full-suite baseline/candidate repeat policy, obtain human
video/audio quality review, and write a video-specific hash-bound attestation.
LLM arithmetic/JSON/token-suite booleans do not apply automatically. Unsupported
oracle, fresh-repeat, unchanged-official-target and no-quality-loss gates remain
false; `featured_metric` stays null. See [owner review](OWNER-REVIEW.md).

## Validation

[validation.json](validation.json) records the CPU commands, exit codes and
scratch results. A structural guide-catalog pass is not a recipe-publication
certificate. The missing publication manifest, release assets and quality
closure remain explicit failures/gaps. No model test or site generation ran.
