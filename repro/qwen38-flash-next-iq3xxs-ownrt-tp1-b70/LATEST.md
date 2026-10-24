# Flash-Next own runtime: October 23 closeout

The current one-card capped record is **37.595605 tok/s**. The runtime also
completed a separate single-owner streaming and checkpoint test. These are
different measured configurations; the buildable full-512 replay below retains
its original identity and measurements.

| What you need | Verified result | Recipe or evidence |
| --- | --- | --- |
| Build the published sources | One-card rebuild passed two device runs at 31.827 / 31.813 tok/s, with complete outputs matching the sealed line | [Source build](BUILD.md), [full-512 replay](README.md) |
| Inspect the newest one-card record | 37.595605 tok/s, twelve prompts with a 128-token cap, all 1,536 output IDs exact | [Completed record](../../experiments/own-xpu-runtime/stage2/packet196-onecard-diet-chain/RESULT.md) |
| Inspect the two-card record | 63.611824 tok/s under its separate 128-token protocol | [Two-card recipe and limits](../qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md) |
| Use an already admitted experimental chat endpoint | Sixteen turns, seven SSE and nine JSON replies; all 1,484 output IDs and final retained states matched their references | [Streaming result](../../experiments/own-xpu-runtime/stage2/packet201-streaming-serving/RESULT.md), attach command below |

## Check the latest record without loading a model

From the repository root:

```bash
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/verify-current-record.py
```

The [verifier](scripts/verify-current-record.py) reads the retained record and compressed evidence, checks their hashes,
and recomputes the submitted metric. It does not contact the submission API,
load weights, access a GPU, start a service or rerun a benchmark. The evidence
bundle is about 42 MB compressed; allow memory for its decoded members. The
[retained verification](manifests/current-record-verification.json) reproduces
the exact record metric and all twelve oracle comparisons.

The measured record uses Unsloth revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`, target-only greedy decoding,
full BF16 KV, context 4096, and the following selected settings:

```text
--expert-gateup diet
--cache-cap max23
--cache-bytes 23049601024
--wait-policy spin
--foreground-io kernel
```

These are identity settings, not a complete launch command. The measured engine
SHA-256 is `537c080767f241653a8ac13c77289cd59e8f7444cbee2a4fcb35586eb1e743d4`.
Its seven qualification stages passed. The final metric is the median of six
prompt-class medians over the 99 intervals between generated tokens 1 and 100.
The [approved submission](https://www.localmaxxing.com/runs/cmvl5k4p9004nng01z5xtanw5)
supersedes the matching 36.602512 tok/s cache-capacity record.

The original record launcher and preparation README are historical inputs:
their fixed output directory is already consumed. They are not reusable
fresh-host commands. This record also depends on retained local build objects;
the published clean-source builder still reconstructs the separate full-512
profile. A new record replay requires a fresh, reviewed host/device admission
and a newly qualified binary if rebuilt. Do not rewrite historical seals or
reuse a completed output directory.

The 128-token record has no second independent timing repeat, full-512 quality
promotion or matched 512-token prompt-reading result. The separate full-512
profile remains 31.510–31.782 tok/s with oracle coverage limited to the first
128 output tokens. Neither profile establishes general model quality or
equivalence to official FP8 weights.

## Attach to the tested streaming interface

The serving pilot uses the unchanged checkpoint engine, context 4096, full
BF16 state and a **21,552,729,600-byte** expert cache. It is not the max23 record
binary above. One loaded owner completed all sixteen RUN and SAVE dispositions
and exited cleanly. Streaming and ordinary replies matched, and final saved
state was independently checked. This establishes bounded serving correctness,
not a new throughput record or a production-service release.

Once a coordinator has supplied an admitted loopback endpoint and model name:

```bash
cd experiments/own-xpu-runtime/integration
python3 -B -m chat_cli_v1 --endpoint http://127.0.0.1:PORT \
  --model MODEL --session conversation-a --prompt 'Explain this briefly.'
```

Replace `PORT` and `MODEL` with those supplied values. This attach-only client
does not launch or stop a server. Omit `--prompt` for successive turns on stdin;
use `--ordinary` for JSON replies. The client itself has CPU socket/replay
qualification and was not the client used in the native serving test. See its
[protocol, limits and failure behavior](../../experiments/own-xpu-runtime/integration/chat_cli_v1/README.md).
The historical serving controller is not a portable service installer.

## Research closed for this publication

The later two-row prefill, publication and expert-sharing work remains outside
these measured recipes. CPU correctness and compile-only checks do not qualify
a native performance improvement. The final expert-sharing proof passed 100
checks across 17 synthetic cases after fixing NaN operand priority; both failed
attempts are retained. See [the proof and its limits](../../experiments/own-xpu-runtime/stage2/packet215-two-row-iq2-expert/README.md).

No GPU run was performed for this closeout. Native prefill qualification,
full-output quality beyond the existing oracle span, portable admission,
concurrent users and first-use phase attribution remain unqualified. The prepared native
launch paths remain disabled or unadmitted. Further optimization is closed at the
owner's request; none of these research candidates is silently promoted into
the published measured recipe.
