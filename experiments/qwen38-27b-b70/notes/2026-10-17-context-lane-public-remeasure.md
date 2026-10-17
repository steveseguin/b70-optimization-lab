# Context lane: today's server against the public figures (2026-10-17)

The public context pages (skindeep `context-use.html`, the working-view table; ctxkeeper README) quote times measured
before two of today's changes, both bit-identical: one-launch verify (`2026-10-17-fp8-writing-attention.md`) and the
exact cache's tail switch (`2026-10-17-fp8-cache-tail-block.md`).

## Already measured on the same task (campaign 27, the 240K-token question stream, seed 0)

| Working view | public | today (c27a) |
| --- | --- | --- |
| 32K | 39/39; 9 min | 39/39; 6 min 58 s |
| 64K | 39/39; 10 min | 39/39; 7 min 24 s |

## Repair task re-measure (registered 05:51 EDT, before the run): campaign 28d

The public "32K repair: 40/40, 7/7; 16 min" is XR4 on `repair-n40-s2x` from campaign 17 (2026-10-13, 15 min 38 s;
`2026-10-10-context-16k-baseline.md`). Today's runner (`longrun-campaign28.sh`, kind `repair`: notes thinking off,
effort medium, in-place notes, recite on tickets) on c27a's server (depth 5, one launch, tail), queue line
`K32 repair 2x 3600`.

- **Prediction:** 40/40 fixed, 40/40 clean, 7/7; 10-13 min. The keeper and server have changed since campaign 17, so
  the transcript is not expected to match it; this is a re-measure of what the current stack does, not an A/B.
- **Use:** the figures go to the owner as a proposal for the public pages (owner's call); nothing public changes here.
