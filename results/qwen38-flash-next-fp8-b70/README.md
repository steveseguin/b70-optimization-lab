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
now also includes a target-only official-thinking quality profile that passed
25/25 preregistered responses. A later MTP1 1K arm passed every boot and
admission gate but stopped on its first request without returning output; that
cell is quarantined, while MTP1 512 and exact 4K remain unchanged and MTP1 2K
remains unrun. It does not yet establish a production recipe, a fully quality-
qualified MTP speed, stable repeated serving at 8K, 16K+ behavior, or vision
support.

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

The service-shaped TP4/MTP3 configured-4,352 point now passes exact 4K parity,
formal depth, and three p4096/o256 rows. Its TTFT and wall-rate tradeoff, plus
fresh-boot stability, remain production work. The 16K/24K/32K MTP0 expansion
is deferred while the 8K repeated-serving boundary remains unresolved. TP1
and TP2 require a separate fit/offload design. The complete configured-512
MTP1-4 grid and exact-4K MTP1/MTP2/MTP3 cells are separately screened below;
MTP4 at exact 4K and MTP1 at active 1K are quarantined for separate stopped-
request events. Target-only official-thinking quality now passes. The first
MTP3 transfer attempt returned 19/19 correct completed answers but is
unqualified after a repeated-session runtime stop; MTP1 active 2K, graph,
deeper context, vision, fresh-server determinism, clean-host replay, and a
sealed deployment package remain explicit gaps.

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
passing exact-4K headroom recipe. Active 2K remains missing rather than failed.
Receipt:
[`20260828-tp4-mtp1-1536-context-attempt1-bounded-negative.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-1536-context-attempt1-bounded-negative.json).

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
