# The divergence does not reproduce through the offline API

Five configurations, none of which reproduce it, and three design flaws found in the probe along the
way. The negative is worth more than it looks: it moves the phenomenon out of the model's arithmetic
and into the serving path.

## What was tried, all at TP2 against a strictly single-row oracle

| configuration | result |
| --- | --- |
| 64 identical prompts, lockstep, eager | 64/64 match the oracle |
| same, with `FULL_DECODE_ONLY` graph capture at sizes 1-64 | 64/64 |
| unequal generation caps so half the batch retires mid-window | 32/32 |
| the twelve fragile prompts that carry every ladder divergence | 64/64 |
| those prompts with the ladder's own scheduling (`max_num_batched_tokens=512`, `max_model_len=256`), which forces chunked prefill interleaved with decode | 64/64 |

The same twelve prompts diverge from their oracle at about `1.7%` of requests when the ladder drives
them through `vllm serve`. Through the in-process `LLM` API they never do.

## Three flaws in the probe, each of which produced a clean and meaningless pass

Worth recording, because each looked like a result:

- **Comparing a constant-composition window.** The first drift attempt spread generation caps from 32
  to 128 and compared the first 32 tokens - exactly the phase in which all 64 requests are still
  running, so the composition was constant across the entire comparison. Fixed by retiring half the
  batch at token 8.
- **A twelve-row oracle.** Generating all twelve reference outputs in one call makes the oracle a
  12-row batch, not the single row the identity ladders compare against. Any effect needing more than
  twelve rows would have been invisible. Fixed by generating them one at a time.
- **A generic prompt.** A prompt with no near-tie cannot show this however the batch is composed. The
  first runs used one, which made them a control rather than a test.

## What is left

The remaining difference is the serving path itself. The ladder issues requests over HTTP to a
running server, so they are admitted asynchronously and the batch grows from one to sixty-four while
the earliest requests are already decoding. The offline API submits everything at once; the batch is
assembled once and only shrinks.

That is a real difference in composition dynamics and it is the only one left standing. It also fits
the shape of everything else found: the ops are individually row-count dependent, a fixed batch is
nonetheless deterministic, and only a batch whose composition changes underneath a request produces
divergence.

## What to do next

Reproduce it against the server, not the offline API - the ladder already does, so the cheap version
is to instrument that path rather than rebuild it. The layer hook works in eager mode and the strict
launcher can run eager, so a server arm with the hook enabled and the fragile suite would put a real
divergence next to per-layer digests for the first time.

Evidence: probe `probes/drift-reproduction.py`.

## Amendment 2026-09-09: a fourth flaw, and the rerun that never happened

The five configurations above generated 128 tokens and compared the first 64. In the ladder data 78% of
divergences first appear at position 64 or later and the median first difference is at token 90, so the
comparison window excluded most of the effect it was looking for. This is the same class of mistake as
the constant-composition window in the first flaw, found the same morning; the probe's `COMPARE` now
defaults to the full generation and warns when it is shorter than `CAP_MAX`.

The full-window rerun (`scripts/run-20260908-drift-reproduction.sh`, 2026-09-08 14:07 UTC) did not
complete: the TP2 worker failed in oneCCL with `opendir failed: could not open device directory`, because
the runner set none of the oneCCL transport environment the strict launchers set
(`CCL_ZE_IPC_EXCHANGE=pidfd` and the rest), and the lockstep control was cut off during weight loading.
The runner now carries those lines and is queued behind the 4B row-chunk chain.

Until it reports, the headline of this note is **weaker than written**: the offline API has not been
shown to reproduce the divergence, but it has not been given a fair chance to either. The serving-path
conclusion in "What is left" stands on the 4B lane's staggered-admission result, which is independent of
this probe, and not on the five nulls above.

## Amendment 2026-09-11: the queued rerun did not report either

The runner started at 20:43 on 2026-09-09. The lockstep control failed at engine start (a WorkerProc
initialisation error; the root cause line is not in the retained tail). The drift arm then began loading
with `Available RAM: 1.17 GiB` against a 10.65 GiB checkpoint, wrote nothing for thirty-two hours, and
exited at 05:12 on 2026-09-11, holding the queue behind it for that whole time. The runner has no memory
guard - the campaign engine's `LOAD_MEMORY_MIB` wait exists for exactly this - and its `| tee | tail`
masks the exit code. This probe has now failed to complete four times for four different reasons; the
headline of this note remains unproven and the offline route is not cheap. The 4B lane's serving-path
findings (staggered admission; the R224/R290 FP16 linear work) stand on their own evidence.
