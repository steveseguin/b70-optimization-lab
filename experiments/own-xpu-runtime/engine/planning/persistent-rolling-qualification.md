# Persistent rolling: cold requests, fixed process policy

CPU-tested opt-in implementation; native/GPU qualification is pending. The old
rolling, pending-provider, quiescent and wavefront entrypoints keep their behavior.
There is no training, process restart, automatic continuation or device action
in the suite helper. The owning coordinator admits the single guarded lifecycle.

## Configuration and authority

Use `tools/persistent_rolling_driver.py --config CONFIG --plan PLAN` for CPU
planning. Execution additionally requires `--run --admission ADMISSION --unit
UNIT`, exact regenerated plan equality and its independently admitted digest.
The original base pipeline config still supplies build receipt, adapter,
placement, card boundaries, model/context, resources, explicit EOS set and trusted
draft-manifest digest. Add:

```json
{
  "persistent_requests": true,
  "rolling_depth2": true,
  "use_proposals": true,
  "check_policy": "qualification",
  "verify_restore": true,
  "verify_recursive_restore": true,
  "verify_provider_survival": true,
  "max_new": 32,
  "admitted_max_new": 32,
  "suite": "/absolute/path/to/inputs.json",
  "suite_sha256": "INDEPENDENT_INPUT_FILE_SHA256",
  "suite_prompt_count": 2,
  "dump_each": true
}
```

The first qualification requires exactly two requests, at most 32 outputs each,
and full state dumps after both. For a separately admitted measured process,
`check_policy` is `measured`, all three diagnostic booleans are false, and
`measured_policy_admitted` must be true. Every policy is fixed in all native
argv; RESET cannot change it. An explicitly admitted per-process cap can be at
most 512, with each request at or below it. Checked copies, errors, proposal
restoration, target truth and wire provenance remain required in measured mode.
This does not certify measured-policy parity or performance before its evidence
gate. A later twelve-request plan is separate from this first two-request proof;
there is no implicit extension of a live session or policy switch.

Runtime inputs have exactly this schema. Reference answers and cached-token
assertions are forbidden in the input file; output comparison is offline.

```json
{
  "schema": "ownrt.persistent-rolling-inputs.v1",
  "model_identity_sha256": "MATCH_ADMITTED_MODEL_AUTHORITY",
  "activation_dtype": "F32",
  "eos_token_ids": [248044, 248046],
  "prompts": [
    {"id": "first", "prompt_tokens": [1, 2, 3], "max_new": 32},
    {"id": "second", "prompt_tokens": [1, 2, 3], "max_new": 32}
  ]
}
```

The token arrays above illustrate syntax, not the actual 87-token proof cohort.
Each request's immutable identity binds the process identity, suite digest,
model/draft/arithmetic/context/EOS, policy, index, epoch, id, prompt and cap.
Identical prompts still get distinct request identities and independent state.

## Reset and owner continuity

Native capability must include `pipeline/ring/persistent_reset.inc` and
`pipeline/ring/reset_descriptor.hpp` in the fully source-verified build receipt.
All owners receive `--pipeline-ring-persistent-requests` and
`--pipeline-ring-check-policy qualification|measured` in addition to the existing
actual rolling flags. Qualification retains all three native verification flags.

Before the first request and every later one, all target/provider commands must
be drained: empty wire buffers, no pending target rows, equal physical/committed
frontiers. The preceding rolling drive also checks its provider lease/job drain.
No first ROW is admitted until every RESET reply and receipt has passed.

For owner `N`, write `ORIGINAL_NATIVE_OUTPUT/reset-GLOBAL_SEQUENCE.json` using
exclusive creation. Descriptor schema `ownrt.ring-reset-request.v1` binds
`stage_id`, `global_sequence`, `previous_epoch`, `next_epoch`,
`previous_request_sha256`, `next_request_sha256`, `destination`, and empty
`oracle`. Destination is a fresh `ORIGINAL_NATIVE_OUTPUT/requests/request-NN-ID`.
The initial process epoch zero advances to one for the first prompt, then two.
Global wire sequence never restarts, including diagnostic DUMP commands.

Op11 has zero token/position/fixture/speculative fields; its reply must have
zero status/token/ready/bytes and exact sequence/rank/stage/final identity. The
native `ring-reset.json` (`ownrt.ring-reset.v1`) binds the descriptor and metadata
hash, monotonic reset index, fixed policy, zero target positions/pending, zero
first-owner draft position/provider serial, extents 32, cleared counters/traces,
no sticky errors, invalidated shared publication, and identical before/after
allocation inventory digests. Nonprovider fields are null on other owners.
The controller independently observes all complete shared mappings are zero.
Only then does it clear Python target/provider ledgers and seed a fresh rolling
coordinator with the new epoch/request and each owner's preserved wire sequence.
Any partial reset, malformed receipt, stop or fault fails the outer lifecycle;
no retry and no next prompt occurs.

## Evidence and timing

Per request, retain `request-plan.json`, `reset-commands.jsonl`, unchanged v6
command/proposal/final-record/token/schedule journals, `driver-result.json`, and
`result.json` (`ownrt.persistent-rolling-request-result.v1`). The reset journal
keeps raw requests/replies, descriptors/receipts and hashes. The request result
binds complete driver evidence, native output paths, epoch/request, previous,
initial, final and post-dump owner sequences, output/prompt hashes and clocks.
`cached_tokens: 0` is emitted only after actual validated cold-reset receipts.
It means request state is cold; resident weights, runtime and filesystem caches
are retained.

`suite-result.json` has schema `ownrt.persistent-rolling-suite-result.v1`.
`persistent-rolling-result.json` (`ownrt.persistent-rolling-result.v1`) binds the
existing lifecycle result and plan; it never turns a failed lifecycle into a pass.
Summary final output/state positions apply to the last request only. Full state
dumps are bounded to two-request qualification; a later full suite retains final
state only unless independently budgeted. Per-request DUMP markers are
`2000000000+index`; the outer lifecycle performs its existing final sentinel dump.

Decode is `(N-1)/(last committed token time-first committed token time)` for
`N>=2`. TTFT and full response are separate, exclude reset/dump, and full response
includes final provider/drain work. Recorded values are controller observations;
all results retain `speed_claim: false`. Independent audit must validate every
request's native reset, provider/target state, journals and expected output bytes
before drawing performance conclusions.

CPU validation:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=engine/tools:engine/planning \
  python3 -m unittest test_persistent_rolling test_rolling_ring_socket test_rolling_ring_driver -v
```

The new fixtures use actual fragmented socket messages and codecs across 2/4/6
owners, cold identical/different prompts, both diagnostic policies, incorrect
guesses, stale/truncated replies, corrupted reset receipts, stale publication,
partial all-owner reset failures and preserved wire sequences through DUMPs.
They do not substitute for native reset/state qualification on GPUs.
