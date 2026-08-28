# Qwen3.8 Flash-Next FP8 on four Arc Pro B70s

Status: **research screen; not deployment-qualified**

Last updated: 2026-08-28

This packet covers the first instrumentation-free TP4/EP4 server results for the official
Qwen3.8 Flash-Next FP8 export on four 32-GiB Intel Arc Pro B70 cards. It proves
that the exact checkpoint and maintained XPU overlay can load, profile, become
healthy, serve cache-zero MTP0 context through a formal exact-8K screen, and
run matched MTP1-4 configured-512 research screens at 9.372, 11.895, 14.889,
and 20.727 tok/s. It also qualifies 32-block MTP1/MTP2 recipes and MTP3 at
exact 4K, with `8.904`, `9.893`, and `15.502 tok/s` decode medians respectively.
MTP3 remains the preferred 4K recipe because it also has lower TTFT and higher
wall output. These rows remain bounded screens, not stable ceilings. The packet
now classifies all 25 cells in the practical TP4 eager-text MTP/context slice:
12 screened and 13 quarantined, with no blank practical cell. MTP1, MTP2, and
MTP4 completed exact active-8K requests under scoped cross-runtime parity
quarantines, while MTP3 reached its fixed 8K bound without a completed receipt.
It also includes a target-only official-thinking quality profile that passed
25/25 preregistered responses. Later MTP1 1K and 2K arms passed every boot and
admission gate but stopped on their first requests without returning output.
An MTP2 active-1K arm then returned the exact frozen target twice with zero
cache reuse and perfect two-position acceptance, but corrected local-NVMe
events after the frozen cutoff failed its strict clean-host gate. Those three
cells are quarantined. A later MTP3 active-1K boot passed every startup gate
but received an external SIGTERM during request one, leaving no completed
response or speed; it is separately quarantined. The MTP4 active-1K arm then
passed both exact target-parity requests with perfect four-position acceptance,
but its detached supervisor failed to forward the exact stop to the server
group; the frozen teardown gate quarantines its diagnostic 13.326 and 17.291
tok/s observations. All configured-512 and
exact-4K passes remain unchanged. It does not yet establish a production recipe, a fully quality-
qualified MTP speed, stable repeated serving at 8K, 16K+ behavior, or vision
support.

The retained current runtime has now also passed an independent additive MTP0
anchor at short context and exact active 4K. It measured `5.223789 tok/s` on
the established short screen and `4.757818 tok/s` conventional at exact 4K,
while passing 6/7 semantic quality, 16/16 repeats, an exact cache-zero 4K
needle, and card-clean teardown. This closes two current-runtime website cells;
it does not replace the legacy-runtime rows or establish clean-host,
fresh-server, graph, vision, or deployment qualification.

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

## Current-runtime MTP0 anchor

The additive attempt-4 profile used vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`,
XPU-kernel source `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, and
the preserved staged runtime built at `2f829747503c77d4814834dffd0840fb1dd9f75a`.
It retained TP4/EP4, eager graph-off, MTP0, automatic KV precision, disabled
prefix caching, and selective host placement, with a configured maximum of
4,352 tokens and 201,326,592 cache bytes.

The fresh four-rank preflight and exact cache-zero `OK` recovery canary passed.
The direct battery passed 6/7 with only the known `30` versus `14` miss,
repeated one hash 16/16 times, and passed the exact cache-zero 4K needle. Three
established p146/o256/c1 rows measured `5.315578`, `5.223789`, and
`5.219405 tok/s` after first text, median **`5.223789 tok/s`**. The short
harness does not retain per-row cache detail or finish reason, so neither is
claimed.

Two exact p4096/o128 rows then measured `4.720311` and `4.795325 tok/s` under
conventional 99-interval accounting, median **`4.757818 tok/s`**. TTFT was
`149.330` and `145.607 s`; both responses returned exact 4096/128/4224 usage,
zero cached tokens, length stops, 128 token IDs, and one output-token hash. The
hash matches the retained legacy target-only authority. Client and supervisor
both exited zero, all four cards returned below 43 MiB, and no B70-addressed
event appeared. This is same-boot Grade-C evidence, not clean-host or
deployment qualification. Receipt:
[`20260828-tp4-mtp0-current-runtime-anchor-attempt4-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp0-current-runtime-anchor-attempt4-result.json).

## Quality profiles

The historical direct-answer batteries passed 5/7 literal cases. Exact response, copy,
arithmetic, JSON, and factual cases passed. The logic case differed only by
case (`Yes` instead of `yes`), while the range-expression case substantively
returned `30` instead of `14`. The first eight-repeat battery contained one
different valid-looking four-color selection; the second was 8/8 stable, for
15/16 majority stability overall. All 30 quality requests reported zero cached
tokens.

The corrected semantic reading is therefore 6/7, not 5/7: `Yes` is correct.
The later sealed exact-4K deterministic control matched all 26 baseline
comparisons, repeated 16/16 with one hash, returned the exact 4,096-token
needle, and kept all 24 cache observations at zero. Its sole semantic miss was
still `30` rather than `14`.

A separate target-only profile then used Qwen's published thinking sampler,
`reasoning_effort=xhigh`, and the `qwen3` reasoning parser. The four-case scout
passed 4/4, followed by all seven cases at three frozen seeds, 21/21. Every one
of the 25 responses exposed nonempty separated reasoning and final fields,
stopped normally, had complete usage accounting, and reported zero cached and
created-cache tokens. The code expression returned `14` in all four
appearances. This qualifies the official target quality profile; it does not
retroactively quality-certify or replace the non-thinking MTP speed rows.

The measured speed remains a bounded research screen and must not be promoted
as deployment-ready or used to lower any prior captured result. The quality
receipt is
[`20260827-tp4-mtp0-official-quality-attempt2-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-official-quality-attempt2-result.json).

The preregistered MTP3 transfer arm passed its local-NVMe boot and the complete
deterministic control. Its official-thinking battery then passed the 4/4 scout
and 15 of 21 grid rows: all 19 completed responses passed semantic,
structural, usage, and cache-zero gates, and all 19 final answers exactly
matched MTP0. The next `copy_phrase` request, seed `2026082713`, stopped at 98
computed and 33 output tokens; the fixed 300-second worker-response timeout
ended in API 500. The six remaining rows did not run. Official MTP3 quality is
therefore **inconclusive and unqualified due to repeated-session stability**,
with no answer-quality failure observed. No timing result changed. Receipt:
[`20260827-tp4-mtp3-official-quality-attempt2-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-official-quality-attempt2-result.json).

## Exact identity

- Base model family: `Qwen/Qwen3.8-Flash-Next`.
- Quantized child artifact: `Qwen/Qwen3.8-Flash-Next-FP8` at
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
- Artifact tree: 144 files, 131 safetensor shards, 185,563,783,127 bytes,
  152,089 indexed tensors, tree SHA-256
  `4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2`.
- Retained legacy MTP0 vLLM source: `658965050f259999e635b52a850004a3771cd644`.
- Current MTP0 and MTP1-4 vLLM source: `1372c62d975c554f4b465c8299bc5f3295301ceb`.
- Current XPU-kernel source: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
  the staged runtime used here was built at
  `2f829747503c77d4814834dffd0840fb1dd9f75a`.
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

The service-shaped TP4/MTP3 configured-4,352 point now passes exact 4K parity,
formal depth, and three p4096/o256 rows. Its TTFT and wall-rate tradeoff, plus
fresh-boot stability, remain production work. The 16K/24K/32K MTP0 expansion
is deferred while the 8K repeated-serving boundary remains unresolved. TP1
and TP2 require a separate fit/offload design. The complete configured-512
MTP1-4 grid and exact-4K MTP1/MTP2/MTP3 cells are separately screened below;
MTP4 at exact 4K and MTP1 at active 1K and 2K are quarantined for separate
stopped-request events. MTP2 active-1K is separately quarantined only because
the local-NVMe lane failed the strict clean-host gate after two otherwise exact
requests. Active-8K MTP1, MTP2, and MTP4 are separately quarantined against
the frozen cross-runtime/cache MTP0 authority; the MTP3 active-8K arm retained
no completed receipt. Target-only official-thinking quality now passes. The
first MTP3 transfer attempt returned 19/19 correct completed answers but is
unqualified after a repeated-session runtime stop; graph, deeper context,
vision, fresh-server determinism, clean-host replay, and a sealed deployment
package remain explicit gaps.

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

## Matched TP4 MTP2 screen

The configured-512 MTP2 arm preserves the MTP1 source/runtime and selective
host placement while changing only native speculative depth and its proven
cache requirement. Its 201,326,592-byte fixed allocation resolved to 17 usable
current-source blocks with 1,273,856 bytes left over, and reported 621 cache
tokens at 1.21x concurrency.

All 26 sealed MTP0 comparisons matched, fixed-set repeats held one hash for
16/16 runs, the small cache-zero needle passed, and all 24 audited usages were
complete. The inherited strict target score remains 5/7. Three p146/o256/c1
rows returned the target hash at `13.586500712`, `10.064084892`, and
`11.895061403 tok/s`, median **`11.895061403 tok/s`** after first text. Median
end-to-end output was `7.804965165 tok/s`, median TTFT was `11.278097242 s`,
and cumulative counters accepted 770/770 draft tokens across both positions.

The rows span 29.61% of the median. Comparisons with other depth cells are
therefore descriptive cross-run evidence rather than same-window causal A/Bs.
This closes only TP4/eager/MTP2/configured-512 as Grade C; it does not establish
MTP2 4K or deployment readiness. Receipt:
[`20260827-tp4-mtp2-512-attempt1-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp2-512-attempt1-result.json).

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

## Matched TP4 MTP4 screen

The configured-512 MTP4 arm keeps the exact MTP3 source, staged runtime,
TP4/EP4 eager path, selective host placement, and client identity. Its fixed
282,427,392-byte allocation resolves to exactly 24 current-source cache blocks,
reporting 558 tokens and 1.09x maximum concurrency. The 51B PLE/input-embedding
shards remain resident in pinned system RAM during service.

All 26 bounded MTP0 comparisons matched, fixed-set repeats held one hash for
16/16 runs, the small cache-zero needle passed at 317 actual prompt tokens, and
all 24 audited quality requests completed. The inherited strict score remains
5/7, so the evidence grade remains C and this does not establish MTP4 at 4K.

Three corrected p146/o256/c1 rows returned the MTP0 target hash at
`21.119694109`, `18.576248605`, and `20.727176372 tok/s`, median
**`20.727176372 tok/s`** after first text. Median wall output was
`11.560326763 tok/s`, median TTFT was `10.023315082 s`, and the rows span
12.27% of the median. Cumulative metrics accepted all 1,716 draft tokens, 429
at each of four positions. The 39.21% descriptive uplift over MTP3/512 is
cross-run evidence, not a causal same-window A/B.

The first timing loop used one literal result filename, retaining only its
last row. That surviving JSON and log are preserved and checksummed; the
identical three-row workload was rerun with distinct filenames without changing
the service. Receipt:
[`20260827-tp4-mtp4-512-attempt1-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp4-512-attempt1-result.json).

## Exact 4K TP4 MTP1 headroom screen

The 4K MTP1 support arm preserves the successful source, staged runtime,
TP4/EP4 eager path, selective host placement, and text client identity. It uses
a configured maximum of 4,352 and an exact 32-block cache allocation
(376,569,856 bytes, 359.125 MiB per rank), exposing 9,284 cache tokens and
2.13x reported concurrency. The allocation is 16 blocks above the admission
floor; this screen does not claim that 32 blocks is minimal or that cache
headroom explains the separate MTP2/MTP4 stalls.

All 26 sealed MTP0 comparisons matched, repeats held one hash for 16/16 runs,
the cache-zero needle passed at exactly 4,096 server prompt tokens, and the
formal p4096/o128 row passed all 25 checks at `3.471451019 tok/s` conventional
with `317.104665 s` TTFT. Three p4096/o256/c1 rows then returned all 256 tokens
with the accepted target hash at `8.904420575`, `8.868704697`, and
`9.581812274 tok/s` after first text, median **`8.904420575 tok/s`**. Median
wall output was `0.981050478 tok/s`, median TTFT was `232.079233 s`, and
cumulative counters accepted 528/539 draft tokens.

This is a Grade-C support cell, not a deployment or record result: the target's
inherited strict quality remains 5/7, clean-boot replay is still missing, and
the wall-rate and TTFT rows vary widely. MTP3 remains the preferred exact-4K
recipe at `15.501565 tok/s` decode, `187.899186 s` TTFT, and `1.246260 tok/s`
wall output. Receipt:
[`20260827-tp4-mtp1-4352-headroom32-attempt1-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp1-4352-headroom32-attempt1-result.json).

## Quarantined 1K TP4 MTP1 screen

The separately preregistered active-1K arm retained the successful MTP1
source, staged runtime, TP4/EP4 eager path, selective host placement, and the
same exact 32-block cache allocation used by the passing exact-4K recipe. It
changed the configured maximum to 1,536 and read the 131 checkpoint shards
from the local NVMe model copy. All model/runtime hashes, staged imports,
four-rank collective, per-rank placement, cache admission, capacity, and API
health gates passed. All four ranks completed model loading in about 101
seconds; the server reported 4,468 cache tokens and 2.91x capacity.

The first 1K request reached the unchanged 300-second worker-response gate
during sampling after 768 computed prompt tokens, with zero output tokens and
no response returned. The second request was not sent, and the separate 2K
boot was not launched under the frozen stop rule. Cleanup left no model
process or listener and all four cards were discoverable. The host journal
named no B70 event. Corrected local-NVMe receiver-link events are retained as
host context without assigning causality.

This is a bounded negative, not a performance row. It grants no speed or
quality credit and does not alter either the passing MTP1 512 screen or the
passing exact-4K headroom recipe. The later standalone active-2K arm is
classified separately below.
Receipt:
[`20260828-tp4-mtp1-1536-context-attempt1-bounded-negative.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-1536-context-attempt1-bounded-negative.json).

## Quarantined exact-2K TP4 MTP1 screen

The separately preregistered standalone active-2K arm retained the same
current source, staged runtime, TP4/EP4 eager path, selective host placement,
and 32-block allocation, while using configured maximum 3,072 and the local-
NVMe model. Every source/runtime, four-rank, placement, cache, capacity,
identity, and health gate passed. All four ranks loaded 32.06 GiB in
98.76--99.37 seconds, and the server exposed 7,561 cache tokens / 2.46x
reported capacity.

The first exact-2K exchange had a 2xx HTTP status but a zero-byte completion
body and no output token recorded when the fixed 360-second client bound
expired. The subsequent engine diagnostic showed 448 computed prompt tokens,
64 scheduled next, and zero output. vLLM completed-request, token, and MTP
counters remained zero. The engine independently reported its own
sampling RPC timeout; the evidence does not establish that either timeout
caused the other. Request two was not sent and no speed result exists.

The post-failure teardown window recorded one compute-class and one copy-class
reset on each of the four B70 addresses. No listener or residual model process
remained and all four devices were discoverable afterward, but no post-reset
collective was run. Five corrected NVMe receiver-link events are retained as
non-causal host context. This is a bounded negative with no speed, quality, or
deployment credit. It leaves the passing MTP1 configured-512 and exact-4K
cells and all captured rates unchanged. Any repeat requires a material first-
request completion treatment, a new preregistration, and a fresh four-rank
preflight. Receipt:
[`20260828-tp4-mtp1-3072-context-attempt2-bounded-negative.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-3072-context-attempt2-bounded-negative.json).

## Quarantined active-1K TP4 MTP3 external stop

The preregistered active-1K MTP3 arm used the verified local-NVMe model,
current source, preserved staged runtime, TP4/EP4 eager serving, and the exact
25-block allocation. It passed source/runtime identity, a fresh four-rank
collective, all four 12.22-GiB placement receipts, cache/capacity/identity, and
health. Model loading took 97.56--97.96 seconds per rank and the server exposed
2,021 cache tokens at 1.32x the configured 1,536-token limit.

Request one began under the frozen p1024/o256/cache-zero protocol. At 00:05:06
local time, the server received an external `SIGTERM` before completing the
response. No request JSON, usage, output hash, or performance result exists.
The last partial server metrics showed six drafted and six accepted tokens with
1.000 acceptance at all three positions. Those partial counters are transport
context only and receive no target-parity, speed, quality, or deployment
credit. The evidence does not assign the external signal's source, and request
two was blocked by the preregistered stop rule.

The full window contained one corrected-only NVMe receiver record and no event
naming any B70 address. Shutdown left no listener or model process and all four
cards remained discoverable. This Grade-D quarantine does not lower or replace
MTP3/512, active-2K, exact-4K, or any featured rate. Receipt:
[`20260828-tp4-mtp3-1536-context-attempt1-external-stop.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-1536-context-attempt1-external-stop.json).

## Quarantined active-1K TP4 MTP4 teardown screen

The preregistered active-1K MTP4 arm used the verified local-NVMe model,
current source, preserved staged runtime, TP4/EP4 eager serving, and the exact
29-block allocation. It passed the fresh four-rank collective, all four
12.22-GiB placement receipts, source/runtime identity, cache, capacity, served
model, and health gates. Model loading took 100.11--100.53 seconds per rank and
the server exposed 1,936 cache tokens at 1.26x the configured 1,536-token limit.

Both authorized p1024/o256 requests returned exact 1,024/256 usage, 52 stream
chunks, the frozen MTP0 completion hash, zero cache queries or hits, and
identical text. Each added 51 drafts, 204 draft tokens, and 204 accepted tokens,
split 51/51/51/51 across positions zero through three. Request one observed
`13.326165 tok/s` after first text with `114.399 s` TTFT; the determinism repeat
observed `17.290937 tok/s` with `105.444 s` TTFT.

The attempt nevertheless failed its frozen teardown gate. The exact stop
sentinel ended the `timeout` supervisor with rc 143 without reaching the
already-detached server group. Direct recovery then produced a complete API,
engine, and four-worker shutdown; final checks found no listener or model
process and all four cards idle and discoverable. Seven corrected-only local-
NVMe APEI records, all with zero uncorrected status, also block clean-host
qualification; no event named a B70 address.

Because the preregistration made every teardown mismatch a Grade-D stop, the
cell receives no speed, quality, or deployment credit despite two exact request
passes. It does not lower or replace MTP4/512, MTP4/exact-4K, or any featured
rate. Future detached cells require a separately tested descendant-aware
lifecycle helper. Receipt:
[`20260828-tp4-mtp4-1536-context-attempt1-teardown-quarantine.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-1536-context-attempt1-teardown-quarantine.json).

## Quarantined exact-2K TP4 MTP4 no-output screen

The preregistered MTP4/2K arm retained the verified local-NVMe model,
current-source runtime, TP4/EP4 eager identity, selective placement, and exact
29-block allocation. It passed the fresh four-rank preflight and every startup
gate, exposing 3,563 cache tokens at 1.16x configured concurrency.

The first exact p2048/o128 request reached the fixed 360-second client bound
without producing a receipt. About five seconds later the engine independently
reported its own sampling timeout; the fatal snapshot showed 384 computed
prompt tokens and zero output. No HTTP status, usage, output hash, timing
window, target-parity result, MTP counter delta, or speed exists. Request two
was correctly blocked.

The corrected descendant-aware supervisor returned zero and left no listener,
recorded process, compile path, or RPC path. During that bounded teardown
window, however, the journal recorded one compute- and one copy-class reset on
each B70 plus 60 unsuccessful fault responses. All four cards were rediscovered
at low memory use, but no post-reset collective or known-good generation canary
was run. Seven APEI records separately contained eight corrected local-NVMe
receiver sections; none was fatal or uncorrected.

This is a Grade-D bounded quarantine with no speed, quality, parity,
MTP-acceptance, or deployment credit. It does not alter the MTP4 configured-512
screen, active-1K diagnostics, exact-4K quarantine, or any captured speed.
Receipt:
[`20260828-tp4-mtp4-3072-context-attempt1-bounded-negative.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-3072-context-attempt1-bounded-negative.json).

## Quarantined exact-2K TP4 MTP3 parity screen

The separately preregistered active-2K MTP3 arm retained the accepted source,
staged runtime, TP4/EP4 eager path, selective host placement, and the same exact
25-block allocation used by the passing exact-4K MTP3 recipe. Its local-NVMe
boot passed all source/runtime, four-rank, placement, cache, capacity, identity,
and health gates and reported 3,657 cache tokens.

Request one completed normally with exactly 2,048 prompt tokens, 128 output
tokens, zero cached tokens, a length stop, and a complete 100-event/99-interval
window. MTP3 counters increased by 54 drafts, 162 draft tokens, and 76 accepted
tokens. The generic exact-depth measurement was `5.931661201 tok/s`
conventional with `150.769910 s` TTFT.

The frozen lane-specific oracle nevertheless failed: the returned token-array
hash was `4a56559f49ea6e38b09a24bb7bb2888f81237de4b4cb0acbd9a3fd400d943f71`,
not the sealed MTP0 hash
`5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e`.
The first difference is zero-based generated-token index 4. The preregistered
stop rule therefore blocked request two. The observed rate is diagnostic only:
it receives no speed, quality, or deployment credit and does not change the
passing MTP3 configured-512 or exact-4K results.

This proves a scoped failure of the frozen cross-lane parity gate, not that
MTP3 alone caused the divergence or that the output is universally low quality.
The MTP0 authority used vLLM `658965050`, while this MTP3 arm used `1372c62d`,
and their cache allocations also differ. Controlled shutdown left no listener
or model process and all four cards remained discoverable. Receipt:
[`20260828-tp4-mtp3-3072-context-attempt1-parity-quarantine.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-3072-context-attempt1-parity-quarantine.json).

## Quarantined active-1K TP4 MTP2 clean-host screen

The preregistered active-1K MTP2 arm used the verified model from local NVMe,
the current vLLM source, the preserved staged runtime, TP4/EP4 eager serving,
and the exact 32-block headroom allocation. It passed the fresh four-rank
collective, all four 12.22-GiB placement receipts, cache/capacity/identity
checks, and health. The model loaded in 97.54--97.92 seconds per rank and the
server exposed 3,276 cache tokens.

Both authorized requests returned exactly 1,024 prompt and 256 output tokens,
the frozen MTP0 text hash, zero cached prompt tokens, and identical text. Each
request added 85 drafts, 170 draft tokens, and 170 accepted tokens, split
85/85 across MTP2 positions zero and one. Request one observed
`10.682699 tok/s` after first text with `126.042 s` TTFT; the repeat sentinel
observed `12.641866 tok/s` with `110.997 s` TTFT.

The final journal artifact contained no event naming a B70 address, but it did
contain 11 corrected APEI records for local NVMe `0000:01:00.0` after the
frozen cutoff. The preregistered clean-host rule therefore quarantines this
cell despite its exact transport, parity, determinism, cache-zero, and MTP2
results. Both rates are diagnostic only and do not lower or replace MTP2/512,
active-2K, exact-4K, or any featured rate. Shutdown left no listener or model
process and all four cards remained discoverable. Receipt:
[`20260828-tp4-mtp2-1536-context-attempt1-host-quarantine.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-1536-context-attempt1-host-quarantine.json).

## Quarantined exact-2K TP4 MTP2 parity screen

The successor active-2K arm used native MTP2 and the proven exact 32-block
headroom allocation. Its local-NVMe boot passed all identity, four-rank,
placement, cache, capacity, and health gates and exposed 5,782 cache tokens.
Request one completed with exactly 2,048 prompt and 128 output tokens, zero
cached tokens, a length stop, and a complete 100-event/99-interval window.
Endpoint counters increased by 54 drafts, 108 draft tokens, and 74 accepted
tokens. The generic exact-depth measurement was `4.526752827 tok/s`
conventional with `310.712871 s` TTFT.

The frozen MTP0 token array first diverged at zero-based generated-token index
12, so request two was not sent. The observed rate receives no speed, quality,
or deployment credit and does not lower the passing MTP2 configured-512 or
exact-4K rows. This is cross-lane parity evidence rather than isolated MTP2
causality because the authority used a different vLLM commit and cache
allocation. Controlled shutdown left no listener or model process and all four
cards discoverable. Receipt:
[`20260828-tp4-mtp2-3072-context-attempt1-parity-quarantine.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-3072-context-attempt1-parity-quarantine.json).

## Exact 4K TP4 MTP2 headroom screen

The working MTP2/4K arm preserves the configured-512 source, runtime,
placement, and eager TP4/EP4 identity while using the same exact 32-block
allocation as the MTP1 headroom recipe: 376,569,856 bytes (359.125 MiB) per
rank. It exposes 7,329 cache tokens at 1.68x reported concurrency, 12 blocks
above the MTP2 admission floor. Peak logged cache use was 61.3%.

All 26 sealed MTP0 comparisons matched, fixed-set repeats held one hash for
16/16 runs, the needle passed at exactly 4,096 server prompt tokens, and all 24
quality requests reported zero cached and created-cache tokens. The formal
p4096/o128 fixture passed all 25 checks at `3.479239661 tok/s` conventional
with `369.141154 s` TTFT. The inherited strict score remains 5/7.

Three separately salted p4096/o256/c1 rows, with no harness-added warmups,
returned the accepted target hash at `9.893154792`, `12.078049628`, and
`9.217263500 tok/s` after first text, median **`9.893154792 tok/s`**. Median
TTFT was `263.279224 s`, median wall output was `0.891381690 tok/s`, and
cumulative metrics accepted 719/748 draft tokens (96.12%). MTP3 remains the
preferred exact-4K recipe: MTP2 is 36.18% lower in decode and 28.48% lower in
wall output, with 40.12% higher TTFT, than the separate MTP3 screen.

This is a Grade-C support cell, not a record or deployment result. The larger
pool completed the service workload that the prior 21-block arm did not, but
it does not prove causality or a minimum cache and it did not improve formal
speed: its formal decode was 15.69% lower and TTFT 16.32% higher than the
21-block formal row. Controlled shutdown left no process or listener and all
four B70s remained discoverable. The retained journal is not quiet: it records
corrected Samsung NVMe endpoint/root-port link noise, with all uncorrected
status fields zero and no B70 address involved; the log also retains the known
shutdown-time output-handler notice and one shared-memory cleanup warning. The
earlier quarantine is retained below as superseded history. Receipt:
[`20260827-tp4-mtp2-4352-headroom32-attempt2-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp2-4352-headroom32-attempt2-result.json).

## Superseded 21-block exact-4K TP4 MTP2 quarantine

The additive MTP2/4K arm retained the configured-512 source, runtime,
placement, and eager TP4/EP4 identity. Its exact 21-block allocation exposed
4,810 cache tokens and 1.11x concurrency. All four ranks reported 32.06 GiB
model allocation and 12.22 GiB selective host placement.

All 26 sealed MTP0 comparisons matched, fixed-set repeats held one hash for
16/16 runs, and the needle passed at exactly 4,096 server prompt tokens. All
24 quality requests reported zero cached and created-cache tokens. The formal
p4096/o128 fixture also passed all 25 checks at `4.126872339 tok/s`
conventional with `317.350522 s` TTFT and zero cached tokens. The inherited
strict target score remains 5/7.

The first p4096/o256 deployment-shaped row stopped during prefill at 3,904
computed and zero output tokens. After five one-minute wait messages, the
300-second worker-response deadline expired, the stream returned an error, and
the service stopped. No row JSON, output hash, decode score, or three-row
median is authorized. Rows two and three never started.

Cleanup was followed by one compute and one copy-engine reset on each B70.
No process or listener remained and all four cards were discoverable, but no
post-reset collective was run. This remains Grade-C exact-4K capability
evidence and failure history, but the later 32-block control now supersedes it
as the practical selector. The MTP2/512 and MTP3/4K cells remain untouched.
Receipt:
[`20260827-tp4-mtp2-4352-attempt1-mixed-quarantine.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp2-4352-attempt1-mixed-quarantine.json).

## Quarantined exact-4K TP4 MTP4 screen

The additive MTP4/4K attempt retained the successful 512-token source,
runtime, placement, and eager TP4/EP4 identity. Its exact 29-block fixed cache
admitted 4,352 tokens and exposed 4,674 cache tokens at 1.07x concurrency; all
four ranks again reported 32.06 GiB model allocation and 12.22 GiB host
placement.

The exact-4K quality request stopped at 3,904 computed tokens when the engine's
300-second worker-response deadline expired during token sampling. The request
returned HTTP 500 and the service shut down. Because the helper did not write
its partial in-memory result, no short, repeat, baseline-parity, exact-4K, or
speed credit is taken from this attempt.

Workers lingered after the service stopped. During cleanup the kernel logged
engine resets on all four B70 addresses. No process or listener remained, and
all four cards were discoverable afterward, but no post-reset collective was
run. Raising only the deadline is therefore not an authorized retry. This cell
is quarantined at Evidence D; MTP4/512 and MTP3/4K remain untouched. Receipt:
[`20260827-tp4-mtp4-4352-attempt1-bounded-negative.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp4-4352-attempt1-bounded-negative.json).

## Exact 4K TP4 MTP3 screen

The deployment-shaped MTP3 arm raises only the configured maximum to 4,352 and
the fixed cache to exactly 25 current-source blocks: 294,195,200 bytes
(280.566406 MiB) per rank. It preserves the same model, source, runtime,
TP4/EP4, eager/graph-off path, and selective host placement. Cache admission
reported 4,730 tokens and 1.09x concurrency. The 51B PLE/input-embedding shards
remained resident in pinned system RAM throughout service.

This arm matched all 26 sealed MTP0 4K comparisons, held one hash for 16/16
fixed-set repeats, passed the needle at exactly 4,096 server prompt tokens, and
completed all 24 audited quality requests with zero cached and created-cache
tokens. The formal p4096/o128 fixture also passed with 128 returned token IDs,
zero cached tokens, and a conventional 99-interval rate of
`4.669548249 tok/s` at `266.080895 s` TTFT. The inherited strict score remains
5/7, so this is exact-depth parity and capability evidence, not full quality.

Three separately salted p4096/o256/c1 service rows, with no harness-added
warmups, returned the accepted target hash at `16.578976110`, `15.501565106`,
and `14.615697889 tok/s` after first text, median
**`15.501565106 tok/s`**. Their median TTFT was `187.899186 s` and median wall
output rate was `1.246260 tok/s`. Cumulative session metrics accepted 799/852
draft tokens (93.78%) and reported zero cached prompt tokens.

The after-first-text median is 196.19% above the separate MTP0 4K
legacy-comparable median, but this is not a universal deployment win: compared
with that MTP0 screen, TTFT is 52.28% slower and end-to-end wall output rate is
16.12% lower. On the formal content, decode improved only 4.79% while TTFT was
22.11% slower. MTP0 used vLLM source `658965050`, while MTP3 used `1372c62d`,
so both numerical comparisons are descriptive workload-aligned cross-run and
cross-source evidence, not causal MTP-depth A/Bs. The site therefore keeps decode, TTFT, and wall throughput
together and does not replace the MTP0 or MTP3/512 cells. Receipt:
[`20260827-tp4-mtp3-4352-attempt1-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-4352-attempt1-result.json).

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

## Quarantined active-8K TP4 MTP2 screen

The separately preregistered current-source MTP2 arm used the verified model
from local NVMe and the proven 32-block allocation. It exposed 11,264 cache
tokens and completed exactly one p8192/o128 request with exact 8192/128/8320
usage, zero cache reuse, a length stop, and 128 returned token IDs. MTP2 was
active: 53 drafts produced 106 draft tokens, 76 were accepted, and both draft
positions had positive acceptance.

The output first diverged from the frozen MTP0 authority at zero-based token
index 26. Because that authority used a different vLLM commit and cache
allocation, the result is a scoped cross-runtime parity quarantine rather than
proof that MTP2 caused the difference. The observed `6.234518 tok/s` and
`649.717302 s` TTFT are diagnostic only. Controlled shutdown passed, all four
cards returned idle, and no B70 event appeared; 22 corrected storage/root-port
records separately block clean-host and deployment wording. Existing MTP2
configured-512 and exact-4K screens, MTP0 exact-8K, and every featured speed
remain unchanged. See the
[`MTP2 active-8K receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-8448-context-attempt2-parity-quarantine.json).

## Quarantined active-8K TP4 MTP3 screen

The separately preregistered current-source MTP3 arm passed its exact
local-NVMe source/runtime, fresh four-rank, placement, served-identity, health,
and capacity gates. The fixed 32-block allocation exposed 9,654 cache tokens,
and all four ranks recorded the required 12.22-GiB selective offload receipt.

Its sole p8192/o128 request entered inference but reached the frozen 900-second
client bound without a completed response receipt or any durably recorded
output token. No exact usage, cache-zero, MTP-counter, parity, rate, TTFT, or
quality result exists, so this is a Grade-D bounded no-receipt quarantine with
no performance, quality, or deployment credit.

The descendant-aware failed-request path shut down the exact server group and
left no listener, process group, compile path, or RPC path. All four cards were
rediscovered below 43 MiB and no B70-addressed event appeared. The host window
contained 33 corrected records / 34 corrected endpoint sections for the local
NVMe link; they separately block clean-host and deployment wording. Existing
MTP3 configured-512 and exact-4K screens and every featured speed remain
unchanged. See the
[`MTP3 active-8K receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-8448-context-attempt1-bounded-negative.json).

## Quarantined active-8K TP4 MTP1 screen

The separately preregistered current-source MTP1 arm passed its exact
local-NVMe source/runtime, fresh four-rank, placement, served-identity, health,
and capacity gates. The fixed 32-block allocation exposed 13,516 cache tokens,
and all four ranks recorded the required 12.22-GiB selective offload receipt.

Its sole p8192/o128 request completed with exact 8192/128 usage, zero cache
reuse, all 25 generic exact-depth gates, and active MTP1 counters. It accepted
51 of 76 draft tokens at position zero, but its output first diverged from the
frozen cross-runtime/cache MTP0 authority at zero-based generated-token index
72. The observed 4.151 tok/s decode rate and 953.3-second TTFT are diagnostic
only, so this is a Grade-D scoped parity quarantine with no performance,
quality, or deployment credit.

The descendant-aware completed-classification path performed a controlled
shutdown and passed its cleanup gates: no listener, process group, compile
path, RPC path, or temporary state remained. All four cards were rediscovered
below 43 MiB and no B70-addressed event appeared. The intentional stop retained
the known shutdown-time output-handler notice and one shared-memory cleanup
warning. Seven corrected local-NVMe endpoint records separately block
clean-host and deployment wording. Existing MTP1 configured-512 at 9.372 tok/s,
exact-4K at 8.904 tok/s, MTP0 exact-8K, and every featured speed remain
unchanged. See the
[`MTP1 active-8K receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-8448-context-attempt1-parity-quarantine.json).

## Quarantined active-8K TP4 MTP4 screen

The final practical-slice arm retained the current-source TP4/EP4/eager MTP4
identity and used a 423,641,088-byte fixed cache. Its exact 36-block admission
reported 9,504 tokens / 1.12x maximum concurrency at the configured 8,448-token
cap, and every rank recorded the required 12.22-GiB selective offload receipt.

Its sole p8192/o128 request completed in 948.095 seconds with exact
8192/128/8320 usage, zero cache reuse, a length stop, 128 token IDs, and all 25
generic exact-depth gates. MTP4 was active at every position: 41 drafts produced
164 draft tokens, 86 were accepted, and the positive accepted-position deltas
`[30, 24, 18, 14]` sum exactly to 86. The candidate output first diverged from
the frozen cross-runtime/cache MTP0 authority at zero-based generated-token
index 26 (one-based token 27). The observed `4.025629 tok/s` conventional
99-interval rate and `918.432851 s` TTFT are diagnostic only. This is a Grade-D
scoped parity quarantine; it does not isolate MTP4 as the cause and grants no
speed, quality, or deployment credit.

The completed-classification supervisor returned zero and passed postflight:
no listener, recorded group, compile path, or RPC path remained, and all four
cards were rediscovered below 43 MiB. The five-second grace expired before the
remaining EngineCore and workers were stopped; the known shutdown-time
output-handler notice and one shared-memory cleanup warning also remain
disclosed. Six corrected Source-514 records named only local NVMe
`0000:01:00.0`; no B70-addressed event appeared.

Attempt 1 is retained as a superseded launcher-protocol artifact. It reached a
healthy server but failed closed at the client's pre-network supervisor-command
identity check, sent no model request by control-flow inference, and grants no
matrix or performance credit. Its corrected receipt is the
[`attempt-1 pre-request stop`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-8448-context-attempt1-pre-request-stop.json).
The classified attempt-2 receipt is the
[`MTP4 active-8K parity quarantine`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-8448-context-attempt2-parity-quarantine.json).

The practical TP4 eager-text slice is now fully classified at 25/25: 12
screened and 13 quarantined. The retained MTP4 configured-512 result remains
`20.72717637199404 tok/s`, the preferred MTP3 exact-4K result remains
`15.50156510641242 tok/s`, and every prior speed is unchanged.

## Quarantined active-16K TP4 MTP0 screen

The first deeper-context arm used the current-source TP4/EP4/eager MTP0
identity with a 358,465,536-byte fixed cache. Exact 33-block admission exposed
21,795 tokens, and every rank recorded the required 12.22-GiB selective
offload receipt.

Attempt 1 became healthy but stopped before any request because the client
rejected a relative supervisor path; its sealed no-request receipt grants no
matrix credit. Attempt 2 corrected only that ownership check and used fresh
paths and port. Its one p16384/o128 request completed in 1,097.981 seconds with
exact 16384/128/16512 usage, zero cache reuse, a length stop, 128 token IDs,
and all 25 generic exact-depth gates. Output-token SHA-256 is
`5706b3445c50abaaedacae0e5f52739856300701374126c23d610367c1dd1d39`.

The `5.219484 tok/s` conventional diagnostic rate and `1,073.542649 s` TTFT
receive no speed or curve credit. Semantic, repeat, and fresh-server-repeat
gates were absent, so this is Grade-D bounded capability evidence with no
quality or deployment credit. Controlled shutdown passed postflight and all
cards returned below 43 MiB. Thirty-six corrected Source-514 reports and 46
RxErr log lines named only local NVMe `0000:01:00.0`; no B70-addressed event
appeared. The 49-entry manifest verifies at
`d1cbe2533ca024bbadf725163a0ce22cb268a54b42d83ac65cc2dd08984d1363`.

The ≤8K practical slice remains exactly 25/25 and every captured speed is
unchanged. The full 480-cell contract is now 26 classified: 12 screened, 14
quarantined, and 454 missing. See the
[`MTP0 active-16K receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp0-16512-attempt2-generic-quarantine.json).

## Quarantined active-16K TP4 MTP2 treatment exhausted

The normal current-source MTP2 identity admitted exactly 40 blocks /
470,712,320 bytes and reported 20,014 cache tokens. Its scheduler-64 request
stopped at 3,200 computed prompt tokens with no output. The sole material
treatment preserved the model, source, stage, topology, cache, request,
comparator, and 300-second runtime response deadline while halving max batched
and scheduled tokens to 32. It passed a fresh four-rank preflight and became
healthy, then reached 5,440 computed prompt tokens after 958.552 seconds before
the same runtime deadline ended it with no output. The 2,240-token / 70%
extension is treatment evidence, not repeat-confirmed causality or active-16K
capability. Generic completion, MTP counters, and same-runtime MTP0 parity
remain unavailable.

During treatment shutdown, the sealed host window recorded eight card resets
(two per card) and 58 unsuccessful card responses. This fails the preregistered
postflight rule: supervisor rc was 70 and the treatment tranche is exhausted.
Current checks show no listener, owned process, compile path, or RPC path, and
all cards below 43 MiB. The 47-entry manifest verifies at
`62895c7066ae52f33e937c93c2a9b173908a1fcd03135460385ca968f41a01ba`.

This remains a Grade-D bounded negative with no capability, speed, curve,
quality, parity, deployment, or headline credit. The full contract remains
27/480: 12 screened, 15 quarantined, and 453 missing. The completed ≤8K
practical view and every prior captured speed remain unchanged. There is no
scheduler-16, timeout-only, or further MTP2 active-16K retry. See the
[`MTP2 scheduler-treatment receipt`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-16512-scheduler32-attempt2-runtime-timeout-quarantine.json).

## Coverage-contract supersession

The `27/480` total above remains historical experiment accounting, but the
public contract now uses **22/270 classified**. The old denominator crossed all
eight text-context depths into vision and therefore created 240 combinations
without a defined image fixture. It also mixed five legacy-runtime MTP0 screens
into the latest-runtime contract.

The replacement is a 240-cell latest-runtime text contract (7 screened, 15
quarantined, 218 missing) plus a 30-cell latest-runtime fixed-fixture vision
contract (all missing until the fixture and first TP4 eager MTP0 anchor exist).
Legacy MTP0 4K/8K measurements remain visible in an archival view. Deterministic
Grade-D legacy-runtime estimates at 24K and 32K are shown there with 50%-150%
bands and no boot, fit, quality, current-runtime, deployment, record, or
promotion authority. The practical 25/25 mixed-runtime view and every captured
speed, packet result, quarantine, and protected claim remain unchanged.
