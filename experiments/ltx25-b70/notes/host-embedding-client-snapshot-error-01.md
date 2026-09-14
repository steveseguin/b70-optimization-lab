# Preserve the primary request failure when the server disappears

2026-09-14. During packet11 request11, the request client failed when the server was OOM-killed. The parent screen's `finally` then called the post-request `/proc` snapshot. That missing-process error replaced the primary request failure in `progress.json`, although the original helper traceback remained in the per-request client log.

Inactive [client v2](../scripts/run-host-embedding-screen-v2.py) changes only this diagnostic handling: a failed request stays primary; if the subsequent snapshot also fails, its exception is recorded under `after_snapshot_error`. If the request succeeds but its snapshot fails, postflight remains fatal. No parity, result, lifecycle, retry, timeout or native admission gate is weakened.

The frozen original client remains unchanged. This successor retains packet11 admission and is not compatible with the unqualified residentv2 receipt schema. The active fault latch and existing-campaign refusal still prohibit another packet11 run. It was not launched or connected to any endpoint.

Four stdlib actual-helper-AST tests passed: original failure object preserved with missing-server snapshot, successful request plus failed snapshot remains fatal, failed request plus successful snapshot preserves metadata, and ordinary success. See [receipt](../data/host-embedding-snapshot-failure-stdlib-01.json), [log](../data/host-embedding-snapshot-failure-stdlib-01.log) and [focused patch](../patches/host-embedding-client-snapshot-error-01.patch). These tests use fake callbacks and perform no native or endpoint action.
