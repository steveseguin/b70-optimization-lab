# Packet45 SPEED6 LocalMaxxing payload — prepared, not submitted

2026-10-15. Run 1 is the pre-registered headline. This packet prepares a
submission under the owner's existing 128-token exception. It does not submit
or change the public record. The coordinator retains submission and the
confirmation evidence below; the planned A-B-A did not complete.

Same Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS GGUF model and quantization as
SPEED3 record `cmv9j70v100v1le01q9jxyx2r`, revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`. This is the quantized compressed
model lane, separate from the official FP8 model. The new runtime is
`packet45-merged3 SPEED6 34c62b433`, arithmetic `iq3-p17-detmath-v2`.

Two B70 cards, cards 0–1, run target layers split **23/25**, with the official
one-token MTP draft on **rank 1** and the native controller. Right-sized
operator scratch and pre-launch 30 GiB arena admission allow this split to
fit at context **4096 only**. The write-set snapshot preserves full state;
draft events are profiled once. K2-selected kernels and the small-FFN repair
remain enabled. Accepted tokens are verified by the unchanged target. KV stays
full 16-bit BF16; the API has no BF16 enum, so `apiKvCacheDtype=auto` accompanies
the literal BF16 identity. Boot: `13858eef-ec68-44ea-a67c-9444933b7100`.

| Measurement | Run 1 |
|---|---:|
| Primary: median of six class medians, 99 intervals between events 1 and 100 | **39.42200890284251 tok/s** |
| All-prompt median of the same 99-interval rate | 39.269033659702785 tok/s |
| Decode median, 63 intervals between events 1 and 64 | 39.39782269029965 tok/s |
| Median wall rate including prompt processing and complete generation | 28.225251993839873 tok/s |
| Median TTFT | 1265.3163114737254 ms |
| Median acceptance | 0.7913385826771654 |
| Requests / generated tokens | 12 / 1536 |
| Median input / output tokens | 68 / 128 |

The current submitted record remains
[`cmv9j70v100v1le01q9jxyx2r`](https://www.localmaxxing.com/runs/cmv9j70v100v1le01q9jxyx2r),
38.15715689731613 class-balanced tok/s. This measured run is **3.31485% higher**.
That is a comparison of observed headline values, not a confidence interval.
No repeat is substituted or pooled into the headline.

Every fixed realistic prompt ran once as a cold response, after a distinct
excluded warmup and complete state reset. All requests report cached_tokens=0.
There is no prompt/KV/response reuse or history acceleration. Each prompt
emitted 128 tokens with no earlier EOS. Full natural completion under 512 tokens
and 512-input-token prefill were not measured. Cap-limited rates and per-row
hashes, token counts and TTFT remain in the result JSON.

## Device exactness and provenance

The preparation verifies five passing, qualifying, device-executed windows
with the same seal, artifact hashes, dispatch, split, placement and boot.
Each window used distinct rank processes and records no retained owner PID.

| Window | Tokens exact | Layer fixtures exact | Role |
|---|---:|---:|---|
| W2m | 64/64 | 384/384 | Development-prompt exactness |
| WS | 1536/1536 | 4608/4608 | Fixed realistic suite |
| WSs | 1536/1536 | 4608/4608 | Sequential target-only comparison |
| WS128x | 1536/1536 | 9216/9216 | Steps 1–8 and 97–104 |
| WS128 | 1536/1536 | None retained | Timed headline suite |

**W2m, WS, WSs and WS128x are the real-model exactness authority** under
`packet45.fix6.device-oracle-authority.2026-10-15`. Historical CPU evidence
is not used to qualify this new runtime's speed. Every emitted token is checked
against the immutable arithmetic-v2-detmath per-prompt oracle, with no tolerance.
Preparation independently compares the stored tokens across all four suites,
verifies original request hashes, recomputes the headline from timestamps,
and checks zero caching and exact 128-token lengths. The retained fixture
comparisons come from passing device checker receipts, not a new model run.
Window journal tails contain no new fault signatures; preflight includes
historical faults, so this is not a claim that the whole boot was fault-free.

## Explicit 128-token scope exception

Owner authorization, **2026-10-15**, verbatim:

> authorized: submit under the same 128-token scope as the October 13 record.

The SPEED6 preparation directive explicitly extends that same scope to this
run: the fixed realistic twelve-prompt suite, cold, cached_tokens=0, **128**
generated tokens per prompt, primary metric over **99 intervals between events
1 and 100**. This is the scope of the October 13 submission
`cmv6pugme0020oa01fjrho6nx` and October 15 SPEED3 submission
`cmv9j70v100v1le01q9jxyx2r`. The current task authorizes preparation and server
dry-run only, not a real submission.

The source strict 512-cap gate remains **false**, with its unedited reason:

> measurement preparation only; cap below fixed 512 and no promotion attestation; repeats/partial suites never qualify

The source reason predates this separate attestation; retaining it does not
claim that the newly prepared attestation is absent. Both
`realisticSuiteGatePassed` and `strict512TokenFinalGatePassed` remain false.
`engineFlags.realisticSuiteScopeException` retains the dated authorization and
original named exception path. Result and attestation carry the same scope and
raw gate, plus the explicit SPEED6 extension authorized by the coordinator.
The owner decision concerns the fixed suite, metric and cap; the implementation
still admits only two explicitly pinned run-1 identities, SPEED3 and SPEED6. No unconditional marker bypass
is used. The historical `lab.promotion-attestation.v1` and
`lab.realistic-suite-result.v1` schemas match the SPEED3 packet.

## Confirmation evidence — planned A-B-A did not complete

Run 1 remains the pre-registered submitted value. The same-pair fresh-process
repeat and the second-pair replicate each passed their qualifying device window
with 12/12 prompts and 1,536/1,536 tokens exact. The three SPEED6 runs share
boot `13858eef`, runtime `34c62b433`, build receipt `9b6fa7f3…`, actual artifact
hashes, context 4096, 23/25 split and draft rank 1. The second card pair has its
own measured dispatch. No confirmation value replaces or is pooled into run 1.

| Run | Cards | Requests retained | All-prompt tok/s | Class-balanced tok/s | Status |
|---|---|---:|---:|---:|---|
| SPEED6 WS128, run 1 — HEADLINE | 0–1 | 12/12 | 39.2690336597 | 39.4220089028 | Passing qualifying window |
| SPEED6 WS128-r2, fresh processes | 0–1 | 12/12 | 39.2186653814 | 39.3856075012 | Passing qualifying window |
| SPEED6 second-pair WS128 | 2–3 | 12/12 | 39.1990004664 | 39.3778483680 | Passing qualifying window |
| Packet44 WS128-r3, interleaved | 0–1 | 8/12 | 37.2109863807 | Not reported | FAILED window; partial measurement only |
| Packet44 WS128, earlier same boot | 0–1 | 12/12 | 37.7497798493 | Not reported | Passing legacy window |
| Packet44 WS128-r2, earlier same boot | 0–1 | 12/12 | 37.7937680076 | Not reported | Passing legacy window |
| Planned SPEED6 WS128-r3 | 0–1 | 0/12 | Not measured | Not measured | Did not execute |

**Control caveat:** packet44's interleaved control completed device work, but
its old 6 GB build-cap admission refused a write. Both its window and summary
read `passed=false`. More specifically, the retained summary contains **eight
rows** and only **eight passing request receipts** exist, each with 128 tokens
matching the headline's corresponding oracle-checked token sequence. Its
37.21098638069249 all-prompt median recomputes from those **8/12 prompts**, not
from a complete twelve-prompt suite. The old summary also says `complete=true`;
that field does not override the observed count or failure. We preserve the
original bytes and do not upgrade this to a qualifying window or matched
full-suite speed comparison. The legacy failed window has no bound request
hash map; the archive records the hashes of the retained request bytes read
here. The actual error is:

> Packet38 storage admission refused: free=23191195648, build=5342995322, reserve write=668210560; require 8 GB free and build below 6 GB

This corrects the coordinator's initial blanket 12/12 description for that
control only. The earlier same-boot packet44 controls were complete twelve-row
runs (37.74977984928242 and 37.79376800760946 all-prompt tok/s).

The coordinator reports that its runner halted on the failed control window,
so planned SPEED6 run 3 never executed; its output directory is absent. Thus
this is a fresh-process repeat plus a second-pair replicate and partial
interleaved control evidence, **not a completed A-B-A**. Original windows,
summaries, per-request archives, SHA256 hashes, exact metrics and monotonic
timestamp order are retained in
[confirmation-evidence.json](20261015-own-rt-iq3-tp2-c4096-s23dr1-confirmation-evidence.json).
The engine flags, result and attestation reference that same hash-bound record.

## Files and exact commands

All new files use prefix `20261015-own-rt-iq3-tp2-c4096-s23dr1-`.

- [Payload queue](20261015-own-rt-iq3-tp2-c4096-s23dr1-localmaxxing-payload-queue.json).
- [Result JSON](20261015-own-rt-iq3-tp2-c4096-s23dr1-realistic-suite-v1-result.json).
- [Promotion attestation](20261015-own-rt-iq3-tp2-c4096-s23dr1-promotion-attestation.json).
- [Verification](20261015-own-rt-iq3-tp2-c4096-s23dr1-verification.json) and [preparation script](20261015-own-rt-iq3-tp2-c4096-s23dr1-prepare.py).
- [Confirmation evidence](20261015-own-rt-iq3-tp2-c4096-s23dr1-confirmation-evidence.json).

The copied window JSON files preserve their exact original bytes. Compressed
request archives contain original base64-encoded bytes, source paths and SHA256
hashes; decompress, decode each member and verify its hash. No model weights,
binaries or state dumps are copied. Neither packet45-merged3 nor packet44-context
was written during preparation, including build outputs and Python caches.

`commandSnippet` uses the corrected compact placeholder style and is
**523 characters**, below the requested 600-character ceiling.
It is a summary, not the full executable command. `commandSnippetFullInEvidence`
points to the actual coordinator scripts:

- [Headline WS128](../../../../data/own-xpu-runtime-packet45-device-rounds-20261014/chains/1013-p51a-WS128.sh).
- [Chain](../../../../data/own-xpu-runtime-packet45-device-rounds-20261014/chains/1010-p51a-chain.sh).
- [OMP=2 chain runner](../../../../data/own-xpu-runtime-packet45-device-rounds-20261014/runner/coordinator_windows_speed5_omp2.sh).

These retain affinity, environment and prerequisite paths. They are evidence,
not commands executed by preparation. No historical 1,754-character literal
snippet is sent to the API.

Build receipt SHA256: `9b6fa7f397151c380a25f79dc3cf08abca1c70853300d7159febbf9456b35fbf`.

Device binary SHA256: `a68963d2e207ee6ad1aee0d0311bc319b2b2368f02132f48d67410951f12182b`.

After coordinator confirmation, the **single real submit command** is:

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env -u LMX_API_KEY OMP_NUM_THREADS=2 \
  python3 -B scripts/submit_localmaxxing_results.py \
  --payloads experiments/qwen38-flash-next-ud-iq3xxs-b70/data/20261015-own-rt-iq3-tp2-c4096-s23dr1-localmaxxing-payload-queue.json \
  --label qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-mtp1-c4096-s23dr1-realistic-20261015
```

Only the `--server-dry-run` version is authorized in this preparation. The
helper reads `~/.config/localmaxxing/api_key` directly; no credential is printed
or copied into evidence. Server validation status will be recorded below.

## Validation status

The coordinator authorized the narrow helper extension under the owner's
2026-10-15 decision. The helper now admits exactly these pinned identities:

- SPEED3 `75d2c459d`, 24/24 dr0, cards 0–1, seal `8460585f…`, headline
  38.15715689731613; already submitted as `cmv9j70v100v1le01q9jxyx2r`.
- SPEED6 `34c62b433`, 23/25 dr1, cards 0–1, seal `9b6fa7f3…`, headline
  39.42200890284251; prepared only.

The gate also pins the label, complete optimization identity, engine/binary
identity, model and suite. It checks the hash-bound result, attestation and
passing device quality windows. Removing authorization, changing the cap or
revision, flipping a pass marker, changing the headline or seal, moving to the
other card pair, or supplying diagnostic/unqualified receipts is refused.
There is no unconditional bypass. The 26 reviewed checks are committed as
individual unit tests, together with five extra identity/receipt checks; all
13 existing helper tests also pass: **44/44 total**. [Test receipt](20261015-own-rt-iq3-tp2-c4096-s23dr1-helper-tests.json).

The authenticated **server dry-run returned HTTP 200, `{"valid": true}`**.
The [response archive](20261015-own-rt-iq3-tp2-c4096-s23dr1-dry-run-response.json)
binds the exact queue and helper hashes and preserves the earlier local refusal.
No real submission was performed. The strict 512-cap gate remains false, and
run 1 remains the only prepared headline. The submit command above is for the
coordinator after confirmation.
