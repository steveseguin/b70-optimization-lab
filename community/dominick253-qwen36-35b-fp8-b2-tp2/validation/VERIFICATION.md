# Verification matrix

This file records how each submitted claim was checked before the PR update.
The entry remains `community-reported` because these checks ran on the
contributor host, not the maintainer's reference lab.

## Model identity

1. Hugging Face `refs/main` resolved to
   `95a723d08a9490559dae23d0cff1d9466213d989`.
2. `hf cache verify Qwen/Qwen3.6-35B-A3B-FP8 --fail-on-missing-files`
   checked 56 files without a missing-file failure.
3. The safetensors index named 42 unique shards. All existed and totaled
   37,463,662,160 bytes.
4. The live `/v1/models` response reported the same snapshot revision.

## Runtime identity

1. The launcher pins image digest
   `3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e`.
2. `docker inspect` reported the same image ID and command for the live
   container.
3. The vLLM startup log resolved TP2, FP16 compute, FP8 weights, `fp8_e4m3`
   KV, 131,072 context, maximum 12 sequences, eager mode, and MTP2.
4. In-container package metadata reported vLLM
   `0.21.1.dev0+gad7125a43.d20260802.xpu`, XPU kernels
   `0.1.8.3.dev0+g3cab97a.d20260802`, custom ESIMD kernels `0.1.0`, and
   PyTorch `2.11.0+xpu`.

## GPU identity

1. PCI discovery listed two `8086:e223` devices at `03:00.0` and `08:00.0`.
2. In-container PyTorch reported two XPU devices named
   `Intel(R) Graphics [0xe223]`.
3. PyTorch reported 34,242,297,856 bytes for each device.
4. PCIe width was deliberately omitted because the current width probe
   conflicted with the earlier contributor report.

## TP2 workaround

1. Intel contributor guidance in `llm-scaler` issue #550 specifies the four
   simple-collective variables used here.
2. The launcher contains those variables plus the recorded TCP/direct oneCCL
   environment.
3. `docker exec env` reported the same variables in the live container.
4. The service reached health and completed all three clean TP2 sweeps.

This establishes a working configuration on this host. It does not isolate one
variable as the sole cause of earlier startup failures.

## Throughput

1. Three separate raw `llama-benchy` JSON files record five measured batches at
   each concurrency after one warmup batch.
2. `benchmark-triple-summary.json` stores all three sweep means and their range.
3. `verify-evidence.py` recomputes each raw mean from its per-run values, then
   recomputes the three-sweep means and ranges.
4. Three raw monitor files show exactly 165 expected completed requests in each
   sweep, with no extra completed request.

The superseded preliminary benchmark was not submitted because user traffic
overlapped it.

## Driver stability during the clean benchmark

1. The benchmark wrapper sampled running and waiting request gauges every
   100 ms.
2. It counted selected `xe` fault/reset signatures before and after each sweep.
3. All three raw monitors record 697 before and 697 after, for a zero delta.
4. `verify-evidence.py` rejects any nonzero delta.

The claim is only zero new matching lines during these sweeps. The 697 earlier
boot events are not attributed to this configuration.

## Long-output corruption gate

1. Four complete MTP responses are preserved in two raw JSON artifacts.
2. The original validator recorded zero failures across 11,024 completion
   tokens.
3. `quality-manifest.json` records response token counts, finish reasons,
   content hashes, character counts, and `!!!!` counts.
4. `verify-evidence.py` independently recomputes hashes, token totals,
   `!!!!` counts, and repeated-punctuation checks from the raw text.

This is a bounded test. It does not claim that every future response is immune.

## GDN source context

1. Intel `llm-scaler` PR #464 documents the XE2 GDN out-of-bounds write and
   all-`!` failure signature.
2. PR #464 merged on 2026-06-09.
3. Local inspection of source tag `vllm-0.21.0-b2` at
   `f19b3294e63d49f1cfb90a1b6f5e3716237df5a9` found the
   `v_head_id >= num_v_heads` guard in `vllm_xpu_kernels.patch`.
4. The bounded runtime tests did not reproduce all-`!` output.

The compiled container does not expose enough native source provenance for a
direct binary proof. The packet therefore does not make a one-cause claim.
