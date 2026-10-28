Prepared source and CPU tests; no plan, model, or device run.

The harness uses the current parent planner and build-registration-r2.json for binary 42458c9016fc7e6b62c9f175278d52ecaa6c3a1316a5030a3fcb10fd9fc1425a. It reuses C.execute, adapter6.reset, and the sealed state reader. Canonical runtime sources are unchanged.

The root config must specify the original 244-token prefix, context 4,096, cut 23, F32, no draft, max_new=1, reference_tie_diagnostic=true, and the exact registered receipt. Root owns planning, admission, and launch:
  python3 .../remaining-regressions/run.py --config CONFIG --plan PLAN
  nice -n 19 taskset -c 8-15 python3 .../remaining-regressions/run.py --plan PLAN --run --admission ADMISSION --unit UNIT

cases.json authenticates historical input files, CPU rows, and packed prefixes. The order is technical-guide prefixes 244, 330, 489, 531, 541; bug-report-synthesis prefix 527; then technical-guide 244 again. Only prescribed input IDs and a one-token output cap reach the target controller. CPU argmax is compared afterward. A mismatch is a finding, without retry or lifecycle failure. C.execute sends one final FINISH after all seven requests. A protocol failure preserves partial evidence and halts the lifetime.

Before the first request and after each real OP11 reset, both owners receive sentinel DUMP 2,147,483,647, which also emits the real inventory. The sealed reader verifies every source. Later cold bundles are compared byte for byte to the initial bundles; the canonical source maps and host/unrepresented-allocation inventories must also match. Only launch_extent and alternate_launch_extent may differ: each must be an integer multiple of 32 within context. Their initial and retained values are reported separately, with the source-proven rebind to 32 before the first HALF. Native reset receipts must report success, preserved allocation IDs, and consistent allocation counts and byte totals. No cold-state claim is manufactured.

The outer sequence audit records each actual transport send through the existing start method. Existing receive validates the matching reply. Internal scalar HALF traces do not expose wire sequences; this harness does not invent them.

Each request validates all forced positions, no speculation or guesses, 48 F32 layer captures, and complete per-position/per-layer router journals. Every changed slot needs equal raw score words, and selected weight hashes must remain unchanged. Both owners receive a final prefix-length DUMP. The first and last 244-token cases must have identical output, authenticated canonical source maps, and complete final bundle bytes.

Evidence forecast: 6 GiB, roughly fourteen 430.5 MB bundles plus captures and journals. The existing evidence floor is required in addition; host, runtime, and root filesystem floors remain unchanged. All dumps are retained.

Source proof: cache-source-proof.json pins Engine.admit_position, its call before HALF, inventory field production, and the legacy reset source. Prepared launch extents are retained and rebound; this is not a claim of complete identical host state. GPU model bytes and every other inventory field remain strict, including loaded_layer, fp32_cache, histories, and unrepresented allocations.

Nine bounded CPU tests passed in 0.063 seconds: input authority mutation; changed/truncated bundle bytes; outer sequence gaps; partial reset without retry; receipt and sequence validation; missing journal entries, unequal tied words, or changed weights; omitted forced positions; and only the two proven cache fields may differ, with other fields and malformed extents rejected; and identical payload bytes cannot hide renamed canonical sources. These tests do not qualify actual native cold reset or persistent operation.
