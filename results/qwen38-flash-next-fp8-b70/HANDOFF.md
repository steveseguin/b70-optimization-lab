# Qwen3.8 Flash-Next FP8 B70 handoff

The current result is a bounded research screen, not a promoted deployment.
Attempt 19 is the first diagnostic-free healthy TP4/EP4 server and must remain
intact while later matrix cells are added.

## Resume identity

- Active verified model: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`.
- Preserved external source copy:
  `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`.
- Model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
- Current vLLM source checkout: `/home/steve/src/vllm-current-main` at
  `1372c62d975c554f4b465c8299bc5f3295301ceb`. Attempt 19 used
  `658965050f259999e635b52a850004a3771cd644`; the later changes are the MTP
  tests and fail-closed legacy speculative adapter, while the MTP0 target route
  is unchanged.
- Current XPU-kernel source checkout: `/home/steve/src/vllm-xpu-kernels` at
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`.
- Preserved runtime used by MTP0 and the accepted untreated MTP1 control:
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, built from
  kernel source `2f829747503c77d4814834dffd0840fb1dd9f75a`.
- Launcher:
  `experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp0-512.sh`.
- Attempt-19 evidence root:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1-attempt19`.

Apply vLLM patches `0001`–`0010`, `0012`, and `0014`–`0018` in order on base
`76cfe1cd88d30d525eec8be5bff75f8b77471c88`. Do not apply diagnostic patches
`0011` or `0013` to a qualification or timing tree. Apply all five kernel
patches on base `0fd18a7c08a64d2645bf083cfa5576200b61b02c`. Patch `0005` is the
paused exact-runtime treatment and is not present in the accepted preserved
stage. The authoritative
checksums are in `patches/qwen38-flash-next-fp8-b70/README.md`.

The exact pre-upstream-sync kernel tree also has a verified self-contained
bundle at
`/mnt/usb-models/qwen38-build/source-backups/vllm-xpu-kernels-pre-gdn-sync-2f829747.bundle`
with SHA-256
`be14c05473a77ea908282dc62478dc6fe5f5b55dedd3477f1de0b4f6c21fc149`.
Do not merge the newer upstream GDN refactor casually: it overlaps retained
serving optimizations and needs a deliberate forward port plus parity and
speed qualification.

## Current boundary

Attempt 19 measured 5.142647219 / 5.221849709 / 5.289933931 tok/s after first
text on p146/o256/c1. Both short batteries passed 5/7 strict cases and one of
16 greedy repeats diverged. This is Grade-C research evidence and a
`lab-screened` operating point. It is not record-eligible.

The additive TP4/EP4/eager/MTP0 1,536-token-cap arm is complete. It passed the
987-token needle, 16/16 repeats, and the formal realistic-suite validity gate;
three exact-1K samples had a `5.133588 tok/s` median after first text. The same
5/7 short-quality boundary remains, so the cell is research-only. Its receipt
is `experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-1536-context-screen.json`.

The first configured-3K arm passed an exact cache-zero 2K needle and reported
6,144 cache tokens, but one open-choice repeat differed. The frozen gate
stopped before speed; that quarantine remains retained. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-3072-context-screen.json`.

The repeat-v2 retry changed no server setting. Its prescribed canary passed
32/32 first tokens and 16/16 full outputs, the formal exact-2K row passed, and
three comparable rows had a `5.228429 tok/s` median after first text. The 2K
selector is research-screened; the known 5/7 short boundary remains. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-3072-context-repeat-v2-screen.json`.

The additive configured-4,352 arm passed exact baseline agreement, 16/16
fixed-set repeats, the exact cache-zero 4K needle, and the formal depth gate.
Its formal rate was `4.456026 tok/s`; three legacy-comparable exact-4K rows had
a `5.233665 tok/s` after-first-text median. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-4352-context-screen.json`.

The additive configured-8,448 arm passed exact baseline agreement, 16/16
fixed-set repeats, the exact cache-zero 8K needle, and the formal p8192/o128
gate at `3.979729 tok/s` with `386.534332 s` TTFT. Two legacy-comparable rows
completed at `5.170404 / 5.182353 tok/s` with identical output; the runtime
stopped during row 3, so no legacy median or curve point is authorized. Commit
`08a865143` makes the helper fail closed on incomplete streamed responses.
Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-8448-context-screen.json`.

The configured-4,352 MTP3 gate and complete configured-512 MTP0-4 depth grid
now pass their bounded gates. Exact 4K is also classified across MTP0-4:
MTP0/MTP1/MTP2/MTP3 are screened and only MTP4 is quarantined. MTP4/512 is the fastest short screen at a
`20.727176 tok/s` median with 1,716/1,716 cumulative draft acceptance. The
MTP4 exact-4K selector is quarantined after its first quality request
stalled at 3,904 computed tokens and cleanup reset all four card engines. The
MTP1 and MTP2 32-block headroom selectors completed their exact-4K batteries
at `8.904421` and `9.893155 tok/s` decode medians. MTP3 remains preferred at
`15.501565 tok/s`, `187.899186 s` TTFT, and `1.246260 tok/s` wall output.

The target-only official quality profile also passes. Its sealed
non-thinking control matched 26/26, repeated 16/16, and returned the exact 4K
needle; semantically it is 6/7, with only the inherited `30` versus `14` code
miss. Qwen's official thinking sampler then passed a 4/4 scout and 21/21
three-seed grid with separated reasoning/final fields, normal stops, complete
usage, and zero cache reuse. The code answer was `14` in all four thinking
responses. This does not certify the MTP speed rows or replace any decode
number. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-official-quality-attempt2-result.json`.

The preregistered MTP3 transfer attempt is now closed inconclusive rather than
left open. Its verified local-NVMe boot and Door A passed. Door B passed the
4/4 scout plus 15/21 grid rows; every one of the 19 completed responses passed
semantic, structural, usage, and cache-zero gates and exactly matched the MTP0
final answer. The twentieth response (`copy_phrase`, seed `2026082713`) stopped
at 98 computed and 33 output tokens, then the fixed 300-second worker-response
timeout produced API 500. This is an unqualified repeated-session stability
result with no observed answer-quality failure and no causal claim. Forced
post-grace cleanup reset CCS and BCS engines on all four cards; final receipts
show an idle host, clear port, and four discoverable cards. The incident kernel
snapshot was clean before forced stop. Corrected NVMe receiver events existed
in the wider run window, while SMART reported zero critical warnings, media
errors, and error-log entries. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-official-quality-attempt2-result.json`.

The later preregistered MTP1 active-1K arm passed its exact source/runtime,
four-rank, placement, cache, capacity, and health gates, then stopped during
its first request after 768 computed prompt tokens with no output. The fixed
300-second worker-response gate fired; request two was not sent and the
separate active-2K boot did not run. This retains MTP1/1K as a bounded negative
under that combined stop rule. MTP1/512 and exact-4K remain unchanged. Do not
retry the 1K arm without a material first-request completion fix and a fresh
four-rank boot. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-1536-context-attempt1-bounded-negative.json`.

The separately preregistered standalone MTP1 active-2K arm is now also a
bounded negative. Its local-NVMe boot passed every source/runtime, four-rank,
placement, 32-block cache, capacity, identity, and health gate, exposing 7,561
cache tokens. The first exact-2K exchange had a zero-byte completion body and
no output token recorded when the fixed 360-second client bound expired. The
subsequent engine diagnostic reported 448 computed prompt tokens and zero
output, and the engine independently
reported its own sampling timeout. Request two was not sent and no speed or
quality credit is authorized. The post-failure teardown window recorded one
compute- and one copy-class reset on every card; all four devices were
discoverable afterward with no listener or residual model process, but no
post-reset collective was run. MTP1/512, exact-4K, and all captured speeds
remain unchanged. Any repeat requires a material first-request completion
treatment, a new preregistration, and a fresh four-rank preflight. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-3072-context-attempt2-bounded-negative.json`.

The separately preregistered MTP3 active-2K arm also closes as a quarantine,
for a different reason. Its local-NVMe boot passed source/runtime, four-rank,
placement, 25-block cache, capacity, identity, and health gates. Request one
completed with exactly 2,048 prompt and 128 output tokens, zero cached tokens,
a length stop, and positive MTP3 counters. Its generic exact-depth gate passed
at `5.931661 tok/s` conventional with `150.769910 s` TTFT, but the returned
token-array hash differed from the frozen MTP0 authority beginning at generated
token five. Under the frozen rule, request two was not sent and the observed
rate receives no speed or quality credit. This is a scoped cross-lane parity
mismatch; MTP0 and MTP3 used different vLLM commits and cache allocations, so
the run does not isolate MTP3 as the cause or establish a universal semantic-
quality failure. MTP3/512 and exact-4K remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-3072-context-attempt1-parity-quarantine.json`.

The successor MTP2 active-2K arm used the proven 32-block headroom allocation
and passed the same startup gates. Request one completed with exactly 2,048
prompt and 128 output tokens, zero cached tokens, and positive MTP2 counters.
Its generic exact-depth gate measured `4.526753 tok/s` conventional with
`310.712871 s` TTFT, but its token array first diverged from the frozen MTP0
authority at generated token 13. Request two was not sent and the diagnostic
rate receives no speed or quality credit. As with MTP3, this is a scoped cross-
lane parity mismatch rather than isolated MTP causality because the MTP0
authority used a different vLLM commit and cache allocation. MTP2/512,
MTP2/exact-4K, MTP3/active-2K, and all featured speeds remain unchanged.
Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-3072-context-attempt1-parity-quarantine.json`.

The separately preregistered MTP2 active-1K arm used the verified local-NVMe
model and the same 32-block headroom allocation. Its fresh four-rank boot passed
all startup gates. Both authorized requests returned exactly 1,024 prompt and
256 output tokens, the frozen MTP0 text hash, zero cache reuse, identical text,
and perfect 85/85 acceptance at both MTP2 positions. Request one measured
`10.682699 tok/s` after first text and the repeat sentinel `12.641866 tok/s`.
However, the bounded journal contained 11 corrected records for local NVMe
`0000:01:00.0` after the frozen cutoff. No event named a B70 address, but the
strict clean-host gate still failed, so the cell is a Grade-D host-health
quarantine and both rates remain diagnostic only. MTP2 configured-512,
active-2K, exact-4K, and all captured rates are unchanged. Retry only with a
clean local-NVMe link or an identical verified model on a storage path with a
clean post-cutoff host window. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-1536-context-attempt1-host-quarantine.json`.

The subsequent MTP3 active-1K arm used the verified local-NVMe model and exact
25-block allocation. It passed identity, fresh four-rank, placement, capacity,
served-model, and health gates. During request one, the server received an
external `SIGTERM` at 00:05:06 before completing a response. No request JSON,
usage, output hash, or speed exists. Partial server metrics retained six
drafted and six accepted tokens with 1.000 acceptance at all three positions;
those counters are transport context only and receive no parity, speed,
quality, or deployment credit. Request two was blocked. The journal retained
one corrected-only NVMe receiver record and no B70 event; teardown left no
listener/process and all four cards discoverable. MTP3 configured-512,
active-2K, exact-4K, and all captured rates remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-1536-context-attempt1-external-stop.json`.

The successor MTP4 active-1K arm passed every startup gate and both exact
p1024/o256 requests. Both matched the frozen MTP0 text with zero cache reuse,
and each accepted 204/204 draft tokens split 51/51/51/51 across all four MTP4
positions. Its `13.326165` and `17.290937 tok/s` after-first-text observations
remain diagnostic only: the detached supervisor ended its timeout wrapper but
did not forward the exact stop to the server group. Direct recovery produced
an orderly shutdown, yet the frozen teardown contract makes the cell Grade D.
Seven corrected-only local-NVMe records separately block clean-host credit; no
B70 event appeared. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-1536-context-attempt1-teardown-quarantine.json`.

The corrected descendant-aware lifecycle test then passed, and the separately
preregistered MTP4 active-2K arm used it for one bounded boot. All startup
gates passed with the exact 29-block allocation and 3,563 reported cache
tokens. Request one reached the fixed 360-second client bound without a
receipt; about five seconds later the engine independently reported its own
sampling timeout at 384 computed prompt tokens and zero output. Request two
was not sent. The supervisor returned zero and left no listener, recorded
process, compile path, or RPC path, but the teardown window recorded compute-
and copy-class resets on all four B70s plus 60 unsuccessful fault responses.
All four cards were rediscovered at low memory use; no post-reset collective
or known-good generation canary was run. The cell is Grade D with no speed,
quality, parity, MTP-acceptance, or deployment credit. MTP4/512, active-1K,
exact-4K, and all captured rates remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-3072-context-attempt1-bounded-negative.json`.

Before any new GPU arm, follow the documented post-reset recovery qualification
boundary; do not infer readiness from device rediscovery alone. Do not retry
stopped arms by raising only the timeout. After qualification, reduce
MTP3 4K TTFT and qualify fresh-boot stability. Audit the XPU host-lookup overlap
separately. Defer 16K+ until the 8K repeated-serving boundary and larger
fixed-cache requirement have a bounded design. TP1/TP2 need a new memory design
and are not simple launch variants. Never overwrite the 512 or 1,536 attempts,
remove the accepted runtime, or replace a captured rate with an estimate.

## TP4 MTP1/512 closeout

The performance-preserving speculative adapter is complete at vLLM
`1372c62d975c554f4b465c8299bc5f3295301ceb`. The matched untreated-runtime arm
at attempt 3 passed all 26 MTP0 baseline comparisons once both clients used
`enable_thinking=false`, held the fixed-set repeat at one hash for 16/16 runs,
passed the small cache-zero needle, and measured `9.773841 / 9.372254 /
8.107468 tok/s`, median `9.372254 tok/s` after first text. It accepted 503/505
drafts in cumulative endpoint metrics. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp1-512-attempt3-result.json`.

## TP4 MTP2/512 closeout

Attempt 1 passed cache admission with a 192-MiB allocation resolving to 17
usable blocks and 621 reported tokens,
matched all 26 sealed MTP0 comparisons, held one hash for 16/16 repeats, passed
the small cache-zero needle, and completed all 24 audited usages. Three
p146/o256/c1 rows returned the target hash at `13.586501 / 10.064085 /
11.895061 tok/s`, median `11.895061 tok/s` after first text. Median end-to-end
output was `7.804965 tok/s`, median TTFT was `11.278097 s`, and cumulative
acceptance was 770/770 across two positions. The 29.61% row span keeps this a
variable Grade-C screen, not a stable ceiling or causal depth A/B. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp2-512-attempt1-result.json`.

Attempt 2 remains preserved as a client-identity mismatch, not a runtime
parity failure. The exact-runtime candidate and its component gates remain
preserved but are paused because the unchanged runtime passed. Next qualify
MTP1 at deeper context and audit whether the current XPU UVA lookup overlaps
host-row transfer like the official NVIDIA PLE-prefetch design. Keep MTP0 and
MTP1 as separate Grade-C cells; neither is deployment- or record-eligible.
The deployment audit and bounded replacement gate are in
`experiments/qwen38-flash-next-fp8-b70/notes/2026-08-27-ple-deployment-audit.md`.

## TP4 MTP2 exact-4K mixed quarantine

Attempt 1 used the exact 21-block allocation (`247123968` bytes), passed the
fresh four-rank preflight, became healthy, and reported 4,810 cache tokens.
All 26 sealed MTP0 comparisons matched, repeats held one hash for 16/16, the
exact 4K needle passed, and the formal p4096/o128 gate passed at
`4.126872 tok/s` conventional with `317.350522 s` TTFT.

The first p4096/o256 row stopped during prefill at 3,904 computed and zero
output tokens. The worker-response deadline expired, no durable row was
written, and rows two and three never started. Cleanup reset all four card
engines. No process or listener remained and every card was discoverable, but
the next GPU arm must repeat the collective preflight. Preserve the quality
and formal artifacts, grant no p4096/o256 comparison speed, and do not retry by
raising only the timeout. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp2-4352-attempt1-mixed-quarantine.json`.

## TP4 MTP3/512 closeout

Attempt 4 is the first valid configured-512 MTP3 arm. It retained the MTP1
source, staged runtime, selective host placement, TP4/EP4, eager/graph-off, and
client identity, while using the independently sized 20-block fixed cache
(`235356160` bytes). It became healthy with 568 cache tokens, matched all 26
bounded MTP0 comparisons, held 16/16 fixed-set repeats to one hash, passed the
small cache-zero needle, and completed all 24 audited quality requests without
cache reuse. The inherited strict boundary remains 5/7; the 317-token needle
is not evidence of 4K MTP3 quality.

Three p146/o256/c1 rows measured `17.473321 / 14.888790 / 12.538689 tok/s`,
median `14.888790 tok/s` after first text, with the exact MTP0 target hash. The
post-session endpoint reported 768/768 cumulative draft tokens accepted. The
rows declined monotonically and span 33.14% of the median, so this is a Grade-C
research cell rather than a stable ceiling or record. MTP0 remains primary and
the MTP1 cell is unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-512-attempt4-result.json`.

## TP4 MTP4/512 closeout

Attempt 1 passed with the frozen source/runtime/placement and exact 24-block
cache allocation (`282427392` bytes), reporting 558 cache tokens and 1.09x
concurrency. All 26 MTP0 comparisons matched, repeats held one hash for 16/16,
the small cache-zero needle passed, and all 24 quality usages completed. Three
corrected p146/o256/c1 rows returned the target hash at `21.119694 /
18.576249 / 20.727176 tok/s`, median `20.727176 tok/s` after first text. Median
wall output was `11.560327 tok/s`, median TTFT was `10.023315 s`, and
cumulative acceptance was 1,716/1,716 across four positions.

The first timing loop's literal filename retained only its third row; both
surviving files are preserved and checksummed, and the unchanged workload was
rerun correctly. This closes the configured-512 TP4 MTP0-4 grid, not MTP4 at
4K or production readiness. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp4-512-attempt1-result.json`.

## TP4 MTP4 exact-4K quarantine

Attempt 1 retained the successful MTP4/512 source/runtime/placement and used
the exact 29-block cache allocation (`341266432` bytes). It became healthy and
admitted 4,352 tokens, but its exact-4K quality request stopped at 3,904
computed tokens when the 300-second worker-response deadline expired during
sampling. The service shut down before the helper wrote a durable quality
JSON; no quality or speed credit is authorized.

Workers lingered until the launcher was stopped. Cleanup was followed by
engine resets on all four B70 addresses. No process or listener remained, and
all cards were discoverable afterward, but a post-reset collective was not
run. Do not retry by raising only the deadline. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp4-4352-attempt1-bounded-negative.json`.

The user has selected roughly 4K as the practical deployment ceiling for now.
The next launch should therefore use configured maximum 4,352 and exactly
`294195200` cache bytes (25 blocks) for a 4,096-token prompt plus 256 output
tokens. Preserve the current host placement: the PLE/input-embedding shards are
resident in pinned system RAM during service, not streamed from the USB model
tree. The separate gate below now supplies that exact-depth evidence.

## TP4 MTP3 exact-4K closeout

Attempt 1 at configured maximum 4,352 passed with exactly 25 cache blocks,
4,730 reported cache tokens, and the same source/runtime/placement as the
configured-512 MTP3 cell. All 26 sealed MTP0 4K comparisons matched, fixed-set
repeats held one hash for 16/16 runs, the needle passed at exactly 4,096 server
prompt tokens, and all 24 quality usages were complete and cache-zero. The
formal p4096/o128 fixture passed at `4.669548 tok/s` conventional with
`266.080895 s` TTFT.

Three no-warmup p4096/o256 rows returned the target hash at `16.578976 /
15.501565 / 14.615698 tok/s`, median `15.501565 tok/s` after first text. Median
TTFT was `187.899186 s`; median wall output rate was `1.246260 tok/s`.
Cumulative session acceptance was 799/852 (93.78%). Relative to the separate
MTP0 4K legacy-comparable screen, decode is 196.19% higher but TTFT is 52.28%
slower and wall output rate is 16.12% lower. The next production problem is
prefill/TTFT and fresh-boot stability, not proving 4K fit. These deltas are
descriptive workload-aligned cross-run/cross-source evidence, not a causal
MTP-only A/B: MTP0 used vLLM `658965050` and MTP3 used `1372c62d`. MTP0, MTP1, and
MTP3/512 remain untouched. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-4352-attempt1-result.json`.
