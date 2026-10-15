# Packet45 SPEED3 LocalMaxxing payload — prepared, not submitted

2026-10-15. This packet prepares the same submission schema and 128-token
measurement scope as the October 13 record. It does not record a real
submission, change the public record or authorize a later submission.

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

**Strict final gate:** the source summary explicitly records
`realistic_final_gate.passed=false`: it is measurement preparation at a
128-token cap, below the repository's fixed 512-token final gate, with no
promotion attestation at runtime. The source marker is retained verbatim in
the prepared result and attestation. A legacy 128-token submission exception
must be explicitly authorized before setting the submission helper's pass
marker. It does not turn the strict 512-token gate into a pass. The attestation
keeps the October 13 `lab.promotion-attestation.v1` schema requested by the
owner; it does not claim to be the newer strict neural.download attestation.
The owner-exception decision is pending. The prepared queue currently keeps
`realisticSuiteGatePassed=false`. The requested `--server-dry-run` command was
invoked; the helper stopped at local preflight with exit 2 and
`missing realistic-suite final gate pass marker`. No HTTP request was sent.
See [dry-run response](20261015-own-rt-iq3-tp2-c4096-s24dr0-dry-run-response.json).
After a written exception for this historical scope, rerun the preparation
script with `--owner-128-exception`, rerun server dry-run, and retain its
response before any real submission. Neither an exception nor a submission
has been inferred from elapsed time or a successful schema check.

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
packet45-merged3 was created, modified or deleted during preparation.

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
