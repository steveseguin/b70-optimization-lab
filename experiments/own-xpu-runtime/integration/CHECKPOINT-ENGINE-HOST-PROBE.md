# Host-only integration probe — corrected attempt B passed

The [compact closeout receipt](receipts/checkpoint-engine-host-b-closeout.json)
records **8 requests, 44 generated tokens, 5 SAVE + 3 RELEASE controls**, one
model load and clean stopped with exit code 0. Actual append versus fresh tokens
and state were exact; edited-prefix prefill and same-ID reinspection/release
passed. This is synthetic context64/vocab16 GNU HOST_ONLY integration, with no
device/model qualification or HTTP wiring. The source closure and small payloads
are retained in [checkpoint-engine-host-b](receipts/checkpoint-engine-host-b),
and all 177 raw artifacts have recorded sizes and digests. Large diagnostic logs
remain local in ignored scratch.

[checkpoint_engine_host_probe.py](checkpoint_engine_host_probe.py) prepares one
unchanged packet198 GNU `HOST_ONLY` owner, with tiny context64/vocab16 geometry.
Read-only plan:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/integration/checkpoint_engine_host_probe.py --plan
```

The exact reviewed launch command used for attempt B was:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/integration/checkpoint_engine_host_probe.py --run-host-only
```

All generated files go to the fresh ignored
`stage2/packet198-postreply-checkpoint/build/engine-integration-b` directory.
Existing outputs refuse; the frozen host proof remains unchanged. The probe
binds its owner and native metadata tool to the same sealed GNU binary. A three-row
synthetic identity TSV supplies an explicit digest for new fixture manifests;
this is not a model identity or a claim about real-model arithmetic. No bridge
validation is weakened to admit the earlier mini fixture's empty identity hash.

Attempt A failed at the first SAVE because its empty TSV did not satisfy the
native writer's three-row identity requirement. Its exact script, source closure,
configuration and full small run evidence are preserved under
[lineage/checkpoint-engine-host-attempt-a](lineage/checkpoint-engine-host-attempt-a),
with a [failure/drain receipt](receipts/checkpoint-engine-host-attempt-a-failure.json).
The native receipt reports safe teardown and no device execution, and the owner
PID was absent at closeout. The revised fixture uses three explicitly named
`synthetic-host-shard-*` rows with five zero-valued stat fields each. Mini mode
does not read model shards; these are synthetic metadata, not filesystem/model
claims. The plan derives the complete expected model identity from those exact
TSV bytes and rows. Attempt B is a separate reviewed launch, not an automatic retry.

Its eight replies cover A parking, B no-save release, restored append versus
fresh token/state equality, edited-prefix prefill, and final no-save release and
clean stopped. One deliberate fresh replay exercises the actual same-ID parking
shortcut followed by explicit adapter RELEASE. This phase skips normal
`before_request`, which would correctly delete the prior checkpoint when given
the repeated shorter prompt. Automatic non-None/same-ID RELEASE inside
`run_turn` remains separately covered by the synthetic CPU unit test.

The host harness allows one cooperative SIGTERM to its exact retained host PID
on failure, followed by a bounded wait; it never kills, retries or restarts.
The adapter itself still does not signal. The harness checks helper-core/nice19
placement, a 4 GiB process address-space limit, and the 27 GB free-space floor.
No native owner was executed merely by preparing or checking `--plan`.
The completed attempt B cannot be rerun in place; future replay needs a fresh,
separately reviewed scratch output. No further native execution was performed
to capture this closeout.
