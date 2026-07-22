# Laguna S 2.1: attention set rebuilt, target baselines measured, DFlash blocked

Date: 2026-07-22 (America/Toronto)

## Numbers first

| Mode | Median generated tokens 1-100 after TTFT | p10 | Mean | Median TTFT | Fresh/cache-zero | Classification |
|---|---:|---:|---:|---:|---|---|
| target-only eager | **13.802098 tok/s** | 13.669648 | 13.791683 | 79.434 ms | 6/6 | valid nonspec baseline |
| target-only PIECEWISE, M=1 | **19.461517 tok/s** | 19.335432 | 19.476362 | 72.639 ms | 6/6 | valid nonspec baseline |
| DFlash eager, depth 7 | **11.414684 tok/s** | 11.369503 | 11.405444 | 100.546 ms | 6/6 | diagnostic only: missing kernel fallback and 0% acceptance |

PIECEWISE is `41.004%` faster than eager. Eager reaches only
`2.680-3.286%` of the stated 515-420 tok/s roofline; PIECEWISE reaches
`3.779-4.634%`. The DFlash diagnostic is `17.297%` slower than eager.

DFlash proposed 5,334 tokens over 762 draft steps during the fixed suite and
accepted **0**: token acceptance `0.0%`, mean acceptance length `1.0` including
the target bonus token. It is not an optimized or promotable result.

No LocalMaxxing endpoint, submission, or held-out pack was used. Nothing was
written to `/mnt/fast-ai`.

## Complete attention dispatch set observed and derived

The target checkpoint has head dimension 128, eight total KV heads, block/page
size 64, 12 full-attention layers with 48 total Q heads, and 36
sliding-attention layers with 72 total Q heads and window 512. Under TP4 that
is 12Q/2KV (ratio 6, q-group bucket 8) for full attention and 18Q/2KV (ratio
9, q-group bucket 16) for sliding attention. One active request at 8K does not
change these compile-time policy keys.

The six target-only phase/mode rows reduce to four unique tuples:

| Phase | Attention | Incoming causal | Effective policy tuple | Before this run |
|---|---|---:|---|---|
| prefill | full | true | `128,true,true,false,false,false` | present |
| prefill | sliding 512 | true | `128,true,false,true,false,false` | **missing** |
| chunk-prefill | full | true | `128,true,true,false,false,false` | present |
| chunk-prefill | sliding 512 | true | `128,true,false,true,false,false` | **missing** |
| decode | full | forced false | `8,128,64,false,false,false` | present |
| decode | sliding 512 | forced false | `16,128,64,false,true,false` | present from `09960db2` |

The chunk tuple schema is
`head_dim,is_paged,is_causal,is_local,is_sink,is_lse`; the decode schema is
`q_group_bucket,head_dim,page_size,is_causal,is_local,is_sink`.

Both pure prefill and mixed/chunk-prefill enter the paged chunk interface.
`fmha_xe2.cpp` normalizes causal+local to effective
`is_causal=false,is_local=true`; decode is dispatched with causal false.
There is no separate non-paged prefill tuple in this vLLM route.

The later DFlash load exposed one additional DFlash-only tuple that the
target-only enumeration missed:

- `16,128,64,false,false,false` — **not compiled**.

Its dispatch path is the DFlash parallel drafter's non-causal attention:
`DFlashProposer._create_draft_vllm_config(use_non_causal=True)` and
`set_inputs_first_pass(causal=False)` -> vLLM `FlashAttentionImpl` ->
`vllm_xpu_kernels.flash_attn_interface.flash_attn_varlen_func` with paged KV
and no local window -> `_vllm_fa2_C.varlen_fwd` ->
`cutlass_paged_decode_interface` -> `cutlass_paged_decode_xe2` ->
`dispatch_by_page_size` / `dispatch_by_head_size`. The six-layer draft has
72Q/8KV, hence 18Q/2KV under TP4 and q-group bucket 16. All 25,536 logged
fallback notices named this same tuple; no other missing tuple appeared.

This is explicitly a failure of the original “full set” enumeration. Per the
one-build constraint, it was recorded and not followed by a second kernel
rebuild.

## Kernel edit, build, and four-card gate

- Kernel branch: `experiment/laguna-s-2.1-fwht-20260721`.
- Source commit: `bcfde2d06362d7ca64d56fc89415f0acbacf9035`
  (`attn: compile Laguna sliding prefill shape`).
- Added to `chunk_prefill_default.conf`:
  `128,true,false,true,false,false`.
- Toolchain: oneAPI compiler 2025.3 (`icx`/`icpx`), Release, XE2, FA2 only.
- Valid build compiled the generated head128 and head128_b16
  `tfftf` translation units and relinked the attention library.
- Build log:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-vllm-fa2-laguna-bcfde2d-20260721.log`
- Build-log SHA256:
  `70fc13d47cbca7a33a012b326d195f71196f9de6e7513432c2adb431be9d33dd`.
- Installed wrapper `_vllm_fa2_C.abi3.so` SHA256:
  `e6faed930bbcd7a366cc55281b99e1a8d7016a8db40ab10015d78f72937c8e64`.
- Installed payload `libattn_kernels_xe_2.so` SHA256:
  `2091f7f40c5480360fb6ab2821d44575c2ab14dcbc1b07eb06df71eb6afc0103`.

The Python wrapper did not change; the payload library is the binary carrying
the new instantiated policies. An initial incremental build only relinked the
stale generated source list. Inspection caught that the new trait was absent,
so that binary was rejected before installation or model loading. CMake was
then explicitly regenerated, the trait and generated sources were verified,
and the valid policy build above was performed once.

`gate_laguna_attention_tuples.py` independently exercised all six target rows
against a CPU FP32 bottom-right GQA/masking reference with changed seeds and
hashes, the reference fallback patched to hard-fail, and exactly one visible
XPU per process. Results:

| Card | Cases | Result | Worst max abs error | Artifact SHA256 |
|---:|---:|---|---:|---|
| 0 | 6 | PASS | 0.0078125 | `8c13b8ceed50c40413deeca6db3402b74f6dfe896bb0c0f7b0659e20dce6b156` |
| 1 | 6 | PASS | 0.0078125 | `a35e9ff4324bd6100a4dc5960ccb8dfcacc46486052ee99678ee5020537002c4` |
| 2 | 6 | PASS | 0.0156250 | `6762d71223f93d860911ad5d115e7111cfde5d095d78d4c58c39d5b6ce04272d` |
| 3 | 6 | PASS | 0.0156250 | `899476b7a2f25e49cbafdb5330b0a873caf04476a89fd154c1062311be030312` |

Artifacts are
`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/attention-all-tuples-gate-card{0,1,2,3}-bcfde2d-20260721.json`.

## Tokenizer repair and verification

The serving tokenizer registry at vLLM `024672b34` already passed
`fix_mistral_regex=True`. The remaining warning came from the secondary
AutoProcessor chat-template probe in `vllm/renderers/hf.py`. vLLM commit
`e0e56c7e81780ae413c5e22549dcb208d65440aa` now carries the flag through that
Laguna-only path and includes it in the processor-template cache key.

Verification:

- six plain strings covered camel/snake case, contractions, Unicode, emoji,
  multiline CRLF, Python syntax, and `/東京.\n/_`;
- three rendered chat-template probes were also compared;
- vLLM, an independent local `AutoTokenizer(..., fix_mistral_regex=True)`,
  and the live `/tokenize` endpoint returned identical IDs;
- all live `/detokenize` round trips were exact;
- backend tokenizer SHA256 was
  `a6d75cc3b2d9339ed34c7f5a179acea1dabfbb65cd6cb64646504cd0c45bec63`;
- the fixed secondary probe was warning-free.

The broad renderer test file produced 59 passes and four unrelated failures
from gated Hugging Face repositories returning HTTP 401. The local Laguna
probe passed and required no network.

## Target reload and correctness

Both target-only modes reached HTTP ready with TP4+EP4, INT4 WNA16 MoE on XPU,
XCCL ranks 4/4, 8K maximum length, block 64, NHD KV, prefix caching disabled,
and `max_num_seqs=1`.

- Eager: 16.92 GiB weights and 8.36-8.37 GiB KV/card; `xpu-smi` total
  27,498,680-27,502,028 KiB on the worker-owning card.
- PIECEWISE: 16.92 GiB weights, 8.22 GiB KV/card, 0.01 GiB graph memory;
  `xpu-smi` total 27,351,980-27,357,468 KiB.

Correctness evidence:

- eager greedy repeat: 3/3 identical 128-token ID sequences and output SHA256
  `88b6c39e1a3a25a1ad4444dfeff11fadb9e6a7797c6e8ae056eff1fa8a19a812`,
  with `cached_tokens=0` each time;
- PIECEWISE repeat: 2/2 identical 128-token sequences and output SHA256
  `3cbc81f50904f52b71116e61d1570935e6062b6754f07f7d3fd07ef3294f4f1b`,
  cache-zero each time;
- PIECEWISE does not have eager parity: first token-ID divergence is output
  index 29 (`350` eager versus `268` graph). Both streams are coherent, but
  this remains a correctness caveat for future graph work;
- coding prompts produced coherent Python interval/mean implementations and a
  correct deterministic PostgreSQL latest-row plan; several 192-token replies
  ended at the output cap, so the strict completeness heuristic did not pass;
- factual canary correctly identified Ottawa/Ontario versus Toronto;
- concise arithmetic returned exactly
  `137*29=3973; minus 845=3128; divide by 23 gives quotient 136 remainder 0.`;
- no token-like garbage reappeared.

Thus token integrity, greedy within-mode determinism, factual/arithmetic, and
coherence pass. The bounded code-answer completeness gate and cross-mode exact
parity do not pass and must not be overstated.

## Nonspec measurements

The fixed six-prompt suite is
`experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json`. Each unique prompt
ran once with thinking disabled, temperature 0, 128 output tokens, token-ID
stream timing, no prefix cache, and `cached_tokens=0`.

- Eager summary:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/target-eager-20260721b/bench.json`
  (SHA256 `9f579120e6c98b5436d7220721486fc282cfb03cbec77b514517c39249416fb7`).
- PIECEWISE summary:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/target-piecewise-igc-noopt-20260722/bench.json`
  (SHA256 `d8056e8e0c26f7444c17ae6fb6aaf5356e2a8fdc5035b3fa5994f57d940b2688`).

Two earlier PIECEWISE compile attempts hit oneAPI IGC floating-point
exceptions from `ocloc` exit 245: first on a generated FP32 128-wide RMS
reduction, then on `triton_red_fused_mm_mul_silu_t_9` with a 3072 reduction,
both using `-cl-intel-256-GRF-per-thread`. The successful launch set
`TRITON_INTEL_DISABLE_IGC_OPT=1`, loaded the AOT artifacts retained by the
custom-op attempt, and captured PIECEWISE M=1. This establishes a reproduction
recipe, not a clean attribution; a cold cache rebuild still needs validation.

## DFlash diagnostic and remaining blocker

The draft loaded all six layers and logged auxiliary IDs
`(2,11,20,30,39,48)`, corresponding to target layer taps
`(1,10,19,29,38,47)`. Configuration was depth 7,
`draft_sample_method=greedy`, target rejection sampling, eager target/draft,
one active request, and no synthetic acceptance.

Every decode step missed `16,128,64,false,false,false` and used the PyTorch
reference attention fallback. The suite still passed freshness and cache-zero
checks, but its speed is diagnostic only. Worse, its exact counters show zero
accepted tokens. Evidence:

- summary:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-eager-m7-20260722/bench.json`
  (SHA256 `8b6af0547358911c5905658795470bc67c8ef5c3f80003cefc94d06933a30820`);
- counter interval: `metrics-prebench.txt` -> `metrics-postbench.txt` in the
  same run directory;
- server log: `server.log` in the same run directory.

Do not treat 11.414684 tok/s as a DFlash baseline suitable for comparison.
The next rebuild must include the DFlash non-local q-group-16 tuple, and draft
logit/token-map correctness must be investigated before another performance
claim.

## Commits and preserved state

- XPU kernels: `bcfde2d06362d7ca64d56fc89415f0acbacf9035`.
- vLLM tokenizer path: `e0e56c7e81780ae413c5e22549dcb208d65440aa`.
- Lab gate harness: `f4f945b5d7379c1867fa5f79ab86de409eea3530`.
- Lab result/harness commit: recorded after this note.

DeepSeek `option4-decoder` and all `preserve/*` tags were not modified. At
postflight port 18080 was closed, no vLLM/EngineCore/worker remained, and all
four B70s showed only the transient `xpu-smi` process.

## Top two optimization targets

1. Compile and gate `16,128,64,false,false,false`, then diagnose DFlash's
   `0/5,334` acceptance before tuning depth or graphs. The likely audit surface
   is its non-causal/full-window draft attention and target/draft token/logit
   alignment.
2. Reduce the target's 47-layer sparse-MoE/EP launch and collective overhead,
   while making the M=1 PIECEWISE build cold-cache reliable. Even the graph is
   below 5% of the bandwidth roofline, so WNA16 MoE dispatch, all-gather /
   reduce-scatter, and graph segmentation dominate the opportunity.
