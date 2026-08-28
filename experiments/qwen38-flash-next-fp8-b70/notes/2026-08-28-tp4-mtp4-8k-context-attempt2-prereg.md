# Flash-Next TP4 MTP4 active-8K attempt-2 amendment

Date: 2026-08-28

Attempt 1 completed every server startup gate and confirmed the preregistered
36-block allocation yields exactly 9,504 cache tokens. The client then failed
closed before creating request artifacts because the supervisor had been
invoked through a repository-relative path while the client required its
absolute path in `/proc`. Live metrics proved zero prompt, generation, draft,
draft-token, and accepted-token counts. The registered failed-request sentinel
performed controlled shutdown; no listener or B70-addressed event remained and
all four cards were rediscovered below 43 MiB. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-8448-context-attempt1-pre-request-stop.json`.

Attempt 2 changes only operational identity:

- invoke the supervisor by its absolute path;
- use `ATTEMPT=2`, port 19672, state
  `/tmp/q38-mtp4-8448-supervisor-a2`, and fresh attempt-2 run, evidence,
  cache, compile, and RPC paths;
- retain the exact model/source/runtime, MTP4, eager mode, 423,641,088-byte
  cache, 36-block admission requirement, p8192/o128 request, MTP0 authority,
  non-gating MTP2 comparator, four-position mechanism assertions,
  1,200/1,210/3,000-second bounds, sentinels, and all protected data hashes
  from the parent preregistration.

There is still exactly one authorized inference request for attempt 2. No
attempt-1 model request exists, so this is not a repeat chosen after seeing
model output.

Frozen attempt-2 executable identities:

- launcher wrapper:
  `e7f4d8c8dd2950ab5d6a1b32e729f1f5da1d9cc320bde320431723120d9b172b`;
- one-request client:
  `147b8910e8a219f2b743edfe433e75ba29ef7c3cc4fce4da1b883d7595536e7d`;
- lifecycle supervisor:
  `ccdc31ce4876c0dc3a97fb436cc6fb5ad01da9b15e363a985497beecc5deefa9`.

Any further executable or identity change requires a new attempt and paths.
