# Packet99 boundaries

| Arm or method | Decision | Revisit condition |
| --- | --- | --- |
| IQ4 byte-pair SLM lookup | Exact on CPU; rejected for 1,664-byte linked spills, 52 scratch messages | Distinct lower-liveness mechanism; [closeout](DOWN-CLOSEOUT.md) |
| IQ2 separate sign-table optimization | No such table in production IQ2_S; signs are inline | A different format/path with an actual table |
| Claim compact encoding is new | Packet52 already had the same two-bit magnitude encoding | Credit lab history and isolate changed scheduling/storage |
| Claim SLM amortizes over more rows | Old and new short workgroups both fill per 16 scalar rows | Actual distinct geometry/evidence |
| E3 word prefetch, E2 scale cache, H1 HC cache | Closed by supplied packet95/90 verdicts | Not reopened here |
| CPU/assembly pass as speed | Forbidden | Micro ≤85% kernel time in both orders, then exact B and A brackets |

Records belong on lane A. No candidate may skip micro qualification, mix
different candidates into one B grid, or use a B improvement as an A verdict.
Only the seven views exposed by `screen_jobs.py` are sealed for screening.
Packet97's other composition dimensions are retained in the engine; changing
one requires new selected-composition gates and seals.
