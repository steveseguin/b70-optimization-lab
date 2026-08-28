# Flash-Next TP4 MTP4 active-8K attempt-2 amendment

Date: 2026-08-28

Attempt 1 completed every server startup gate and confirmed the preregistered
36-block allocation yields exactly 9,504 cache tokens. The client then failed
closed before creating request artifacts because the supervisor had been
invoked through a repository-relative path while the client required its
absolute path in `/proc`. No metrics snapshot or durable client error transcript
was retained; the no-request conclusion is a control-flow inference from the
frozen pre-network identity check and absence of every request artifact. The
registered failed-request sentinel performed controlled shutdown; no listener
or B70-addressed event remained and all four cards were rediscovered below 43
MiB. Receipt:
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

## Observed attempt-2 result

The absolute-path retry passed every startup gate with 36 cache blocks, 9,504
reported cache tokens, 1.12x maximum concurrency at the 8,448-token cap, and
four 12.22-GiB offload receipts. Its sole p8192/o128 request returned exact
8192/128/8320 usage, zero cached tokens, a length stop, 128 token IDs, and all
25 generic exact-depth checks. The conventional 99-interval rate was
4.02562915156999 tok/s after a 918.432851015008-second TTFT; both figures are
diagnostic only.

MTP4 mechanism evidence passed: 41 drafts produced 164 draft tokens and 86
accepted tokens, with positive accepted-position deltas `[30, 24, 18, 14]`
whose sum is exactly 86. The candidate output hash
`a1890c804678cbc523d2e070c60bd0446bf05091ab205aad651c0b00278d1e8c`
first differs from the frozen cross-runtime/cache MTP0 authority at zero-based
generated-token index 26. This is therefore a scoped Grade-D parity quarantine;
it does not isolate MTP4 as the cause and receives no speed, quality, or
deployment credit.

The completed-classification sentinel returned supervisor code zero.
Application shutdown and engine drain completed; no listener, recorded server
group, compile path, or RPC path remained, and all four cards were rediscovered
below 43 MiB. The five-second shutdown grace expired, after which the process
manager force-killed the remaining EngineCore and the executor sent SIGTERM to
four workers still running after its grace period. The intentional stop also
emitted the known AsyncLLM output-handler notice and one shared-memory cleanup
warning. Six corrected Source-514 records name only the local NVMe endpoint at
`0000:01:00.0`; no B70 event appears.

The 49-entry raw manifests verify with SHA-256
`c786f83af22b6350533464230188f701418522667ab78048d45ab1a15a7e2f55`.
The structured receipt is
`data/20260828-tp4-mtp4-8448-context-attempt2-parity-quarantine.json`.
This closes the practical TP4 eager-text matrix at 25/25 classified while
preserving the 20.72717637199404 tok/s MTP4 short screen, the 15.50156510641242
tok/s MTP3 exact-4K result, and every other captured speed unchanged.
