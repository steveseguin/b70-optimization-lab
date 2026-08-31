# Qwen3.8 GDN B/A FP16 cross-process D2 result

Date: 2026-08-31

Status: **current padded path stable; historical direct path causally unstable**

The current overlay's 256-row padded B/A projection was bitwise exact within
and across all eight fresh processes for all 24 M/N cases. The direct unpadded
control was unstable at M=65,71,75,78 for both TP2-local N=48 and TP1 N=96,
often producing a distinct hash in every process. This independently validates
why the B/A pad exists and rules the engaged padded path out as the remaining
R9 cause.

Only 1/24 padded outputs exactly equaled the direct control. That numerical
difference is expected from the different oneDNN algorithm and reinforces the
need for later same-model quality/baseline attestation; it is not permission to
remove the pad.

Next: test the actual Gemma-style RMSNorm plain and fused-residual paths at
M=1 and every strict-suite prefill size, comparing direct, per-row serial, and
padded execution across fresh processes.

Condensed result:
`../data/2026-08-31-qwen38-gdn-ba-fp16-cross-process-d2-result.json`.
Complete raw result SHA-256: `e5c4a03a...b68de`.
