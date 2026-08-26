# Qwen 3.6 embedded-Q8 Q8KV exact-2K classifier R2 result

Classification: pre-request harness failure, no inference evidence and zero
publication authority.

All six GPU-backed server lifetimes initialized successfully, exposed the
expected model alias, and cleaned up without forced kills or survivors. The
first client process in every arm then exited with status 2 before making an
HTTP completion request. Consequently the run contains zero exact-depth
receipts, six zero-byte stdout placeholders, no server-side slot-launch or
prompt/decode timing marker, and zero GPU inference requests. Model loading did
occur; this is specifically a zero-inference-request finding, not a claim that
the GPU was never initialized.

The raw arm errors retain the six failing commands. They passed per-arm repeat
labels such as `q8kv-exact2k-mtp0-repeat-1` through `--case-id`. An inert
post-run `--check` reproduction returned `unknown fixture case id`, while the
fixture's actual 2K case ID is `depth-2048`. The original subprocess stderr was
not captured, so the deterministic check is disclosed as post-run confirmation
rather than represented as a raw log.

This result cannot classify MTP0/1/2/3/4 behavior, output stability, the prior
2K split, throughput, draft counters, or quality. It authorizes no site cell,
curve expansion, speed or graph claim, protected replacement, record, or
LocalMaxxing submission.

The raw root is
`/mnt/fast-ai/bench-results/qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-20260825-r2`.
Terminal SHA is
`ff88e3db558098cae20d604a46aa73e688715c4c5216a754c630ff223bd5f510`,
identity SHA is
`38179f3f8025c8400d5219630833776c31fabab169815ca39312272852f85467`,
and the complete 33-file inventory SHA is
`2ca36f247d2dfc3c5e6a4c40549f37313ea813a4fd5eb5c98160e49e5254493d`.
