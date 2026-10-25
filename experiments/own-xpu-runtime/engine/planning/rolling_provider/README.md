# Opt-in rolling depth-two qualification

This adapter uses actual existing-MTP canonical and recursive proposals with
the generic ring coordinator. It supports 2/4/6 owner scheduling; this is not a
claim of measured speed or qualified GPU results for every topology. The first
model gate is bounded to 32 output tokens with every native diagnostic check
enabled. Existing pending/quiescent controllers and native defaults are unchanged.
No training is involved.

The lab entrypoint is `engine/tools/rolling_ring_driver.py`. It uses the existing
pipeline planner and guarded process lifecycle, so it still requires the
recorded adapter, model authority, compiled source receipt and local observer.
This is not the portable deployment entrypoint. CPU planning is the default;
execution additionally requires `--run`, an admission whose hash matches the
plan, and the owning unit. Plan regeneration verifies source/config/launch
identity before process creation. The controller contains no restart policy.

Use the existing pipeline configuration schema and resource/card identity, plus:

```json
{
  "rolling_depth2": true,
  "use_proposals": true,
  "verify_restore": true,
  "verify_recursive_restore": true,
  "verify_provider_survival": true,
  "eos_token_ids": [248044, 248046],
  "trusted_draft_manifest_sha256": "<independently trusted manifest SHA-256>"
}
```

The selected draft manifest must match that explicit SHA. Target placement/auth,
model/draft arithmetic, native binary and source, EOS, configuration and Python
dependencies are bound to the plan. Reference paths, scripted tokens, forced
miss positions and pending-gate cases are refused. Offline reference comparison
belongs exclusively to the independent finalizer.

```sh
python3 engine/tools/rolling_ring_driver.py --config CONFIG --plan PLAN
# The coordinator supplies a separately admitted unit/window for an actual run:
python3 engine/tools/rolling_ring_driver.py --plan PLAN --run --admission ADMISSION --unit UNIT
```

`arbiter.py` holds the final parent's immutable record until op27 completes and
fences stage-zero acceptance at the next canonical provider seed. `coordinator.py`
preserves the existing row/proposal ownership, shared wire sequences, two target
slots and global drain rules. `transport.py` services all owner sockets while
the provider runs; it uses the existing strict native codecs and owned stream,
hidden and final-record copies. Already issued recursive tokens retain their
original identities if a newer canonical proposal disagrees.

`commands.jsonl` (`ownrt.rolling-command.v1`) flushes each issued/completed event
before a later issue can reuse that owner's shared slot. It binds the full row,
original tentative flag and ROW ticket, raw request/reply and metadata, source
stream hash, target cursors/pending IDs and original proposal provenance.
Provider issues additionally bind the accepted seed sequence and owned final
record. Completions retain exact raw 192-byte proposals and transport replies.
`final-records.jsonl` retains each validated 360-byte final record and hidden
hash/extent. `provider-batches.jsonl`, `schedule.jsonl` and `tokens.jsonl` retain
decoded proposals, scheduler decisions and only actual target outputs.

The plan schema is `ownrt.rolling-driver-plan.v1`. The truthful result sidecar
`rolling-ring-live-result.json` has schema `ownrt.rolling-driver-result.v1`,
mode `rolling-ring-live-depth2-qualification`, and hashes the unchanged inherited
lifecycle result and plan. Controller completion does not replace independent
v6 provenance replay, target/canonical-draft state comparison or native provider
survival checks. Diagnostic timings are not a throughput result.

The internal transport can model explicit cancellation by draining reserved
work and abandoning an unused final-record lease. Its conservative
`cancelled_provider_incomplete` flag excludes that request from ordinary final
state qualification; it does not assert measured corruption. The launcher does
not expose that optional callback: guard stop/failure uses the existing
cooperative shutdown path. Normal EOS/cap and miss recovery preserve canonical
provider progression. Native RESET is refused.

The original design, failures, CPU prototype and independent review remain in
`../rolling-provider-next/`. Promoted CPU checks are:

```sh
python3 -m unittest discover -s engine/planning -p 'test_rolling_provider*.py' -q
PYTHONPATH=engine/tools:engine/planning python3 -m unittest discover \
  -s engine/tools -p 'test_rolling_ring*.py' -q
```

The 19 tests cover event ordering, both miss depths, immutable old recursive
guesses, EOS, 295 cancellation boundaries, real fragmented socket codecs,
shared sequences, raw witness completeness, invalid replies and final markers,
manifest/capability refusal and guarded lifecycle injection. Worker arithmetic
is synthetic; these tests do not constitute GPU/model proof.
