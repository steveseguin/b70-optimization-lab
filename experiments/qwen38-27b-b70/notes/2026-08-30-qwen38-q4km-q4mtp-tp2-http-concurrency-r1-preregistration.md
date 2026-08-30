# Qwen3.8 27B Q4_K_M + Q4_0 MTP2 TP2 HTTP concurrency R1

Status: **preregistered before execution**.

## Question

Does the newly qualified two-B70 Q4_K_M + Q4_0 MTP2 deployment preserve its
single-user advantage under synchronized HTTP concurrency, and at what point
does matched MTP0 become the better aggregate-serving policy?

## Frozen campaign

- Hardware: the two local Intel Arc Pro B70 cards; no remote host.
- Runtime/model identities: the exact hashes from the promoted 64.237301 tok/s
  package.
- Server: TP2 equal target split, draft on SYCL0, F16 target/draft KV, graph
  off, reasoning off, prompt cache disabled, 64 slots, 32768 total configured
  context (512 tokens per slot), batch 1024, ubatch 256, eight CPU threads.
- Work: the frozen eight-prompt small-context suite expanded uniquely at
  concurrency 1/2/4/8/16/32/64; 128 output tokens per request; one repeat per
  point.
- Arms: one fresh MTP0 server, followed by two fresh MTP2 servers. No result
  may be reused from an older binary or server.
- Metric: aggregate completion tokens divided by synchronized batch wall time;
  each published MTP2 point is the median of the two fresh-server values.
- Output gates: all responses complete at 128 token IDs, cache counts all zero,
  no cross-base oracle collision, output-isolation qualification, and a
  separate 64-way exact-answer canary for two rounds on every server.
- Stability gate: the two MTP2 aggregate values at every point must have a
  relative range no greater than 10%.
- Cleanup: every attempt must stop its server and leave both local GPUs idle.

No point may be interpolated or extrapolated. Multi-user greedy tokens are
allowed to vary with batch shape only if the frozen isolation and semantic
canary gates pass; such a curve must be described as output-isolation-qualified,
not token-identical. A failed gate retains diagnostic evidence but publishes no
speed.
