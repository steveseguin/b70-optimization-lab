# Arc Pro B65 Qwen3.8 field report

Evidence level: `community-reported`

Contributor/source: `boyter`, X post relayed by the maintainer on 2026-08-20

Reference-lab reproduction: none; the original post URL, raw logs, exact model
revision, command, prompt suite, context, KV type, and metric window were not
captured in the intake

## Reported observations

The maintainer relayed these approximate Qwen3.8 figures from a single 32-GiB
Intel Arc Pro B65:

- about `42 tok/s` with MTP;
- about `22 tok/s` without MTP;
- about `19 tok/s` after a 150-W power limit.

The intake does not establish whether the 150-W row used MTP, whether the
numbers exclude prompt processing, or whether all three rows share one model,
quantization, context, and prompt. They are useful orientation, not an A/B or
purchase recommendation.

## Hardware context

Intel's Arc Pro B-series quick-reference guide lists the B65 and B70 with the
same 32-GiB capacity, 256-bit interface, and `608 GB/s` memory bandwidth. It
lists B65 at 20 Xe cores / 160 XMX engines / 2.4 GHz / 197 peak INT8 TOPS and
B70 at 32 Xe cores / 256 XMX engines / 2.8 GHz / 367 peak INT8 TOPS:

<https://www.intel.com/content/dam/www/central-libraries/us/en/documents/2026-03/intel-arc-pro-b-series-graphics-quick-reference-guide-v1-0.pdf>

That makes the field report plausible in shape: dense low-batch decode can be
weight-bandwidth dominated and therefore lose less than the core-count ratio,
while prompt processing, draft work, and compute-heavy kernels can expose more
of the B65's reduced execution resources. This is an inference from the spec
sheet, not a validation of the reported rates.

## Comparison boundary

Do not compare the reported single-B65 `42` directly with this repository's
`49.717503 tok/s` Qwen3.8 Q4_K_M headline: the latter is **two B70s at TP2**,
target-only, on a fixed cold suite. The closest published one-B70 Qwen3.8 rows
also use different checkpoints, runtimes, quantization, contexts, and gates.

A useful follow-up report needs GPU board/driver/power identity, exact GGUF or
checkpoint SHA, llama.cpp/vLLM commit, complete flags, context and KV types,
MTP depth/acceptance, fixed cold prompts, cached-token telemetry, conventional
99-interval decode accounting, and the raw server timing log.
