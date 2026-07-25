# Laguna persistent KV-cache views preregistration

Date: 2026-07-25 America/Toronto

Status: preregistered before implementation. No candidate source, XPU
diagnostic, model load, prompt, generation, endpoint campaign, payload, or
submission has started.

## Hypothesis

Each of Laguna's 48 piecewise eager attention boundaries currently recreates
the same KV-cache aliases in `FlashAttentionImpl.forward`:

```text
kv_cache.transpose(1, 2).split(head_size, dim=-1)
```

It then runs singleton-stride canonicalization on both aliases. The preceding
KV-cache update recreates the raw aliases again. These are host-side view
operations over a fixed-address cache; they do not read or change KV data.

The candidate stores the raw key/value aliases and their canonicalized
forward aliases once per `FlashAttentionImpl`, then returns those same aliases
only while a full source-and-view identity contract remains unchanged.
Attention kernels, KV writes, cache contents, BF16 arithmetic, query/key/value
inputs, metadata, graph segments, and every model operation remain identical.

## Measured ceiling

A CPU-only microbenchmark on this host used a representative BF16 cache shape
`[256,2,16,256]` and 31 repeated measurements:

- 48 uncached transpose/split/canonicalize preparations:
  `0.190186 ms` median;
- 48 cached tuple accesses: `0.004592 ms` median; and
- raw forward-only saving ceiling: `0.185595 ms`.

The update path repeats transpose/split, so the generous raw ceiling is about
`0.37 ms` per 48-layer target cycle. A deliberately conservative full
source-plus-view signature check measured about `0.272467 ms` for 96 helper
calls, leaving an expected net opportunity near `0.10 ms`. These CPU
measurements authorize implementation only; they are not XPU, endpoint, or
record evidence.

The latest exact replay diagnostic measured about `21.137799 ms` whole replay.
The absolute hard ceiling is therefore below 1.8%, while a realistic endpoint
effect is expected to be roughly 0-0.5% after host/device overlap.

## Frozen identity

Implementation starts from:

- main repository:
  `60e4a0a38`;
- vLLM:
  `ef334233deabeaeedb607056a2db1c90edb3887c`;
- record XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- installed record grouped-GEMM SHA-256:
  `fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`; and
- matched DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`.

The approved record remains `94.92003934159611 tok/s`,
LocalMaxxing `cmrzrd4tf001ipa013xpx4kid`.

Before any XPU diagnostic, use a clean kernel source worktree at the exact
record commit. The closed N32 source commit and candidate binary are not part
of this experiment.

All model, source, binary, cache, temporary, log, run, and evidence paths must
stay on internal NVMe/ext4. The external USB is backup-only.

## Sole treatment

Control:

```text
VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS=0
```

Candidate:

```text
VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS=1
```

The flag is default off. When enabled it is valid only for the frozen Laguna
exact graph contract: XPU decoder attention, BF16 cache tensor, head size 128,
two local KV heads, one fixed cache layout, exact speculative attention, and
the audited M=8 Breakable graph stack. Any contract mismatch must raise before
the candidate can silently fall back.

No kernel build, op schema, tensor allocation, model arithmetic, attention
argument, graph topology, DFlash policy, collective, or benchmark setting may
change.

## Fail-closed cache contract

The first eligible cache use may build:

- raw key and value aliases from the incumbent transpose/split expression;
- canonicalized key and value aliases using the incumbent helper; and
- immutable source, raw-view, canonical-view, and object-identity signatures.

Every later use must validate:

- source data pointer, storage offset, shape, stride, dtype, and device;
- configured head size and split width;
- cached raw/canonical view object identities;
- every cached view's data pointer, storage offset, shape, stride, dtype, and
  device; and
- exact expected alias offsets between key and value.

Any source pointer/layout change, cached view replacement, in-place view
metadata change, wrong dtype/device/head geometry, or partial cache state must
raise. It may not rebuild or fall back after initialization. Flag-off behavior
must remain byte-for-byte on the incumbent preparation path.

The update path must receive the raw aliases; the attention forward path must
receive the canonical aliases. Quantized KV reinterpretation remains after
the helper exactly where it is today and is outside the frozen BF16 candidate
contract.

## Gate 1: CPU/static

Before any XPU use:

- default-off and strict flag parsing tests pass;
- stable repeated calls return the identical cached alias objects;
- candidate aliases have the same raw bits, shapes, strides, offsets, dtype,
  device, and storage as independently computed incumbent aliases;
- source pointer/storage/shape/stride/dtype/device drift is rejected;
- raw and canonical cached-view object or metadata drift is rejected;
- partial cache state is rejected;
- wrong head geometry, KV heads, attention type, dtype, device, and ineligible
  selector combinations are rejected;
- update selects raw aliases and forward selects canonical aliases; and
- flag-off calls the original view construction with no cache state.

Focused pytest, Ruff, formatting, whitespace, and an independent code review
must pass.

## Gate 2: exact diagnostic

Only Gate 1 authorizes a fresh, no-promotion diagnostic on all four physical
B70s. It must compare the current record control against the candidate and
require:

- one fresh q1 teacher, eager DFlash, and graph DFlash request;
- complete bitwise token identity across q1/eager/graph;
- `cached_tokens=0`;
- unchanged DFlash depth and bounded acceptance;
- q2 through q8 attention output parity;
- unchanged 146-graph/145-break topology with exactly 48 attention and 97
  collective boundaries on every rank;
- exact source, binary, model, environment, and flag identity; and
- 31 replay-profile samples per rank.

Profile both KV-view preparation and whole replay. Promotion requires a
positive median whole-replay saving on the maximum rank, a positive fresh
generation-wall effect, no p90 instability, and no transfer of the apparent
host saving into post-replay synchronization. Host-only improvement is not
enough.

## Gate 3: endpoint boundary

Only a clean diagnostic win may authorize a separately constructed, audited,
and committed graph-vs-graph A1-B1-B2-A2 endpoint protocol. It must retain the
existing 13 unique cold prompts, canonical-q1 exactness, cache-zero, long-next,
rollover, no-retry, no-warmup, single-generation, acceptance-drift, cleanup,
and adjacent-pair causal gates.

Only the lower candidate start may be promoted, and only if it is strictly
above `94.92003934159611 tok/s`. No diagnostic result is submit-worthy.
