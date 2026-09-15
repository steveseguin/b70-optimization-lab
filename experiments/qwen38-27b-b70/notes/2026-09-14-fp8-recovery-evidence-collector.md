# Recovery and MTP metadata evidence collector

[New collector](../scripts/collect-fp8-recovery-metadata-evidence.py) creates a
separate packet for `/mnt/fast-ai/bench-results/fp8-mtp-recovery-metadata-20260914`.
It reuses the frozen prior archive, strict-output, context and RPC replay helpers
without changing them. No old operator stages are required or copied.

Collection requires `campaign-completion.json` with a terminal `status`
(`completed`, `blocked`, `closed-after-gpu-fault` or `closed-after-failure`),
`finished_at` and explicit `final_service.status`. If the client was never run,
include `client_not_run_reason`.

A ready final service must name its evidence:

```json
{
  "status": "completed",
  "finished_at": "EXACT UTC CLOSE TIME",
  "final_service": {
    "status": "ready",
    "source_dir": "final-service",
    "strict_dir": "final-strict"
  }
}
```

`source_dir` may instead be `recovered-service` or `research-server`;
`strict_dir` may be `recovery-strict`. The collector requires the named service
state to be ready and the complete strict outputs/canaries to qualify. A ready
recovery claim also requires the positive health admission to verify.

After closure:

```bash
python3 experiments/qwen38-27b-b70/scripts/collect-fp8-recovery-metadata-evidence.py \
  --snapshot-label final-service-checked
python3 experiments/qwen38-27b-b70/scripts/collect-fp8-recovery-metadata-evidence.py --verify
```

It preserves the explicit health, recovery, research, client and final-service
stages, all strict numeric outputs, canaries, parity receipts, context raw SSE,
metrics, RPC/native results, launch identities and source snapshots. Service
logs carry a `point-in-time/<label>/` prefix; a ready snapshot never implies the
process stopped. Missing stages are represented as absent, never successful.
The old fault and incident are referenced by the hashes of their frozen packet,
summary and fault receipt. Baseline strict/context bytes come from the verified
frozen AMD evidence archive, with original path mappings retained for parity and
preregistration replay. No live historical files are substituted.

Health replay independently generates the expected FP16 copy/compute and XCCL
sum bytes using Python `struct`, then compares all six recorded output hashes.
It verifies both rank receipts, normal cleanup, source pins, completed state,
container exit, ownership and the health kernel window. No raw tensor outputs
were retained by the health worker: this is a deterministic expected-value
health check, not target-model quality or custom communication qualification.

Completed metadata screens require all five strict attempts, all four context
profiles and the complete native/RPC transition and rank-counter proof. The
summary explicitly excludes independent-process speed confirmation and
promotion. Archive and summary replay require matching frozen helper source.
Collection refuses to overwrite an existing manifest.

Eight synthetic CPU tests pass. The closed health stage was separately replayed
successfully; an in-memory corrupted output hash was rejected. No active service
logs or campaign packet were collected during these checks.

## Additions after the research-stage incident (2026-09-15)

- `health-after-research-oom` is a registered phase and is replayed with the
  same expected-value checks as `health`.
- A research `postflight.json` (`neural.download.research-server-postflight.v1`)
  is bound to the unchanged owner receipts it pins (`state.json`, `stop.json`,
  `server.log` and others), must confirm container exit on the same boot, must
  record no GPU fault signature and no served request. Its full kernel windows
  stay local and are referenced by hash only.
- After a failed research stage, a ready final-service claim also needs a later
  passing health check that starts after the research container exit and
  finishes before the final service starts.
- The stale ready-claim test now checks the instance binding requirement.
  Twelve synthetic CPU tests pass.
