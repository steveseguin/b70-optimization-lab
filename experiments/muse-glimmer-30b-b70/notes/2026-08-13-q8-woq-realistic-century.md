# Muse Q8 WOQ realistic-suite century result

## Status

The no-training compressed-target throughput objective is verified and the
result is promoted in
[`results/muse-glimmer-30b-q8-woq-b70`](../../../results/muse-glimmer-30b-q8-woq-b70/README.md).
Target/spec, structured JSON, B-tree rubric, and runnable LRU gates passed with
the limitations below. This is a declared UD-Q8_K_XL / WOQ result, not BF16,
lossless, universally token-exact, or a general quality-noninferiority claim.

## Kernel and serving identity

The target is Muse-Glimmer-30B UD-Q8_K_XL on four B70s with TP4. Eligible
large Q8_0 projections use a direct-strided oneDNN Xe2 WOQ path with BF16
activations, symmetric S8 weights, F16 group-32 scales, F32 accumulation and
F32 destinations. Decode widths 1 through 16 use one fixed width-16 primitive
with padded input/output buffers. DFlash remains the pretrained BF16 assistant;
no drafter training was performed.

Linear serving exports only the top-1 DFlash candidate. Removing the unused
top-15 DDTree export moved the canonical 256-token engineering packet from
`98.688` to `99.438 tok/s` (`70.904 / 105.900 / 121.509`). This still does not
meet 100 under that secondary arithmetic-mean metric.

## Frozen primary gate

Before looking at realistic-suite speed, the suite was frozen as
`experiments/muse-glimmer-30b-b70/realistic-suite-v1.json`, SHA256
`44d3dfafd9565b1411e9ea6a32c3f7fc323b862e4afbf96abe718c94ce9951b7`.
It contains the established 12 generic realistic prompts followed by the three
Muse campaign anchors and uses the canonical system message `Reasoning
strength: low`.

Every prompt was sent exactly once per run with `cache_prompt=false`, greedy
backend sampling, no history/ngram/checkpoint reuse, and a fresh server process.
Native llama.cpp streaming supplied one raw token ID per generation event. A
small additive response field exposes the server's existing
`n_prompt_tokens_cache` counter so cache-zero is directly auditable. The
qualified primary metric is:

`99 / (timestamp[99] - timestamp[0])`.

## Results

Record run:

- median: **166.66362996587313 tok/s**;
- p10: **107.41898887958072 tok/s**;
- mean: `173.25373551165606 tok/s`;
- minimum: `79.41770559571802 tok/s`;
- one-sided prompt-bootstrap 95% lower bound: **126.34887748489899 tok/s**
  (200,000 resamples, seed 20260813);
- 15/15 prompts measurable and `cached_tokens=0`.

Independent fresh-server confirmation:

- median: **169.5879986662736 tok/s**;
- p10: **107.42564746182691 tok/s**;
- one-sided prompt-bootstrap 95% lower bound: **125.69329102518215 tok/s**;
- 15/15 prompts measurable and `cached_tokens=0`.

The record and confirmation artifacts and hashes are indexed in
`data/muse-q8-woq-realistic-record-20260813.json`.

## Full sustained-decode closeout

The initial realistic result still used distributed TOP_K with `k=1` and the
canonical full-256 arithmetic mean remained below 100. Replacing that terminal
selection with the already-retained distributed ARGMAX/local-winner-reuse path
removed the remaining fixed top-k overhead.

Audit correction: the historical config set `LLAMA_SPEC_PROFILE=0`, but the
record source tests `getenv()` presence rather than parsing the value. The
profiler was therefore **enabled** in both retained full-256 runs; the server
log contains `[spec-prof]`. The `noprofile` filename is mislabeled. The two
measured means remain valid and exceeded 100 with the diagnostic overhead
present. The realistic ARGMAX record left the variable absent and had profiling
disabled.

A screen enabling `GGML_SYCL_BF16_GRAPH_CONVERSION_CACHE=1` for the BF16
DFlash context was startup-safe but changed proposal history and regressed the
full packet; it is rejected. The final configuration keeps that cache off.

Two independent fresh-server full-256 runs of the final ARGMAX configuration
(historically mislabeled `no-profile`) measured:

| run | prose | code | JSON | arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| 1 | 71.583 | 106.436 | 122.246 | **100.088** |
| 2 | 72.487 | 106.673 | 122.786 | **100.649** |

The pooled arithmetic mean is **100.3685 tok/s**. Code and JSON retained their
canonical hashes in both runs; prose follows the known Q8 near-tie and changed
acceptance by one token between starts. Both independent full runs exceed 100,
so this is not a selected one-off.

The same final ARGMAX configuration passed the frozen cold realistic suite at
**161.89958040164998 tok/s median**, p10 **108.57350121634562**, with a
one-sided prompt-bootstrap 95% lower bound of **127.08191057486525 tok/s**.
All 15 prompts supplied at least 100 exact raw token events and reported zero
prompt-cache reuse.

The final structured record is
[`data/muse-q8-woq-argmax-century-20260813.json`](../../../data/muse-q8-woq-argmax-century-20260813.json).
The raw JSONL, retained server logs, realistic token/timestamp capture, and
parity artifacts are preserved under the
[`standalone repro`](../../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md),
along with exact hashes and an offline verifier.

An ARGMAX-specific no-spec/DFlash check was token-exact for canonical code and
JSON at 256 tokens. Prose followed a different target-approved near-tie path,
so the final configuration is described as target-verified rather than
universally token-exact. No drafter training was used anywhere in this lane.

## Honest limitations

This demonstrates reproducible sustained throughput above 100 under the
workspace's preregistered first-100-token median metric. It does not mean every
prompt or full natural response stays above 100: the initial TOP_K record
minimum was `79.418`; the final ARGMAX minimum was `82.470`, and its
full-natural completion median after TTFT was `68.586 tok/s`.

Only 6/15 full-output hashes matched across the two fresh speed runs. This does
not invalidate the timing measurement, but it blocks any universal
deterministic/exact decode claim. The follow-up gates below supported the
scoped target-verified promotion while preserving that limitation; no
LocalMaxxing submission was made.

Follow-up target/spec checks refined that limitation:

- under the TOP_K reference at 256 generated tokens, no-spec Q8 and DFlash were
  token- and content-exact on all three canonical prompts (768/768 tokens), with hashes
  `6e0acc044576ad05`, `b4a2bda611510441`, and `4f813a9706abc163`;
- at 512 tokens, code remained exact, while prose diverged after token 156 and
  JSON after token 356. Both JSON outputs nevertheless parsed as exactly 12
  objects with the requested keys/types, and both prose outputs covered the
  required B-tree concepts. Therefore the serving path is target-verified but
  must not be labeled token-exact for long continuations;
- the 512-token code response was truncated mid-method and failed the runnable
  code gate;
- a focused 1024-token code run was token/content exact between no-spec and
  DFlash. Its final answer compiled and passed O(1)-behavior tests covering
  get/put, recency, eviction, overwrite, capacities 1 and 0, docstrings, and a
  runnable example.

Original host evidence directories (mirrored into the promoted repro):

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/realistic/q8-woq-fixed16-top1-spec-parity-20260813`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/realistic/q8-woq-fixed16-top1-spec-parity512-20260813`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/realistic/q8-woq-fixed16-code-parity1024-20260813`.

Three earlier measurement attempts are preserved as invalid evidence:

1. OpenAI stream chunks had no raw token IDs and therefore undercounted
   multi-token chunks.
2. Native `tokens_cached` represented total KV occupancy, not reused prompt
   tokens.
3. OpenAI `verbose` did not expose native IDs through the compatibility route.

The final native packet fixed both audit requirements without changing model
math: exact raw token events plus the authoritative prompt-cache reuse counter.
