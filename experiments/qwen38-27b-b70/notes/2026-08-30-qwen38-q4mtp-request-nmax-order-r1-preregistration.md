# Qwen3.8 request MTP depth — order/state diagnostic preregistration

The request-level safety campaign passed all gates, but both hybrid arms
measured explicit MTP2 at users 1 and 2 only after a full MTP0-request sweep and
128 high-load semantic canaries. The replicated users=2 result (~49.2 tok/s) is
well below the earlier global-MTP2 fresh-server result (~67.8 tok/s). This
diagnostic is frozen before testing and cannot authorize a public speed claim.

Three fresh 64-slot MTP2 servers isolate the cause:

- `explicit-default`: explicit `speculative.n_max=2` at users 1,2 first, then
  the omitted/default request at the same points.
- `default-explicit`: reverse order on a fresh server.
- `pre-stress-post`: omitted/default users 1,2, then one explicit-MTP0 64-user
  batch, then the omitted/default users 1,2 again.

Every response must contain exactly 128 tokens, report zero cached tokens,
preserve complete token-ID evidence, avoid cross-base oracle collisions, and
pass the existing output-identity/isolation classification. No result from this
factorial is promotion evidence. Interpretation is fixed:

- explicit and default within 5% at matched order means the request field is
  not the cause;
- a post-stress regression greater than 10% with a stable pre-stress result
  identifies persistent server/device state or workload order;
- a consistent explicit-only regression greater than 5% rejects the candidate
  request path for MTP2 use pending a source fix.
