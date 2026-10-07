# 27B worker trial with an explicit full-precision cache budget

**Active:** startup reports 59,904-token cache capacity and about 39 GiB available
host RAM. Eight boundary diagnostics and the unchanged worker-format canary
passed. Coding and recall results remain pending. The supervised server must
stop after this bounded trial.

Preregistered follow-up to the [first target-only arm](../qwen27b-target-only-pilot-20261007/README.md),
which passed its runtime gates but missed the fixed coding RAM admission. The
first application stopped cleanly and all four cards passed postflight.

The only serving change is `--kv-cache-memory-bytes 2147483648`: 2 GiB per
GPU instead of the 9.51 GiB automatically allocated. Keep full FP16 KV, the same
33,024-token context, single sequence, FP8 model revision, target-only R276 image,
FP16 activations, eager mode, TP2 topology and transport. This is an application
allocation, not a host memory, swap, cache or power-setting change. The explicit
cache budget overrides GPU utilization for cache sizing; the original utilization
argument remains recorded. Installed-source and capacity evidence are under
[cache-admission](cache-admission/).

Repeat the original eight boundary diagnostics and one actual-SYSTEM canary
before useful tasks. The worker profile, prompts, acceptance fixtures and recall
corpus remain byte-identical. No coding response has yet been observed for 27B.
Require the same 24 GiB available host RAM and 10 GiB free tmpfs before each task;
never reduce those checks to admit work. Each full source snapshot remains intact.

Run catalog then context once each, with independent review and verified evidence
archives between them. Reuse the healthy endpoint for the original full-corpus
recall request only after both attempts and with eight minutes remaining. One
bounded application start, at most 60 minutes; stop once after the sequence or
failure. There is no retry or fallback allocation. Preserve failed results.

Output root: `/home/steve/worker-qwen27b-smallkv-20261007/`. The copied helpers
only change output paths, campaign identifiers, the container name and that cache
argument. [Preparation identities](preparation-identity.json) record every copy.
The original cold-preservation receipt remains authoritative; model RAM files
are retained throughout. No external drive or two-card-host access is needed.
