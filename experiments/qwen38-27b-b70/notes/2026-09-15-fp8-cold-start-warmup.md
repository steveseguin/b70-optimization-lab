# FP8 service: first-request slowdown and the warm-up fix

Restored FP8 services measured 54.0-54.3 tok/s on the strict suite, versus
54.855 on the pre-test control. The whole gap was one prompt:
`incident-retrospective`, always the first request, ran at 42.8 tok/s with a
0.70 s first-token wait on every freshly started server (including a September
14 run from before any of the tests), but 56.5 tok/s and 0.12 s on the control,
which ran on a server that had already served requests. The server log shows two
Triton kernels for the MTP draft step (`eagle_prepare_next_token_padded_kernel`,
`eagle_prepare_inputs_padded_kernel`) compiling during that first request. The
other 11 prompts matched the control within about 1%.

[`serve.py`](../../../packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py) now
sends one untimed 64-token greedy completion before it reports the server ready.
Prompt caching is off, so it cannot help any later prompt.

| Run | Writing speed, tok/s | First prompt, tok/s | First-token wait, s |
| --- | ---: | ---: | ---: |
| Pre-test control (already-used server) | 54.855 | 56.55 | 0.117 |
| Fresh server, no warm-up | 54.306 | 42.77 | 0.707 |
| Fresh server with the warm-up | 54.762 | 56.54 | 0.142 |

All three runs produced the same 12 complete answers. A separate rerun on a
warm server while another agent was busy on the CPU dropped two prompts by 10%
and 37%; decode on this host is sensitive to other CPU load, so benchmarks
should run on an otherwise idle machine.

Evidence: `/mnt/fast-ai/bench-results/optimization-validation-20260915/restored-strict*`,
`final-warmup-strict*` and [copied receipts](../data/2026-09-15-fp8-one-card/).
