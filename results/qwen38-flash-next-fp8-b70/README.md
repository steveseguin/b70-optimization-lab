# Qwen3.8 Flash-Next FP8 on four Arc Pro B70s

Status: **research screen; not deployment-qualified**

Last updated: 2026-08-27

This packet covers the first instrumentation-free TP4/EP4 server results for the official
Qwen3.8 Flash-Next FP8 export on four 32-GiB Intel Arc Pro B70 cards. It proves
that the exact checkpoint and maintained XPU overlay can load, profile, become
healthy, serve cache-zero MTP0 context through a formal exact-8K screen, and
run matched MTP1/512 and MTP3/512 research screens at 9.372 and 14.889 tok/s.
The MTP3 rows were variable and remain a bounded screen, not a stable ceiling. It
does not yet establish a production recipe, a fully quality-qualified speed,
stable repeated serving at 8K, 16K+ behavior, or vision support.

## Measured point

The exact attempt-19 identity was text-only, TP4 + EP4, eager/graph-off, MTP0,
automatic KV precision, prefix caching disabled, and a configured maximum
length of 512 tokens. Three sequential single-request samples used one
repetitive 146-token prompt and forced 256 output tokens:

| Sample | Output tok/s after first text | Wall output tok/s | TTFT |
| --- | ---: | ---: | ---: |
| 1 | 5.142647219 | 4.449694512 | 7.752230 s |
| 2 | 5.221849709 | 4.705774975 | 5.376468 s |
| 3 | 5.289933931 | 4.836666254 | 4.535220 s |

The median after-first-text rate is **5.221849709 tok/s**. All three requests
completed 256 tokens with the same output hash. This is a narrow research
speed screen, not the lab's conventional realistic-suite 99-interval metric
and not an optimized ceiling; the runtime reported that no model-specific MoE
tuning table was available.

## Quality boundary

Two short batteries each passed 5/7 strict cases. Exact response, copy,
arithmetic, JSON, and factual cases passed. The logic case differed only by
case (`Yes` instead of `yes`), while the range-expression case substantively
returned `30` instead of `14`. The first eight-repeat battery contained one
different valid-looking four-color selection; the second was 8/8 stable, for
15/16 majority stability overall. All 30 quality requests reported zero cached
tokens.

These results fail the full-quality and repeat-determinism gates. The measured
speed must not be submitted as a record, promoted as deployment-ready, or used
to lower any prior captured result.

## Exact identity

- Base model family: `Qwen/Qwen3.8-Flash-Next`.
- Quantized child artifact: `Qwen/Qwen3.8-Flash-Next-FP8` at
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
- Artifact tree: 144 files, 131 safetensor shards, 185,563,783,127 bytes,
  152,089 indexed tensors, tree SHA-256
  `4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2`.
- vLLM source: `658965050f259999e635b52a850004a3771cd644`.
- vLLM XPU-kernel source: `2f829747503c77d4814834dffd0840fb1dd9f75a`.
- Runtime stage:
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`.
- Selective UVA placement: PLE n-gram embedding plus input embedding,
  12.22 GiB reported per rank.
- Cache: block-outermost `BLHNC`, fixed 192 MiB, 1,536 tokens available.
- Diagnostics: none.

Installed-package version strings are stale metadata for this source-overlay
run. The Git identities and staged-binary hashes in the retained evidence are
authoritative.

## Evidence and remaining work

The compact receipt is
[`20260827-tp4-attempt19-production-qualification.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-attempt19-production-qualification.json).
The full bring-up chronology is in the
[`XPU overlay and preload ledger`](../../experiments/qwen38-flash-next-fp8-b70/notes/2026-08-26-xpu-overlay-preload-gates.md),
and the source series is documented in the
[`patch packet`](../../patches/qwen38-flash-next-fp8-b70/README.md).

The next service-shaped context point is TP4/MTP3 at configured maximum 4,352,
covering up to a 4,096-token prompt plus 256 output tokens with a separately
sized fixed cache. The 16K/24K/32K MTP0 expansion is deferred while the 8K
repeated-serving boundary remains unresolved. TP1 and TP2 require a separate
fit/offload design. MTP1/512 and MTP3/512 are separately screened below;
deeper MTP1/MTP3 plus MTP2 and MTP4 remain gaps. Graph,
deeper context, vision,
fresh-server determinism, full quality, clean-host replay, and a sealed
deployment package remain explicit gaps.

## Matched TP4 MTP1 screen

The additive MTP1 arm uses vLLM source `1372c62d975c554f4b465c8299bc5f3295301ceb`
with the same preserved staged XPU runtime built from kernel source `2f829747`.
It adds one native MTP draft token while retaining TP4/EP4, eager/graph-off,
configured maximum 512, automatic KV precision, fixed 192-MiB cache, disabled
prefix caching, and the same selective host placement. The full 51B FP8
n-gram embedding is resident as four host-RAM TP shards and remains
GPU-addressable through UVA; it is not streamed from the USB checkpoint during
decode.

An audit found that the earlier apparent MTP1 parity failure had omitted the
baseline's `enable_thinking=false` chat-template setting. With that setting
restored, the unchanged preserved-runtime MTP1 arm matched all 26 MTP0 baseline
comparisons, repeated one exact hash 16/16 times, passed the small cache-zero
needle, and reported zero cached/created-cache tokens on all 24 quality
requests. The inherited short boundary remains 5/7, so this is Grade-C research
evidence rather than deployment qualification.

Three matched p146/o256/c1 rows measured `9.773840621`, `9.372254368`, and
`8.107468408 tok/s` after first text, median **`9.372254368 tok/s`**. Every row
returned all 256 tokens with the MTP0 target hash. The median is 79.48% above
the separate MTP0 `5.221849709 tok/s` control. Cumulative metrics accepted
503/505 draft tokens. MTP0 remains the packet's primary historical cell; MTP1
is a separate matrix result and does not replace it. Receipt:
[`20260827-tp4-mtp1-512-attempt3-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp1-512-attempt3-result.json).

## Matched TP4 MTP3 screen

The additive MTP3 arm retains the MTP1 model, source, runtime, TP4/EP4,
eager/graph-off, text-only, host-placement, and client identity. It changes the
speculative depth to three and uses the exact 20-block cache allocation needed
for this configured-512 screen: 235,356,160 bytes (224.453125 MiB) per rank.
The server reported 568 cache tokens and 1.11x maximum concurrency. The same
12.22 GiB per-rank PLE/input-embedding shard remains resident in pinned system
RAM and GPU-addressable through UVA; generation does not stream weights from
the external checkpoint drive.

All 26 bounded MTP0 comparisons matched, the fixed-set repeat held one hash for
16/16 runs, the small cache-zero needle passed at 317 actual prompt tokens, and
all 24 audited quality requests completed with zero cached and created-cache
tokens. This is not a 4K MTP3 result: the needle was deliberately small. The
inherited strict target score also remains 5/7 with the same logic and
range-expression failures, so the evidence grade remains C.

Three p146/o256/c1 rows returned all 256 tokens with the MTP0 target hash at
`17.473320852`, `14.888789794`, and `12.538688913 tok/s` after first text,
median **`14.888789794 tok/s`**. Their wall-rate median was `9.011438903 tok/s`
and TTFT median was `11.817638450 s`. The cumulative endpoint reported 768/768
draft tokens accepted, 256 at each draft position, proving that MTP3 was
engaged. It is not per-row acceptance evidence.

The three decode observations declined monotonically and span 33.14% of the
median. The median is therefore a research screen, not a stable ceiling or
record. It is descriptively 185.12% above the separate MTP0 screen and 58.86%
above the separate MTP1 screen, but those cross-run differences are not a
same-window causal A/B. MTP0 remains the packet primary and MTP1 remains an
unchanged matrix cell. Receipt:
[`20260827-tp4-mtp3-512-attempt4-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-512-attempt4-result.json).

## Additive 1K context screen

The same exact production source/runtime later served with a configured
1,536-token maximum while retaining the 192-MiB cache allocation. It reported
3,949 available cache tokens, passed the exact needle at 987 actual prompt
tokens, held 16/16 repeats to one hash, and completed the 12-prompt realistic
suite with zero cached tokens. The preferred realistic-suite median was
`4.449168445 tok/s` over 99 inter-token intervals; three unique exact-1,024
prompt + 256 output screens had a median of `5.133587561 tok/s` after first
text and `29.043115 s` median TTFT.

The same two short-suite failures remained, so this is another research-only
cell, not a deployment promotion. See the
[`1K context receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-1536-context-screen.json).

## Quarantined 2K context screen

The additive configured-3,072 arm again kept the exact production source,
runtime, placement, and 192-MiB cache identity. It reported 6,144 cache tokens
and passed the exact needle at 2,048 server prompt tokens. The short battery
matched the prior outputs and all 24 requests were cache-zero.

One of 16 repeats returned a different four-color list. The preregistered stop
gate therefore blocked the formal exact-depth and comparative speed requests.
This closes the 2K combination as a quarantined capability result, not a speed
measurement; the 512 and 1K rates above are unchanged. See the
[`2K bounded-negative receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-3072-context-screen.json).

## Repeat-v2 2K screen

The quarantined arm exposed a flaw in the old canary: it asked the model to
invent any four colors, and both observed lists obeyed the instruction. A
prescribed-set retry retained that raw result and changed no server setting.
The old prompt's returned `blue`/`black` margin was only 0.125-0.375; fixing the
input set widened it to 9.19-10.19 and produced 32/32 stable first tokens plus
16/16 exact full repeats.

The retry passed the exact cache-zero 2K needle and formal p2048/o128 gate. Its
formal 99-interval rate was `3.864877889 tok/s`; three comparable p2048/o256
screens measured `5.034312884`, `5.257401637`, and `5.228429046 tok/s`, median
`5.228429046 tok/s` after first text. The known 5/7 short boundary remains, so
the 2K selector is research-screened rather than deployment-ready. See the
[`repeat-v2 2K receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-3072-context-repeat-v2-screen.json).

## Exact 4K screen

The additive configured-4,352 arm changed no runtime or performance setting
other than the minimum block-aligned context maximum needed for p4096/o256.
The unchanged fixed cache reported 7,121 tokens. All seven short outputs and
all 16 fixed-set repeats exactly matched the 2K baseline, and the needle passed
at exactly 4,096 server prompt tokens with zero cached and created-cache
tokens.

The formal p4096/o128 cache-zero row passed at `4.456026475 tok/s` on its
99-interval window with `217.909692 s` TTFT. Three separately salted
p4096/o256 legacy comparisons measured `5.298983875`, `5.233664732`, and
`5.161604624 tok/s` after first text, median `5.233664732 tok/s`; their median
TTFT was `123.391275 s`. The site graph labels those legacy-comparable values
separately from the formal rate. Short quality remains 5/7, so the cell is
research-screened, not deployment-ready. See the
[`exact-4K receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-4352-context-screen.json).

## Exact 8K formal screen and stability boundary

The additive configured-8,448 arm again retained the exact source, runtime,
placement, eager/MTP0 identity, and fixed 192-MiB cache. It reported 9,504
cache tokens. All seven short outputs matched the 4K baseline, fixed-set
repeats were 16/16 identical, and the exact 8K needle passed cache-zero.

The formal p8192/o128 row completed with 128 token IDs at `3.979729240 tok/s`
on its 99-interval window and `386.534332 s` TTFT. Two secondary p8192/o256
rows completed at `5.170404147` and `5.182352526 tok/s` after first text with
the same output hash. The runtime stopped during the required third comparison,
so those two observations have no authorized median and the legacy context
curve intentionally stops at 4K. The comparison helper now fails closed on
this class of incomplete response in commit `08a865143`.

This fills the formal exact-8K capability cell as research-screened evidence,
but repeated-serving stability, full short quality, and deployment promotion
failed. See the
[`exact-8K receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-8448-context-screen.json).
