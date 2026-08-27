# Qwen3.8 Q8 TP1 strict headline preregistration

## Purpose

Fill the one-card Q8_0 package's missing single-user headline without
transferring its direct `llama-bench` depth rate or queued-concurrency rate into
a different workload.

## Frozen identity and workload

- model `Qwen3.8-27B-Q8_0.gguf`, SHA-256
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`;
- accepted TP1 `llama-server` SHA-256
  `35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545`
  and SYCL backend SHA-256
  `0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154`;
- one B70 (`SYCL0`/physical GPU 0), Q8_0 weights, F16 KV, no MTP or draft,
  `--reasoning off`, graph off, one active slot, 8,192-token capacity, prompt
  cache and slot similarity disabled;
- raw untemplated native `/completion` prompts with returned token IDs;
- full fixed twelve-prompt/six-class suite, one unique request per prompt,
  512-token natural stop/length cap, temperature zero, `cached_tokens=0` on
  every row, and the 99 intervals between generated-token events 1-100;
- class-balanced headline: median within each prompt class, median of the six
  class medians, then median of the two fresh-server attempt values.

The model is verified through direct and ordinary I/O before each fresh server.
The runner is create-only and captures artifact, command, environment, output,
cache, and canary evidence.

## Gates

Both attempts must pass the complete workload and objective canaries. All
twelve complete token arrays must match across fresh servers. The outputs are
also compared with the already-qualified Q8 TP2/historical raw-completion
oracle; any difference is disclosed and investigated rather than ignored.

No result transfers to TP2, MTP, chat templates, long context, or aggregate
serving. A failed or incomplete attempt remains evidence and never becomes a
headline.
