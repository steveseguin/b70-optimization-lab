# Qwen3.8 Flash-Next FP8 A74 root-NVMe free-space floor negative

Date: 2026-09-03 03:05 EDT
Status: procedural negative; no server started; A75 is the byte-identical successor

The A74 host wrapper stopped at its pre-launch guard `requires >=
220000000000 free NVMe bytes`: the root SSD had 205 GB free after the
overnight 27B R139 image builds (docker build cache 10.4 GB, seven image
tags, runtime caches). Freed without touching any result: `docker builder
prune -af` and the replay runtime cache directories; 228 GB available
afterwards. A75 (`tools/rewrite-q38-a74-to-a75-4k-probe.py`) re-freezes the
same server with fresh attempt paths (attempt 75 / port 19747).
Operational rule: keep at least 220 GB free on the root SSD before any
Flash-Next launch; docker build cache on this host counts against it.
