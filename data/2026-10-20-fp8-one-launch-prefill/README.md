# FP8 overlay 0.2.0: six-request synthetic prefill screen

The October 20 run on two selected B70s in `steve-b70s` measured a median
**2164.0807055481273 input tokens/s** at exactly 512 input tokens, with
request-level values from **2128.1513553457826** to **2197.1585271100416**.
Each value is 512 divided by the one-request vLLM prefill histogram duration,
from first scheduled execution to first token. It is not isolated GPU kernel
throughput or HTTP TTFT. All six request rates are retained in
[summary.json](summary.json); the aggregate is the median of six rates, not
median-of-class-medians. No warmup contributes.

The unchanged recommended FP8 package runtime used overlay 0.2.0, MTP5,
one sequence, a 33024-token window and physical cards 0/1 (PCI 23/27).
There were two measured repeats of each synthetic prose/code/docs prompt:
512 numeric input IDs, 128 forced output tokens (`ignore_eos`), temperature
zero, explicit zero cached tokens. Each pair's complete 128 output IDs
matches. No no-MTP reference was compared in this screen. Writing rates use
99 intervals between numeric tokens 1 and 100; SSE burst tokens share arrival
timestamps. HTTP TTFT includes the client adapter's passive admission guard.
These are diagnostic observations, not a new headline or quality promotion.
The historical turin 90.3 tok/s pair and steve-b70s 46.013 tok/s strict
acceptance retain their separate definitions and evidence.

[manifest.json](manifest.json) binds all 91 files and the compressed
[evidence archive](evidence.tar.gz). The archive contains `run/` raw receipts,
`source/` snapshots of all 20 run-pinned code/config files and
`preregistration.json`. Model/cache binaries and empty lock files are omitted;
model identity is retained through the direct/ordinary SHA256 verification
receipt. The source output remains at
`/mnt/usb-models/bench-results/fp8-one-launch-prefill-20261020-a2`.
The earlier admission-only attempt is separate and is not pooled here.

This run used a manually started persistent service and a separate client;
the prohibited host benchmark controller was not executed. The server was
manually stopped once with owned SIGTERM, drained cleanly at
`2026-10-20T04:00:15.396179+00:00`, and was not restarted. Passive kernel
receipts contain no matches to the pinned package's GPU fault expression.
The raw journal also retains unrelated AppArmor denials; it is not an empty
system journal.

Verify all hashes and recompute request counts, input/output IDs, cache
accounting, repeated outputs, 99-interval decode rates and histogram rates:

```bash
python3 tools/extract-fp8-one-launch-prefill.py
python3 -m unittest discover -s tools -p test_extract_fp8_one_launch_prefill.py
```

The extractor also verifies source/preregistration hashes, exact Docker argv,
model verification, passive fault scans and TERM drain receipts. `--write`
regenerates the summary and six package observation rows from these retained
bytes; it performs no GPU, network, Docker or service operation.
