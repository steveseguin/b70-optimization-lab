# Audit of the September 15–16 LTX claims, and the corrections that follow

*2026-09-16, evening. Written after the host reboot at 13:23 EDT. No GPU work
was run for this audit; every check below is offline against evidence already
on disk. Receipts: [`data/pipeline-audit-01/`](../data/pipeline-audit-01/).*

## Summary

| Claim (notes, Sep 15–16) | Verdict | Evidence |
| --- | --- | --- |
| Graph-captured blocks + graph-captured text encoder are bytewise exact | **Holds** for the boat fixture | 452 saved clips hash-compared against `baseline-01`; every clip that should match does, and every non-boat fixture differs (as it must). Full comparator passes on all 19 oracle-gated Sep 16 clips (`g41`…`g55`). |
| Serial steady-state interval ≈ 4.6–4.7 s | **Holds** | Reconstructed from receipt timestamps: 4.57–4.65 s in packets 39/41/42/43/48. |
| Three-stage pipeline (encode-ahead + decode-behind) ≈ 2.56 s per clip | **Holds as a number, with two scope defects** | 2.570 s (packet 48), 2.572 s (packet 47). Defects below. |
| "Encode-ahead is not a cache; every clip computes its own conditioning" | **Misleading** | The worker pre-encodes *this prompt's text* for the next clip index and never checks the next prompt's text. Correct only while the prompt is constant; a changed prompt would silently get the previous prompt's conditioning. In the constant-prompt harness the values are identical, so the oracle cannot see it. |
| Pipelined sampler (two clips sampling at once) | **Regression, unreported** | Packet 55: crashed at prompt 7 on the shared `current_patcher`; the six clips before it were exact, but the steady-state tail ran **3.26–4.01 s** per clip, slower than the 2.57 s three-stage pipe. The pin fix was committed untested; the relaunch (packet 56) coincided with a silent host lockup at 13:20 EDT. |
| Text encoder fp32 is irreducible without lowering precision | **Holds** | `comfy/sd1_clip.py:279` passes `dtype=torch.float32` to every LLM text encoder on every platform, so fp32 activations are the upstream reference, not an XPU artefact. |
| Every fps figure is "new video" | **Overstated** | Every throughput prompt used the boat prompt and seed 42. The clips are identical by construction. Throughput of identical clips is a valid compute-rate measurement, but it does not demonstrate a stream of *new* video, and it blinds the oracle to stale-delivery bugs. |
| Receipts | **Not committed** | Nothing under `data/` is newer than Sep 15 13:05. The throughput driver's JSON outputs are not on disk anywhere. The per-node gate receipts in the server run directories and the saved tensors are what survive; this audit reconstructs from those. |

The headline that stands: **2.57 s of wall time per 1.042 s clip, identical
clips, bytewise exact on the boat fixture, on one server, measured once.** That
is 0.41 s of video per second, about 9.7 fps equivalent, against a goal of 24.

## What the identical-fixture harness cannot see

Two races become invisible when every prompt has the same text and seed:

1. **Stale conditioning.** `ltx_pipeline.run_ahead` submits the *current*
   closure (current `text`) for indices `index+1..index+depth`. With a changed
   prompt the next clip would be sampled from the wrong conditioning and still
   pass the oracle, because the oracle for that harness is the same clip.
2. **Global CPU RNG.** `comfy.sample.prepare_noise` calls
   `torch.manual_seed(seed)` and then `torch.randn` on the global CPU
   generator. Two sampler worker threads interleaving seed/draw would swap
   noise between clips. With equal seeds the swap is a no-op; with distinct
   seeds it corrupts a clip. (The ancestral per-step noise uses a per-call
   `torch.Generator` on the device and is thread-safe.)

Opus recorded caveat (1) in
[throughput-is-the-goal-metric](throughput-is-the-goal-metric.md) and then
did not act on it; (2) was not identified.

## Pipeline fill accounting

With `pipe-samp` (sampler depth 2 + decode depth 1) the first three prompts all
emit clip 0 (`emitted_index: 0` in `g55-s0/s1/s2`). The driver's mean drops only
the first interval, so the fill's near-zero intervals (0.29 s, 1.01 s in `tya`)
deflate the reported mean. Steady-state throughput must be computed over
distinct emitted clips only.

## The corrections in this packet

1. **Encode-ahead binds to the real next prompt.** The worker looks the next
   prompt up in ComfyUI's own queue (`PromptServer.instance.prompt_queue`), reads
   that prompt's `LTXPipelineTextEncode.text`, and encodes *that*. Each job
   carries the SHA-256 of the text it encoded; `collect` refuses a job whose
   text differs from the collecting prompt's text and encodes inline instead,
   recording `speculation_miss`. If the next prompt is not queued yet, nothing
   runs ahead. Receipts record `text_sha256`, `lookahead`, and the miss flag.
2. **Noise generation is serialised.** The pipelined sampler wraps each
   `Noise` object so `generate_noise` runs under one process-wide lock; seed
   and draw can no longer interleave across threads. Bit-identical by
   construction (same generator sequence, just not interleaved).
3. **Ten-fixture throughput driver** (`scripts/run-throughput-fixtures.py`):
   cycles the ten stability-01 fixtures (distinct prompt and seed), records
   per-prompt history/submission/result/prompt/identity exactly as
   `profile-clip.py` does, maps each prompt to the clip it *emitted* via the
   decode receipt's `emitted_index`, runs `compare-clip.py` on every emitted
   clip against that fixture's own reference, and reports the interval over
   distinct emitted clips only.
4. **Receipts go into Git** under `data/`, per the lane's evidence rule.

The pipelined sampler is kept as an arm for one measured comparison with the
races closed, but it is not the direction: its own evidence says it lost.

## Host state

Previous boot ended silently at 13:20:15 EDT with no kernel fault line, two
minutes into packet 56's start (its receipts are zero-byte files, created but
never flushed). That matches the lockup class recorded on Sep 15
([xe-lockup-incident-01](xe-lockup-incident-01.md)): a hard lockup, no
pstore. The host was rebooted at 13:23 EDT (not by this session). No LTX
server has run since; `FAULT.json` is absent; the four cards enumerate.
