# Packet140 — body-lever screening closed

[Ranked analysis](ANALYSIS.md) · [closeout](CLOSEOUT.md) ·
[negative index](DO-NOT-REPEAT.md) · [work note](../../../../notes/2026-10-18-own-runtime-packet140.md)

No new exact target-body mechanism supports the required +3% projection on
the 58.223834 two-card line. The broadest new proposal projects +1.305% with
20% transfer; its +5.433% sensitivity requires an unsupported 80% transfer.
No implementation, device proposal or readiness marker was created.

The [calculation](analysis.json), [complete negative-index search](prior-search.txt)
and [retained inputs](inputs.json.gz) distinguish record intervals from
instrumented class timings and pre-fusion roofline estimates. The record
reproduces exactly; the independent threshold check gives +3.000000000000003%.
[Verification](verification.json) and [retention rationale](RETENTION.md).

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet140-body-lever/analyze.py --check </dev/null
```

This is a CPU analysis packet. Its conditional device workflow is unentered,
not an unfinished build or a request to queue anything.
