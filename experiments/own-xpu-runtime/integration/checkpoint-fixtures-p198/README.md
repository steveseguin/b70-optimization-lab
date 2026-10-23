# Actual p198 metadata store fixtures

The authorized CPU-tool probe passed on 2026-10-23. It inspected the original device S1 and S3 checkpoints through the new local store, replayed their exact small payloads through the explicitly admitted `v1.2+p198` bridge, and tested `in_use`, successful delete and proven missing on a **new tiny host-checkpoint copy**. Original checkpoints were unchanged. The [receipt](../receipts/native-checkpoint-store-tools-20261023.json) and [provenance](provenance.json) retain all five native tool calls and hashes.

The inspector was the pinned GNU `OWN_RT_HOST_ONLY` binary (`41cbb6c4…`). The checkpoint-producing device engine was a different, independently admitted binary (`c9b40108…`). This establishes metadata/tool compatibility and locking behavior, **not a working mixed-binary serving adapter or permission to restore device checkpoints into the GNU host engine**. Native restore still requires the exact checkpoint engine identity.

`*.inspect.json` and `*.manifest.json` preserve exact captured bytes. `*.small-payloads.json` encodes only tokens.bin and next_token.bin as hexadecimal. The expected device identity was admitted through fixed manifest hashes from the independent device audit and the sealed READY binary hash before it was used for bridge validation. Labels, contracts and native payload hashes were not rewritten.

The store held a native-compatible shared sibling lock throughout inspect and all small reads. Metadata mode confirms manifest/fields/file-set consistency; it does not hash large state blobs. The store additionally checks regular-file types, declared blob extents and the unchanged closed inventory. Logical storage, including metadata and tokens, was 69,121,547 bytes for S1 and 76,342,000 bytes for S3. Those are recorded live filesystem measurements, not values reconstructed by the offline fixture tests. Full state correctness remains supported separately by the earlier device lifecycle audit.

Replay without a native executable or original tensor files:

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 -B -m unittest discover -s experiments/own-xpu-runtime/integration -p test_native_checkpoint_store_fixtures.py -v
```

The [one-shot capture script](../probe_native_checkpoint_store.py) defaults to a read-only plan. Its original destinations are retained; it refuses overwrite or automatic retry. No GPU/model owner, generation, restart or new compilation was involved.
