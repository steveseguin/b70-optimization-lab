# Packet45 SPEED3 LocalMaxxing payload — prepared, not submitted

2026-10-15. This packet prepares the same submission schema and 128-token
measurement scope as the October 13 record. It does not record a real
submission or change the public record. The owner has authorized this scope;
the coordinator retains the real submission step.

The target is the same Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS GGUF, revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`, on a new lab runtime revision.
This quantized compressed model is a separate lane from official FP8.
SPEED3 is `75d2c459d`, packet45-merged3, arithmetic `iq3-p17-detmath-v2`.
Two B70 cards, cards 0–1, each hold one rank; target layers are split 24/24
and the official one-token draft runs on rank 0. The native controller,
K2-selected kernels, small-FFN repair, full-state write-set rollback and
single-pass draft profiling are enabled. Accepted draft tokens are verified
by the unchanged target. KV storage stays full 16-bit BF16; the API enum has
no BF16 value, so the payload uses `apiKvCacheDtype=auto` while retaining the
literal BF16 identity.

Context capacity is 4096. This 24/24 rank-0-draft configuration is not admitted
at 32768. Boot: `13858eef-ec68-44ea-a67c-9444933b7100`.

| Measurement | SPEED3 |
|---|---:|
| Primary: median of six prompt-class medians, 99 intervals between events 1 and 100 | 38.15715689731613 tok/s |
| All-prompt median of that 99-interval rate | 38.00415100384534 tok/s |
| Decode median, 63 intervals between events 1 and 64 | 38.2350201374308 tok/s |
| Median wall rate, including prompt and complete generation | 26.933965381469946 tok/s |
| Median TTFT | 1358.4201005287468 ms |
| Median acceptance | 0.7913385826771654 |
| Requests / generated tokens | 12 / 1536 |
| Median input / output tokens | 68 / 128 |

The previous submitted record remains
[`cmv6pugme0020oa01fjrho6nx`](https://www.localmaxxing.com/runs/cmv6pugme0020oa01fjrho6nx),
37.85626413203107 tok/s. This observed SPEED3 value is 0.79483% higher.
That small difference is not a statistical confidence claim. This packet
packages one complete SPEED3 speed suite and does not pool repeat windows.

Each of the twelve fixed varied prompts ran once in the speed suite after a
distinct excluded kernel warmup and a complete reset. Every request records
zero cached tokens. There is no prompt/KV/response reuse, history acceleration
or prompt selection. All requests reached the declared 128-token cap without
an earlier EOS. Full natural-completion throughput and 512-input-token prefill
were not measured; the per-request cap-limited rates remain in the result JSON.

## Quality evidence and scope

All five copied window receipts are passing, qualifying, device-executed and
bound to the same seal, artifact hashes, dispatch, boot and split. Their device
process IDs are distinct across windows; no owner remained alive at completion.

| Device window | Token comparison | Retained layer fixtures | Role |
|---|---:|---:|---|
| W2m | 64/64 | 384/384 | Development-prompt exactness |
| WS | 1536/1536 | 4608/4608 | Fixed suite exactness |
| WSs | 1536/1536 | 4608/4608 | Sequential target-only comparison |
| WS128x | 1536/1536 | 9216/9216 | Exactness at steps 1–8 and 97–104 |
| WS128 | 1536/1536 | 0, intentionally unretained | Timed speed suite |

The preparation script independently compares every stored emitted token to
the immutable arithmetic-v2-detmath oracle and across WS, WSs, WS128x and
WS128. It verifies each request's original hash against its window receipt,
recomputes all 99-interval rates and the class-balanced headline, and checks
cached-token counts, timestamps, output lengths and token hashes. Retained
fixture equality is established by the passing device checker receipts; this
preparation does not rerun model arithmetic or the fixture checker.

Passing W2m, WS, WSs and WS128x device evidence is the seal-6 amendment's
real-model exactness authority. Historical CPU evidence does not qualify this
new runtime's speed. Window journal tails contain no new fault signatures.
Preflight logs include the previously recorded October 11 faults; this is not
a claim that the entire boot had no historical fault.

**Owner authorization, 2026-10-15:** "authorized: submit under the same
128-token scope as the October 13 record." The authorized scope is identical
to submission `cmv6pugme0020oa01fjrho6nx`: the same fixed realistic twelve
prompts, cold responses, cached_tokens=0, 128 generated tokens per prompt,
and the primary metric over 99 intervals between events 1 and 100.
The requested cap is **128**, not 512.

The packet's own strict gate remains **false**, with its unedited reason:

> measurement preparation only; cap below fixed 512 and no promotion attestation; repeats/partial suites never qualify

This is the original runtime summary's reason; the separate preparation now
provides a hash-bound promotion attestation. It does not rewrite that summary
or claim a strict 512-cap pass. The attestation keeps the October 13
`lab.promotion-attestation.v1` schema, not the newer strict neural.download
attestation schema.

The named eligibility exception is
`packet45.speed3.owner-authorized-128-token-scope.2026-10-15`, stored in
`engineFlags.realisticSuiteScopeException`. The helper checks its dated owner
text, prior submission, 12 × 128 scope, runtime/model/suite/seal identity,
24/24 split, rank-0 draft, cards 0–1 and run 1's headline. It also verifies the
attestation and performance JSON hashes, matching authorization and raw gate,
and per-row token counts and hashes. The helper still refuses without this
authorization, even if somebody flips the ordinary pass marker. Both
`realisticSuiteGatePassed` and `strict512TokenFinalGatePassed` stay false.
All other qualification, caching, history and metric checks remain active.

Thirteen focused helper tests passed, including nine exception tests with
negative controls for absent/malformed authorization, changed scope, changed
runtime, changed hashes, a substituted higher repeat, diagnostic receipts and
incorrect interval accounting. The authenticated `--server-dry-run` returned
**HTTP 200, `{"valid": true}`**. No real submission was performed. The
[response archive](20261015-own-rt-iq3-tp2-c4096-s24dr0-dry-run-response.json)
also preserves the earlier local refusal while authorization was pending.

## A-B-A confirmation; run 1 remains the headline

| Run | Cards / draft rank | All-prompt median tok/s | Class-balanced tok/s | Use |
|---|---|---:|---:|---|
| SPEED3 run 1, WS128 | 0–1 / 0 | 38.00415100384534 | **38.15715689731613** | Pre-registered submitted value |
| SPEED3 run 2, WS128-r2 | 0–1 / 0 | 38.03062796232048 | 38.21692500912173 | Confirmation only |
| Interleaved packet44, c4096ctl15a/WS128-r2 | 0–1 / 0 | 37.79376800760946 | Not recorded in legacy summary | Control |
| SPEED3 run 3, WS128-r3 | 0–1 / 0 | 38.043132779622724 | 38.21434624879848 | Confirmation only |
| Earlier packet44, c4096ctl15a/WS128 | 0–1 / 0 | 37.74977984928242 | Not recorded in legacy summary | Control |
| SPEED3 other configuration, speed3-c4096-dr1-gpu/WS128 | 2–3 / 1 | 37.866263682541074 | 38.131238029183585 | Separate configuration; not submitted |

All run paths, raw window hashes, original request archives and exact metrics
are in the [confirmation evidence](20261015-own-rt-iq3-tp2-c4096-s24dr0-confirmation-evidence.json).
The three rank-0 SPEED3 runs share boot `13858eef`, seal receipt `8460585f…`,
revision `75d2c459d`, artifact hashes, dispatch, target split and chain. Each
explicitly records qualifying=true. The packet44 controls have the older
schema without a qualifying field: their passing device receipts are retained
verbatim, alongside the owner's designation as qualifying controls.

Monotonic token timestamps establish the A-B-A order: SPEED3 run 2
(370157.352886–370371.183696), packet44 control
(370776.239777–370915.412943), SPEED3 run 3
(371331.351312–371545.563204). They do not overlap. The preparation recomputes
all six suites' conventional 99-interval medians from timestamps and verifies
all 128 output tokens per prompt against run 1. The rank-0 repeats preserve
the same dispatch; the other card pair has its own measured dispatch.
Higher repeat values are neither substituted nor pooled into the headline.

## Files and reproducibility

All files in this packet start with
`20261015-own-rt-iq3-tp2-c4096-s24dr0-`:

* [Payload queue](20261015-own-rt-iq3-tp2-c4096-s24dr0-localmaxxing-payload-queue.json).
* [Suite result](20261015-own-rt-iq3-tp2-c4096-s24dr0-realistic-suite-v1-result.json).
* [Promotion attestation](20261015-own-rt-iq3-tp2-c4096-s24dr0-promotion-attestation.json).
* [Verification and original input hashes](20261015-own-rt-iq3-tp2-c4096-s24dr0-verification.json).
* [Preparation script](20261015-own-rt-iq3-tp2-c4096-s24dr0-prepare.py).

The five `*-window.json` files are byte-for-byte copies. Each
`*-request-receipts.json.gz` contains original request bytes encoded as base64,
with source paths and SHA256 values. Decompress the JSON array and decode
`raw_base64`; the decoded bytes must hash to each member's `sha256`. This keeps
the evidence reviewable after the coordinator archives the active build path.
No model weights, binaries or state dumps are copied. No file under
packet45-merged3 or packet44-context was created, modified or deleted during
preparation. The confirmation archives add six original window receipts and
six compressed archives of twelve original request receipts each.

`promptSha256` and `outputSha256` are taken from the WS128 receipt's compact
JSON integer-token-array hashes. Their encoding is explicit; they are not
borrowed from the old payload's differently encoded hashes. The full exact
WS128 command, including `--target-split 24`, `OMP_NUM_THREADS=2`, dispatch and
exactness companion, is recorded in `engineFlags.commandSnippet`. It is a
coordinator command, supplied as evidence and never executed by preparation.

Build receipt SHA256:
`8460585fe53879223066a5d54799c9f105c73002adfc09fc9a743ceaee7e3fa8`.

Device binary SHA256:
`724e4dee068d38c561a97e0a2814c470b7f07cc9e5ec24f0297ebd904aed8fc8`.

The real submit command, **only after coordinator confirmation**, is:

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env -u LMX_API_KEY OMP_NUM_THREADS=2 \
  python3 -B scripts/submit_localmaxxing_results.py \
  --payloads experiments/qwen38-flash-next-ud-iq3xxs-b70/data/20261015-own-rt-iq3-tp2-c4096-s24dr0-localmaxxing-payload-queue.json \
  --label qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-mtp1-c4096-s24dr0-realistic-20261015
```

Adding `--server-dry-run` validates against the authenticated no-write endpoint.
The helper reads the existing `~/.config/localmaxxing/api_key` directly; the
credential is never printed or copied into this packet.
