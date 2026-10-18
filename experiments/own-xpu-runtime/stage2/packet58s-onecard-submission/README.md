# Packet58s: one-card submission preparation

CPU-only tooling for the sealed packet58g `evidence/card0-58g-a` queue. It reads
finished evidence and writes only beneath this packet's `submission/` directory.
It never starts a runtime, reads a key, contacts an API, or submits a result.
The separate `submission_cli.py` is for the coordinator's explicit dry-run and
submission steps; it uses the shared CLI unchanged except for the local validator.

Run the commands in [the coordinator note](../../../../notes/2026-10-18-own-runtime-packet58s.md).
Tests:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/stage2/packet58s-onecard-submission \
  -p 'test_*.py' -v < /dev/null
```

The preparer requires all seven completed queue stages and passing receipts,
the exact packet58g build seal, source/artifact/gate hashes, clean kernel logs,
fresh owners and completed drains. It checks every emitted token against the
unchanged packet49 CPU oracle. KD/W2m/WS retained layers must also match its
hashes. WS, WS128x and WS128 must each contain all twelve fixed prompts with
128 tokens, cold request resets and zero cached tokens. The oracle path used by
58g resolves to `/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results`;
there is no alternative oracle or tolerance. Any other authority is refused.

Only WS128 supplies rates. The primary rate is the median of six prompt-class
medians, each prompt using `99 / (timestamp[99] - timestamp[0])`. `tokSTotal`
is the all-prompt median of `128 / (last timestamp - request start)`, matching
the two-card tool. TTFT, all-prompt median/mean/p10, class medians, prompt/output
hashes, timestamps and 100-event/99-interval accounting remain in `result.json`.
The copied `suite_metrics.py` keeps packet58g's receipt accounting exactly.

The result is plain greedy TP1, **no draft**, full BF16 KV at 4096. Host-pinned
expert weights back an 18 GB device cache. Cache fills copy missing immutable
weights; the K1 receipts select the fallback miss path. This weight cache is
distinct from prompt, KV or response reuse, all of which remain disabled.

The requested 128-token owner scope is explicit. Strict512 stays false.
WS128x confirms exactness under possible shared load. It does not become a
timing repeat; the missing second whole-host timing run stays false in result,
attestation and payload. Preparation makes no completed speed-verdict claim.

The new threshold ledger is
[`scripts/packet58_onecard_record_threshold.json`](../../../../scripts/packet58_onecard_record_threshold.json).
An empty history means **no locally recorded matching submission**, not a zero
public record. The authenticated public read was blocked by Cloudflare; the
public best is unknown. After a successful coordinator submission,
`--update-record RESULT_JSON --submission-id ID` replays the original evidence
and appends a strictly higher local threshold. It never verifies an ID online
and never lowers or overwrites history. A stale payload is rejected if a later
local threshold already meets or exceeds its rate.

Original small receipts and sealed sources are retained in `evidence.json.gz`.
Native binary artifacts, retained BF16 fixtures and verbose logs retain their
verified SHA-256 and byte counts instead of duplicate payloads. Layer hashes
are compared to the hash-bound CPU validation records. Offline replay needs
neither the model weights nor the original experiment directory. The queue is
written last, after result and attestation replay. Frozen trees are never edited.

Synthetic fixtures use a different build seal, admitted only by an in-process
test patch. They cannot pass the unmodified production preparer. Tests invoke
the shared CLI's `--dry-run` with network access explicitly forbidden.

Adaptation sources are recorded in `provenance.json`: packet91's current
submission builder/wrapper, packet58g's receipt/oracle checks, and the exact
packet56 metric module. Packet84's restored tool was not edited or copied over.
