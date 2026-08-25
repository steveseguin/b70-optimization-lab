# b2dd TP1 context spine r1 closeout

Date: 2026-08-25. Classification: **passed supporting context probe; no exact
active-context matrix cells filled.**

The frozen b2dd/1e90 Qwen 3.8 AutoRound INT4 parent passed all nine retrieval
probes on one fresh TP1 graph-on/F16 server. Early, middle, and late markers
were recovered at each requested input size: 2K, 8K, and 32K. All responses
used 128 output tokens, exposed enough token-ID events for the decode window,
and reported zero cached input tokens. The canary, context gate, runner, and
post-run cleanup all passed.

The measured interval decode rate fell gradually with prompt size: the nine-row
range was `27.0706–30.2573 tok/s`, with a `29.3772 tok/s` median and
`28.9046 tok/s` mean. These are supporting measurements, not a replacement for
any protected short-suite speed. Speed was not a correctness or expansion gate,
and no historical value changed.

The tokenizer/API wrapper made the actual prompt counts 2,056–2,057,
8,197–8,198, and 32,003–32,004. Therefore this packet does **not** fill the
canonical `active_context_tokens` cells at 2,048, 8,192, or 32,768. It proves
serving retrieval and capacity near those depths and can calibrate estimates.
The 32K probes passed, so the preregistered 16K→24K boundary fallback is not
needed; the separate 4K/16K/24K supporting expansion remains eligible.

The structured closeout is
[`2026-08-25-qwen38-b2dd9ce73d-tp1-context-spine-r1.json`](../data/2026-08-25-qwen38-b2dd9ce73d-tp1-context-spine-r1.json).
The complete run remains under
`/home/steve/qwen38-current-main-runs/tp1-parent-sentinels-b2dd9ce73d-20260825-r1/01-context-spine/sentinel-context`;
its receipt and benchmark hashes are frozen in the closeout.

Next: preserve this result on pushed `main`, then run the preregistered
`p2-eager-control`. Exact-depth matrix measurements still require a harness
that accounts for chat-template overhead rather than relabeling these probes.
