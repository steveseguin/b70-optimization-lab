# Qwen3.8 Q8_0-weight/F16-KV cache64 graph sentinel result

Status: **completed valid diagnostic sentinel**. The result publishes no
website cell, speed claim, headline, protected-value replacement, or
LocalMaxxing submission. It authorizes only a separate, reviewed seven-depth
Q8_0-weight/F16-KV graph-curve preregistration.

The matched control used Q8_0 weights, TP1, MTP0, F16 KV, fit off, exact 8K
HTTP serving, the same pinned graph-patched binary, and a fresh server lifetime
for each arm. Only graph off/cache0 versus graph on/cache64 changed. The
terminal receipt passed all 18 frozen checks.

Both arms returned the same 128 token IDs, text hashes, prompt usage, and zero
cached tokens. Their conventional 99-interval diagnostic observations were
19.17044886972126 tok/s graph-off and 18.66215581878247 tok/s graph-on. The
single graph-on observation is 2.651440529082305% lower; the preregistration had
no speed floor, so this is descriptive diagnostic evidence only.

Each arm independently passed all seven exact quality cases, two repeat runs
with one stable hash, the 25,200-token pre-template long-context needle
(25,212 API prompt tokens), and 10/10 cache-zero quality requests. All quality
output hashes matched between graph-off and graph-on.

The graph arm recorded 263 requested and 263 replayed operations, including
202 direct replays against the frozen minimum of 120. It created and recorded
61 entries in the cache64 profile, with zero cache-full, compatibility reject,
device-unsupported, update, or recreate events. Both arms closed the port,
left no server survivor, needed no forced kill, and left the render node idle.

The compact result binds all 22 raw files by byte size and SHA-256:

- `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1-result.json`
- validator: `experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1-result.py`
- raw root: `/mnt/fast-ai/bench-results/qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-20260826-r1`

No family, package, generated page, existing graph-off cell, or future full
curve packet was modified by this sealing step.
