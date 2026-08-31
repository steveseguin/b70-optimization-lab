# Qwen3.8 AutoRound INT4 TP1 eager R9 result

Date: 2026-08-31

Status: **rejected; 8/12 exact fresh-server repeat**

Both eager TP1 arms passed the complete realistic workload and canaries at
25.2181 and 25.2831 tok/s. Only 8/12 complete token arrays matched; the
mismatches were `benchmark-analysis`, `release-plan`, `risk-register`, and
`sql-debugging`. Compilation is therefore not required to trigger the
rank-local nondeterminism. These rates remain quarantined; quality and MTP are
not authorized.

Identity audit also found that the requested fallback environment variable is
not implemented by the pinned image. The image's default native XPU GDN path
ran in both arms; no fallback treatment was engaged.

The current overlay uniquely pads the GDN B/A prefill projection to a 256-row
FP16 `F.linear`. The next raw diagnostic must test that exact padded operation
across fresh processes before modifying recurrent-state code.

Structured result:
`../data/2026-08-31-qwen38-autoround-native-gdn-tp1-eager-r9-result.json`.
