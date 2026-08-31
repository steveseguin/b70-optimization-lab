# Qwen3.8 AutoRound INT4 native-GDN TP2 R6 result

Date: 2026-08-31

Status: **rejected; 10/12 exact fresh-server repeat**

Correction (2026-08-31): the pinned image does not implement
`VLLM_XPU_GDN_NATIVE_FALLBACK`. The recorded environment variable was inert.
R6 is a valid native-path repeatability measurement, but it did not compare
fallback and native paths. Any earlier causal wording about that toggle is
withdrawn.

R6 requested a fallback toggle that the pinned image ignored. Both fresh
compiled servers passed the complete fixed workload and canary gates. Their
strict class-balanced rates were 31.9525 and 31.9263 tok/s.

The output gate failed: 10/12 complete token arrays matched. The
`performance-hypotheses` and `sql-debugging` prompts diverged. Consequently
31.94 tok/s is diagnostic-only, no quality attestation is authorized, and MTP
remains blocked.

This improves localization relative to the fallback route but does not prove
that native GDN alone is the entire cause. The next bounded test synchronizes
immediately after each native GDN call. It must be preregistered and repeated
across two fresh servers; the prior all-reduce synchronization negative must
not be conflated with this narrower GDN completion boundary.

Structured result:
`../data/2026-08-31-qwen38-autoround-native-gdn-tp2-r6-result.json`.
