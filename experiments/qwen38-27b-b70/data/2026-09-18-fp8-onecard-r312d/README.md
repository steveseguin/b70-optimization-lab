# One-card FP8 package acceptance on the R312d-c image (September 18, 05:02-05:58 UTC)

Receipts from
[`run-20260918-fp8-onecard-r312d-campaign.py`](../../scripts/run-20260918-fp8-onecard-r312d-campaign.py), which ran
all three shipped profiles **through the package launcher**
([`serve.py`](../../../../packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py)) on the `r312d-c` image, then restored the
two-card depth-5 service. This is the acceptance campaign the September 18 staging commit (`b4c727108`) left open; the
[lc-4 receipts](../2026-09-18-fp8-lc4/) are the same image measured through the research launcher.

- Image: `neural.download/vllm-openai-xpu:qwen38-fp8-v0290-r312d-c-multiq`, local id
  `sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a`, passed to the launcher as
  `B70_FP8_TP1_IMAGE` (the registry tag `r312d-fp8-tp1-20260918` is not pushed yet).
- Source run directory `/mnt/fast-ai/bench-results/fp8-onecard-r312d-20260918/`, runner log
  `/mnt/fast-ai/bench-results/onecard-r312d-runner-20260918.log`, unit `fp8-onecard-r312d-20260918`.
- Every comparison is against the same R311b no-MTP references the shipped 32K numbers were gated on
  ([`2026-09-17-fp8-ckpt2`](../2026-09-17-fp8-ckpt2/), the 896-token attention block, 19.430 tok/s without MTP), and
  the long corpus against probe-1's REF5 ([`2026-09-17-fp8-probe1`](../2026-09-17-fp8-probe1/)).
- Nothing above 5 MB was skipped. The two per-request ladder dumps (1.9 MB and 1.3 MB each) are represented by their
  `*-ladder-vs-mtp0.json` verdicts, as in the [R311b packet](../2026-09-17-fp8-onecard-32k/).

## Result

| Profile | Context | Strict vs no MTP | Writing speed | Other gates |
| --- | ---: | --- | ---: | --- |
| `recommended` | 32,768 @ 0.975 | **12/12** twice | **54.236 / 54.011 tok/s** | ladder 64/64 x3, 2K/8K/16K screen, 2,048-30,720 long corpus, chat quality + baseline match, 21-request logprob replay, cache zero |
| `max-context` | 40,960 @ 0.983 | **12/12** | **54.324 tok/s** | ladder 64/64 x2, 2K/8K/16K screen |
| `no-quantization` | 28,672 @ 0.975 | **12/12** | **52.421 tok/s** | ladder 64/64 x2, 2K/8K/16K screen |

Every profile started, served and stopped cleanly through `serve.py` and removed its container. The two-card depth-5
service came back afterwards as unit `fp8-service-20260918-onecard-r312d` (state `service/` here, port 18124) and its
own strict run was **12/12 at 90.271 tok/s** against the comm-2 no-MTP reference.

## Writing speed after a long prompt (`recommended`)

Tokens 1-100 after prompts from the unrepeated September 17 long corpus, median within each content type then across
types, two repeats, 6 requests per point. Every continuation is identical to the no-MTP reference on both images.

| Input tokens | R311b (32K, probe-2) | R311b (max-context, probe-1) | R312d-c | Change vs probe-1 |
| ---: | ---: | ---: | ---: | ---: |
| 2,048 | 59.24 | 59.23 | 59.24 | **0.0%** |
| 8,192 | 76.82 | 76.91 | 79.96 | **+4.0%** |
| 16,384 | 65.71 | 65.82 | 72.36 | **+9.9%** |
| 24,576 | 39.73 | 39.76 | 45.52 | **+14.5%** |
| 30,720 | 37.48 | 37.50 | 43.99 | **+17.3%** |

By content type at 30,720 tokens: code 54.55 -> 63.36, documentation 28.67 -> 33.46, prose 37.50 -> 43.99 tok/s. The
2,048 row is within 0.2% either way, which is why the launcher keeps `B70_FA_MULTIQ_MIN_K=4096` and leaves short
prompts on the per-row path. Prompt reading is unchanged (2,029 tok/s at 2,048 down to 1,807 at 30,720).

The short 2K/8K/16K screen (AMD-transfer corpus, all three profiles) shows the same shape: prefill within 0.5% of
R311b, decode after an 8K prompt 76.4 vs 72.9 and after 16K 68.8 vs 62.3 on `recommended`.

## Files

| Pattern | What it is |
| --- | --- |
| `campaign.log`, `results.json` | runner log and the full result record (every gate, the speed table, the service block) |
| `<profile>-launch.json`, `<profile>-state.json` | the exact launcher command, environment and container state per profile |
| `<profile>-strict-{identity,canaries,performance}.json` | the strict suite's run identity, canaries and per-request timings |
| `<profile>-strict-vs-reference.json` | the 12/12 comparison against the R311b no-MTP reference |
| `tp1-pkg-32k-run2-strict-*` | the second strict run on the same `recommended` server |
| `<profile>-ladder-vs-mtp0.json` | the 64-prompt sequential-oracle and queued-pass verdicts |
| `<profile>-context-summary.json` | the 2K/8K/16K screen |
| `tp1-pkg-32k-long-context-summary.json` | the 2,048-30,720 long corpus in three content types |
| `tp1-pkg-32k-quality.json`, `tp1-pkg-32k-history-summary.json` | the chat quality suite and the 21-request logprob replay |
| `service-*` | the restored two-card depth-5 service and its strict run |

Narrative: [findings note](../../notes/2026-09-16-fp8-review-findings.md). Package:
[`packages/qwen38-27b-fp8-tp1-b70`](../../../../packages/qwen38-27b-fp8-tp1-b70/README.md).
