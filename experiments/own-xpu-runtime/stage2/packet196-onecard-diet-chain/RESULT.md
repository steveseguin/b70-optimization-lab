# One-card expert instruction diet: qualified local record

## Question and identity

Does the exact gate/up instruction diet improve the one-card max23 line?
Qwen3.8 Flash-Next 125B-A6B Unsloth UD-IQ3_XXS, one B70, target-only greedy,
oracle `iq3-p49-split32-v1`, BF16 KV, context4096, 23,049,601,024-byte expert
cache, spin wait and kernel foreground I/O. Engine SHA256
`537c080767f241653a8ac13c77289cd59e8f7444cbee2a4fcb35586eb1e743d4`.
The new flag is `--expert-gateup diet`; capacity and target arithmetic are unchanged.

## Outcome

**37.59560460827345 tok/s**, median of six prompt-class medians using 99 intervals
between generated tokens1 and100 after TTFT. This is **+2.71318%** over the
matching prior local record36.60251162011413. All12 cold prompts and1536 tokens
are exact. All-prompt median38.436544, p10 35.685356; TTFT median1.736s;
capped full-wall rate25.315351 tok/s.

LocalMaxxing accepted the single submission after local and server dry runs:
HTTP201, **APPROVED**, [cmvl5k4p9004nng01z5xtanw5](https://www.localmaxxing.com/runs/cmvl5k4p9004nng01z5xtanw5).
This supersedes `cmvkcqznb002lng01fsrhjn7t` for the matching one-card lane.

## What worked

The registered chain ran once on October23,15:18–15:51UTC. K1a,K1b,KD,W2m,WS,
WS128x,WS128 all passed. The independent audit recomputed raw token equality
and timings, checked source/binary/cache/KV identity and all window digests,
and found clean teardown with no new GPU fault. The unit exited0; privileged
passive device ownership inspection found no remaining holder.

## What failed or remains uncertain

The first coordinator admission refused before any native launch because
systemd reported an unloaded transient service as exit4/`inactive`. That
parser case was fixed and tested, the packet resealed, and the refusal
reviewed with preserved receipts. Continuation used the already drained host;
it did not stop or restart applications again or repeat a benchmark attempt.

This retains the owner-authorized **128-token scope**. The strict512-token
promotion gate is false and disclosed. No second fresh timing repeat, standard
512-token prefill or natural-completion qualification is claimed. The result
is a local-record improvement, not a current global ranking claim. No prompt,
KV or response reuse contributes to it.

## Evidence and patches

- [Prepared result](submission/prepared-a/result.json), [payload](submission/prepared-a/payload-queue.json)
  and [compressed evidence](submission/prepared-a/evidence.json.gz).
- [Seven-stage chain receipt](evidence/card0-diet-a/queue.json) and
  [independent audit](evidence/device-chain-independent-audit.json).
- [Submission receipt](../../../../data/localmaxxing-responses/2026-10-23-packet196-onecard-diet-chain-a-onecard-ws128.txt).
- [Operational continuation review](../../ops/packet196-window/evidence/resume-review-a.json)
  and [chronological note](../../../../notes/2026-10-23-packet196-onecard-diet-chain.md).
- The frozen preparation, original engine binding, source/proof snapshot and
  earlier failed readiness receipts remain in this packet.

The41.93MB compressed evidence bundle is retained with this record because it
contains the hash-bound raw chain members needed by the submission validator,
including exactness and timing evidence beyond the compact tracked summaries.
Its schema is `lab.packet58aj.evidence-bundle.v1`: each member stores its SHA256
and exact bytes as base64. Keep it beside the prepared result/attestation for
`packet58_submission.py` evidence replay; restoring a member means decoding
those bytes into a separate evidence directory and verifying its recorded hash.
Do not overwrite original run evidence. The
[archive receipt](evidence/device-chain-archive.json) records its path, size and
checksum. It contains research evidence, not a deployable engine package.

## When to revisit

Use this measured line as the next matching one-card baseline. The next
substantive runtime work is the
[warm request interface](../../../../notes/2026-10-23-warm-request-front.md):
connect the qualified checkpoint mechanism to a continuously loaded owner,
with explicit session-reuse accounting and separate exactness/device gates.
