# Qwen3.8 27B b2dd/1e90 TP4 zero-overlay r1 preregistration

Date: 2026-08-25 UTC
Status: frozen before launch
Primary product purpose: replace a neural.download TP4 source-stack blank with
an exact measured anchor while preserving every historical high.

## Frozen identity

- Qwen3.8 27B AutoRound INT4 model at the already verified local revision;
- vLLM `b2dd9ce73dce2ad09007d1db5c171454118981d7`;
- XPU kernels `1e90ffa672ba02f17a909da11838a4c55b199783`;
- dependency base digest `sha256:3ee0ec...f876`;
- image ID `sha256:059d4b3e...bc296`;
- embedded wheel-build source identity
  `/opt/neural-download/source-identity.json`, SHA-256
  `2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0`;
- no source, decision, DSO, binary, generated-kernel, or prior-cache overlay.

The exact campaign freeze is tracked in
`data/2026-08-25-qwen38-b2dd9ce73d-campaign-freeze.json`. Its R1 evidence
proves that b2dd/1e90/base-3ee0 matched the upstream observations when the
campaign first launched. A later remote commit never invalidates this frozen
measurement. Upstream refresh is a separate scheduled maintenance campaign.

## Exact topology and serving identity

- GPUs and `ZE_AFFINITY_MASK`: `0,1,2,3`;
- TP4, PP1, DP1; MTP0; float16 model and KV;
- maximum configured context: 32,768;
- GPU memory utilization: 0.60;
- one sequence; 1,024 maximum batched tokens;
- prefix caching off; chunked prefill on; async scheduling on;
- graph mode `FULL_AND_PIECEWISE`, captures 1 and 2, maximum capture 2;
- `PYTHONHASHSEED` absent, not zero;
- max-autotune, coordinate-descent tuning, and Triton autotuning flags absent;
- fresh ext4 cache; no `.best_config` seed.
- the exact model directory is the only USB path mounted into the container,
  read-only; only the isolated compile cache is writable.

## Atomic arms

The packet is one non-resumable sequence after one fresh four-card hardware
gate:

1. fresh-cache ignore-EOS diagnostic, 25 unique 512-token rows;
2. exact-cache natural-EOS strict replay A plus the full quality battery;
3. exact-cache natural-EOS strict replay B.

All three arms run when non-speed gates remain green even if a speed floor is
missed. A miss is recorded as a dated regression; it never lowers a floor or
overwrites an older value.

The packet must launch from clean, pushed `main`. It captures that exact local
lab HEAD, copies every runner/helper/suite/manifest/baseline input into the
fresh result root, and hash-checks those copies plus the live HEAD and worktree
after every arm. Remote vLLM movement is non-gating; concurrent mutation of
the local lab packet is not.

## Gates and frozen interpretation

- exact model direct/ordinary verification: 19/19;
- canary content `14`, cached tokens zero;
- benchmark: 25 unique cold prompts, token IDs returned, every eligible row at
  least 100 events, all cache counts zero;
- primary speed metric: median conventional 99-interval decode tok/s;
- replay A quality: 7/7 exact, 8/8 repeat with one hash, 8K needle, 24/24
  baseline comparisons, and all quality cache counts zero;
- compiled-cache file manifest byte-identical after each arm and container
  removal, with the exact arm container absent and its port unbound;
- diagnostic comparison floor 71.5488 tok/s;
- both strict arms comparison floor 71.29326283364946 tok/s and at least one
  at 71.39843006187554 tok/s.

The historical diagnostic 71.6741, stock strict capture 71.9001988117144,
accepted overlay observations 71.72254506718171 / 71.35287190161719 /
71.45427094575045, and protected ledger all remain untouched.

## Follow-up gate

Only after this zero-overlay packet closes may a separate packet inspect its
fresh b2dd TP4 namespace and remap historical `.best_config` decisions by exact
relative path plus equal embedded `.configs_hash`. No compiled Python, AOT,
binary, `.kernel_perf`, XDG, or outer-cache artifact may transfer.
