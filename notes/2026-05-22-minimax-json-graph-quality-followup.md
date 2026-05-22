# MiniMax M2.7 JSON Quality Follow-up - 2026-05-22

Hardware/software context:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32 GB, TP4
- Engine: local vLLM 0.20.1 XPU build with llm-scaler INT4 MoE path
- Harness: `scripts/run-minimax-json-quality-throughput.py`
  - GitHub artifact: `scripts/run-minimax-json-quality-throughput.py.gz.b64`
  - Decode with: `base64 -d scripts/run-minimax-json-quality-throughput.py.gz.b64 | gzip -dc > scripts/run-minimax-json-quality-throughput.py`
- Promoted environment base: `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`

The question was why the simple website task could pass while JSON tasks were unstable. The answer is not that the model cannot produce JSON. It is a runtime-path issue:

- Strict JSON with the control-character `logit_bias` sampler guard can fail on XPU graph in the logits processor path.
- Strict JSON with no sampler guard but with post-parse validation passes on the non-cudagraph path.
- Forced multi-GPU XPU graph can reach the same 86-89 tok/s class on accepted JSON outputs, but repeated short requests are not quality-clean: graph replay intermittently emits corrupt fragments or semantically wrong fields.

## Harness updates

`run-minimax-json-quality-throughput.py` now separates control-character handling from validation:

- `--control-char-policy logit_bias`: ban control-character tokens in the sampler.
- `--control-char-policy validate_only`: do not alter logits; strict validation still rejects control characters.
- `--allow-control-chars`: compatibility alias for validate-only sampling behavior; validation still rejects control chars.
- `--structured-json`: optional vLLM `StructuredOutputsParams(json=...)` schemas for the three JSON tasks.

This keeps quality accounting honest: sampler/runtime failures and content failures are visible instead of being conflated.

## Results

| Run | Path | Pass | Raw pass rate | Accepted tok/s | Effective accepted tok/s | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Non-cudagraph validate-only | `20260522T161314Z-ctx2048-c1-cgnone-compile1-validateonly-repeat1` | yes | 3/3 | 29.49 | 29.49 | Clean strict JSON, slower path |
| Non-cudagraph structured JSON | `20260522T161032Z-ctx2048-c1-cgnone-compile1-structuredjson-repeat1` | yes | 3/3 | 16.66 | 16.66 | Clean, but constrained decoding is expensive |
| Graph validate-only | `20260522T161917Z-ctx2048-c1-graph-compile1-validateonly-repeat3-warm1` | no | 8/9 | 89.31 | 85.69 | One corrupt `b70_status` response |
| Graph strong+sync | `20260522T162310Z-ctx2048-c1-graph-compile1-validateonly-strong-sync-repeat3-warm1` | no | 8/9 | 59.63 | 53.79 | Slower and still one corrupt response |
| Graph bad-fragment ban | `20260522T162937Z-ctx2048-c1-graph-compile1-validateonly-banfrag-repeat3-warm1` | no | 8/9 | 86.56 | 63.09 | Failure moved to another task, so not a real fix |
| Graph validated retry | `20260522T163303Z-ctx2048-c1-graph-compile1-validateonly-retry2-repeat3-warm1` | yes | 9/12 raw attempts | 88.84 selected | 62.03 including retries | Practical mitigation, not a clean backend pass |

The recurrent corruption patterns included fragments such as `kelompok`, `luas`, `yml`, malformed JSON keys, and one semantically wrong `MiniMax-M2.6` field. These are not normal model reasoning failures. They are consistent with a forced graph replay/output correctness issue under repeated short requests.

## Current Interpretation

The previously reported 89-93 tok/s long-decode result remains plausible for warm single-session decode, and the accepted JSON outputs in this follow-up also run in that band. However, repeated short JSON requests show intermittent quality failures on the forced graph path. Therefore:

- Do not publish raw forced-graph JSON runs as quality-clean until the no-retry gate passes repeatedly.
- For strict JSON usage today, either use non-cudagraph mode for correctness, or use graph mode only behind a validator/retry wrapper and report effective throughput including rejected attempts.
- The validated-retry graph run is useful for application behavior, but it is not evidence that the backend is fixed.

## Next Work

1. Investigate the XPU graph forced communication path:
   - `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`
   - `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`
   - graph replay output ownership in `vllm/compilation/cuda_graph.py`
2. Build a targeted replay reproducer that repeatedly runs the same short request against one live engine and checks raw token hashes.
3. Try a safer graph partition where communication ops are excluded but more non-communication compute remains compiled.
4. Add a serving-side JSON validator/retry wrapper only as an explicit mitigation path.
5. Continue to treat non-cudagraph strict JSON as the correctness baseline.
