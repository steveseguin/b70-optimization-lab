# Current-f01e AutoRound TP1/MTP0 FULL_AND_PIECEWISE E4M3 4K sentinel R1

Status: **preregistered and executable; not launched**.

This packet measures exactly one missing cell in `qwen38-tp1-vllm-xpu-target-matrix`: current-f01e Qwen3.8 AutoRound INT4, TP1, MTP0, exact active context 4K, `FULL_AND_PIECEWISE`, and `fp8_e4m3` KV. It is not a depth ladder or a publication packet.

The target is deliberately E4M3-specific. Current-f01e eager E4M3 exact 4K (`1d541ec7...`) and PIECEWISE E4M3 exact 4K (`cb4f7c4b...`) independently passed, contain the same 128 token IDs, and share hash `a3d7ad63...`. The candidate must equal both arrays token-for-token. Current-f01e F16 exact 4K has a different token hash (`3febb16e...`) and is not an oracle for this compressed-KV cell.

The dated b2dd/1e90 F16 `FULL_AND_PIECEWISE` run is comparison-only graph-shape precedent. It proves the intended capture configuration `[1,2]` and the simultaneous mixed PIECEWISE and decode FULL markers. Its source, KV dtype, token IDs, and speed do not transfer.

The runner launches one fresh TP1 server on GPU0 using exact image `f01e24f6...`, source `ac7509e2...`, E4M3 KV, no speculation, port `19523`, and dedicated output/cache/container identities. Startup must resolve `FULL_AND_PIECEWISE`, capture sizes `[1,2]`, maximum capture size 2, `enforce_eager=False`, `world_size=1 rank=0 local_rank=0`, `TP rank 0`, both graph capture markers, and `Graph capturing finished`.

Only one exact helper request is made at 4096 active tokens. It must pass every exact-depth and cache-zero gate and return 128 IDs identical to both frozen E4M3 parents. The candidate then runs the complete quality battery against the frozen standard baseline: 7 exact cases, 8 passing repeats with one hash, a passing 8K needle, 24 true baseline comparisons, and cache zero on all 16 requests. The needle is quality evidence only and creates no exact-8K cell.

All 19 model files must verify before launch. The fresh cache must expose exactly the TP1 `rank_0_0` namespace, and cleanup must leave no container, port, model-server process, or render owner.

Current E4M3 eager and PIECEWISE results disagree at 2K, 24K, and 32K despite passing their quality batteries. Therefore even a clean 4K pass cannot authorize another depth. There is no speed floor, automatic expansion, publication, replacement, protected-value change, headline, or LocalMaxxing authority.

Static check (inert):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-r1.sh --check
```

GPU execution (not performed by this preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-20260826-r1'
```
