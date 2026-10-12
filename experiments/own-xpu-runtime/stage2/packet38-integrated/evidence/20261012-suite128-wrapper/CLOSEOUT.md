# Packet 38: 128-token suite wrapper, 2026-10-12

The wrapper accepts caps 64 and 128, rejects other caps and any prompt plus cap
above the 256-token runtime capacity, and passes the cap to both ranks. The
existing 64-token manifest's context 192 remains admissible. Full emitted-token
equality and retained fixture steps 1–8 are checked without tolerance. The
128-token checker has no step-list API: its unchanged read-only implementation
validates oracle/input bindings, while the packet wrapper compares the actual
early fixtures. Steps 97–104 are explicitly reported as not retained.

**Native execution remains blocked for 128 tokens.** Contrary to the starting
assumption, `main.cpp:193` rejects `a.tokens > 64`. The unchanged GNU host mini
binary returned `bounded generation/context/deadline` before execution; see
[native-guard.json](native-guard.json). Native code, controllers, kernels and
binaries were outside this change's authorization. A separately authorized
native change, rebuild and qualification is required before WS128 can run.

The existing `decode_tok_s` uses `63 / (t64 - t1)` for a full 64-event span.
The added `submission_tok_s` uses the rate for the 99 inter-token intervals
between generated-token timestamps 1 and 100 after TTFT: `99 / (t100 - t1)`.
Timestamps are monotonic seconds. Every completion is retained; TTFT is
`1000 * (t1 - request_start)` (prompt work plus first token), and wall rate is
`output_tokens / (request_end - request_start)`. Both suite rates have an
all-request median and a median of per-prompt medians. They are not prompt-class
medians and do not establish an external promotion pass.

[tests.json](tests.json) records five passing regression groups: cap/context
admission, hand-computed timing and early ends, both summary aggregations,
exact oracle comparisons with corrupt last tokens and rehashed corrupt fixtures,
and full window-to-summary rehearsals. The hand example gives t1=12, t64=138,
t100=210: both interval rates are 0.5 tok/s, with TTFT 2 seconds from start=10.
WS and WSs each completed two requests with native host mini ranks at cap64;
mock ranks completed both windows at cap64 and cap128. These are six CPU
rehearsals, twelve measured test requests, no device or real-model execution.
The six named `*-native-mini-summary.json` / `*-mock-rank-summary.json` files
retain their final summaries. The older two `*-mini-summary.json` files and
[tests-attempt1.json](tests-attempt1.json) preserve the first attempt, which
exposed the manifest-context assumption and the native CLI guard.

[oracle-admission.json](oracle-admission.json) validates all twelve input/oracle
bindings at each cap, read-only. [verification.json](verification.json) proves
all 41 artifact hashes match [before.json](before.json), all other sealed source
hashes are unchanged, affinity is unchanged, and final build growth is zero.
No compiler ran. Test scratch remained small and was removed by the test harness.

Exactly these existing sealed source files changed:

- `pipeline.py`
- `suite.py`
- `window.py`

`test_suite_cap128.py` was added to the seal. `build-receipt.json` was resealed
by updating those source hashes and appending this wrapper amendment; both prior
coordinator amendments and historical gate receipts remain intact. `WINDOW.md`
was updated, along with this evidence directory. No native source or binary
hash changed. The final build receipt SHA-256 is
`d4eaadce9cea61eaaa8130237e03ca8399c607637183f5df37834e65d6431038`.

Reproduce the CPU regression from the repository root:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet38-integrated/test_suite_cap128.py
```

[WINDOW.md](../../WINDOW.md) contains the exact coordinator commands, including
fresh `K0d`, `K1ad`, `K1bd`, `K2d`, `W0pd`, and `KDd` prerequisites, and WS128 /
WS128s with `--repeat 1`. Those prerequisites must be rerun because the build
receipt changed. No device prerequisite was rerun during this CPU-only task.
The prepared 128-token commands become runnable only after the native guard is
addressed and the resulting native build is qualified.
