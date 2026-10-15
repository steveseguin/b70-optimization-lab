# Packet45 SPEED6 LocalMaxxing payload — prepared, not submitted

2026-10-15. Run 1 is the pre-registered headline. This packet prepares a
submission under the owner's existing 128-token exception. It does not submit
or change the public record. The coordinator retains submission and the
pending A-B-A confirmation.

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
raw gate, plus the explicit SPEED6 extension. No unconditional marker bypass
is used. The historical `lab.promotion-attestation.v1` and
`lab.realistic-suite-result.v1` schemas match the SPEED3 packet.

## A-B-A confirmation — PENDING COORDINATOR

**Placeholder: confirmation windows are queued/running. Do not mark this
section complete until the coordinator adds their qualifying receipts.**
Run 1 remains the headline regardless of subsequent values.

| Run | Cards | All-prompt tok/s | Class-balanced tok/s | Status |
|---|---|---:|---:|---|
| SPEED6 WS128, run 1 | 0–1 | 39.269033659702785 | 39.42200890284251 | Registered headline |
| SPEED6 WS128-r2 | 0–1 | Pending | Pending | Coordinator to fill |
| Interleaved packet44 c4096ctl15a/WS128-r3 | 0–1 | Pending | Pending | Coordinator to fill |
| SPEED6 WS128-r3 | 0–1 | Pending | Pending | Coordinator to fill |

Add source paths, immutable receipt hashes, boot/seal identity and timing order.
Do not replace the headline with a higher repeat or pool the runs. The matching
`confirmation-evidence.json` is explicitly pending with no invented results.

## Files and exact commands

All new files use prefix `20261015-own-rt-iq3-tp2-c4096-s23dr1-`.

- [Payload queue](20261015-own-rt-iq3-tp2-c4096-s23dr1-localmaxxing-payload-queue.json).
- [Result JSON](20261015-own-rt-iq3-tp2-c4096-s23dr1-realistic-suite-v1-result.json).
- [Promotion attestation](20261015-own-rt-iq3-tp2-c4096-s23dr1-promotion-attestation.json).
- [Verification](20261015-own-rt-iq3-tp2-c4096-s23dr1-verification.json) and [preparation script](20261015-own-rt-iq3-tp2-c4096-s23dr1-prepare.py).
- [Pending confirmation](20261015-own-rt-iq3-tp2-c4096-s23dr1-confirmation-evidence.json).

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

The first `--server-dry-run` attempt was **blocked locally (exit 2)** before
reading the API key or contacting the server. The existing helper's scope path
is pinned to SPEED3 `75d2c459d`, its seal, 24/24 dr0 and its headline. SPEED6
correctly fails that current check. This is not an HTTP failure or server
approval. No pass marker has been flipped and no bypass was applied.

A narrowly pinned SPEED6 extension requires permission to change the helper
and its tests outside the task's new-data-only commit boundary. That permission
was requested. A proposed patch was tested in memory only (26 positive/negative
checks passed); the repository helper remains unchanged. The submit command
above becomes usable only after that extension is approved, applied and the
server dry-run succeeds. See the [current dry-run response](20261015-own-rt-iq3-tp2-c4096-s23dr1-dry-run-response.json).
