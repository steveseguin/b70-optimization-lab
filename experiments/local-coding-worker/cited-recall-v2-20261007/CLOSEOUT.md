# Fresh cited-recall trial: complete format, incomplete coverage

The one-shot request finished all ten answers in 176.26 seconds with a natural
stop: 10,135 input tokens, 1,643 output tokens and zero cached input tokens.
Strict reference compilation and the unchanged exact-quote validator passed.
Independent review found **12 of 30 criteria fully covered**, 15 partly covered
and three absent; no question covered all three criteria. All 20 citations were
relevant and their compiled quotations exact. No listed disqualifying false
claim was found. The full semantic gate failed.

The principal weakness is omitted conditions, not invented opposite advice.
Examples include loop-feedback evidence limits, full context/output numbers,
publication re-download checks, mount/space admission and fault-drain procedures.
Cited passages containing a missing fact do not mean the answer stated that fact.
Two answers overstated a human-review requirement beyond their cited wording;
one used three sentences despite the one-to-two sentence instruction.

The model stopped normally with output allowance remaining, so this was not
hard truncation or deadline exhaustion. No response was repaired, no original
question was rerun, and no follow-up model request was made. The changed corpus,
questions and response format prevent a controlled quality or speed comparison
with the original incomplete recall attempt. Operational themes also overlap.

## Preserved evidence

- [Frozen trial](TRIAL.md), [hash bindings](trial-protocol.json), and
  [pre-inference packet review](evaluation/review-only/independent-review.json).
- [Original response](results/recall/raw-refs.json),
  [exact compiled citations](results/recall/compiled/compiled.json), and
  [independent semantic review](results/recall/semantic-review.md).
- [Structured observation](results/observation.json) and
  [all 30 criterion judgements](results/recall/semantic-review.json).
- [Shutdown](results/server/shutdown.json),
  [RAM release](results/model-scratch-release.json), and
  [final host state](results/host-final-state.json).

The same R276 target-only TP2 profile used full FP16 KV with 2 GiB per rank;
all eight finite boundary checks passed before recall. These controls do not
qualify general arithmetic, model equivalence, the newer runtime package or
unattended coding. The observed server prefill was 5.299 seconds (1,912.6 tokens/s)
and stream-arrival decode proxy 9.607 tokens/s; these are one diagnostic request's
observations, not promoted benchmarks or cross-packet comparisons.

The application exited cleanly with one SIGINT, no OOM or new kernel fault.
All four cards passed final checks and are idle. All 80 staged model files were
fully rehashed before releasing only the 30,890,049,597-byte temporary RAM copy.
The verified cold model is retained; EX400U is unmounted. Root free space remains
about 53.2 GiB, and the existing 10 GiB RAM exclusion remains unchanged.

## Decision

Keep the compiler as a tested mechanical component. Do not connect this recall
output to an unattended coding worker or promote a model/package on this result.
Preserve the six unused coding cases and stop tuning these completed question
sets. The next immediate maintenance improvement is storage admission before
worker snapshot creation; it addresses a demonstrated risk independently of
model quality. LTX and Flash-Next remain parked for the owner's eventual return.
