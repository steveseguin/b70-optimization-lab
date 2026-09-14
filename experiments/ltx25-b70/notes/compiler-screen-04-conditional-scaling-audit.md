# Conditional compiler scaling and guard audit

2026-09-14. Source-only planning, conditional on native activation screen04 passing the existing exactness gates. This note records no measured guard overhead or speed benefit. No native imports, requests, implementation changes, or server actions were performed for this audit.

## Pinned sources

- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-05/source/scripts/ltx_block_compile.py` — SHA256 `c3f3e4ede85b2798981dca40562bd77586ad63afe55b043c0705fceddda29a1e`.
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-05/source/scripts/block_compile_node.py` — SHA256 `ddd49674e2603d79818eed3263a4bc6876163fc6b1a1731fb6e95136ceb1ebdc`.
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-05/source/scripts/ltx_native_activations_backend.py` — SHA256 `62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a`.
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-05/source/scripts/encoder_diagnostics.py` — SHA256 `f16d8cefa02dd7557c13348a95e6c0ce07a42c4d0f46b36329ab1c4f182a439a`.
- `/home/steve/src/ComfyUI-ltx25-baseline/comfy/model_patcher.py` — SHA256 `26da6710a7d84e8e98ea3e0f0bc07b88cfef3f99a7f7d59daa71e650512c6ed4`.
- `/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/_dynamo/config.py` — SHA256 `d44a413bf4274ff0ce4384fb0538c3c48a9972af963d8f30c5b16416892ee6b1`.

All adapter/node line references below refer to the packet05 source copies above, not the older lane templates.

## Measure the existing one-block candidate first

Exclude compilation and the first eager/compiled/repeat qualification for each stage from warm timing. Compare eager, compiled and restored requests in the same persistent server, retaining the full-clip bitwise oracle and lifecycle checks. Report request/diffusion wall time separately from selected-block execution time. Diagnostic work must either be matched across arms or separately reported; a negative end-to-end result remains a negative result even if isolated block execution improves.

The route performs three full lifecycle validations per normal selected-block invocation: adapter `__call__` line115, adapter `_call_native` line82, and node `_Gate.__call__` line155. Each reaches `_CompilePreRun._validate` (adapter195–212), which calls `_routes` and `_registered_binding`; `_routes` itself calls `_registered_binding` at152. Thus these paths each traverse the48-route registry twice. Two additional direct state/hook validations run at adapter116 and83. Together this is five state/hook validations per normal selected-block invocation, with one more census validation on the first invocation of each request (node107–108,158). Counts describe source control flow, not measured cost.

`_Gate` also reads diagnostic context, builds stage metadata, snapshots counters and writes one JSON receipt per call (node144–196). Eager/repeat forwards and CPU byte comparisons occur only when a stage is first qualified (node160–176); they are already absent from qualified warm calls.

## Guard placement

Source identity checks already occur during request admission and candidate construction. Static architecture census, immutable startup receipt parsing and diagnostic serialization can be consolidated at request admission/completion in a future sealed request design. Keep dynamic fault checks, current executing-patcher identity, registered-route binding, stage signature and routed numerical input-device checks effective during execution. Counter aggregation can move only if unexpected compilation still fails immediately through a backend/signature guard.

Do not simply move every structural walk to `pre_run`: adapter227–229 explicitly catches callback removal and late mutations after `pre_run`. Native `ModelPatcher.pre_run` sets `current_patcher` before callbacks (model_patcher1440–1444); cleanup clears it (1311–1315). A semantics-preserving first candidate should deduplicate checks within one invocation while retaining the post-routing binding/state validation and numerical input-device checks (adapter82–95). Broader once-per-request validation needs an enforced request immutability/invalidation contract and tests for late mutations. Full-clip equality alone does not replace lifecycle guards. Separating immutable receipt validation from cheap fault-latch checks must preserve immediate fault-halt behavior.

## Explicit blockers to multiple blocks

- Adapter45–47 constructs every backend with the same `native-activation-graphs` directory. The backend uses `directory.mkdir(parents=True, exist_ok=False)` in `make_backend`; constructing block two would collide. Use a sealed candidate identity and block-specific graph directories, with exclusive receipts retained.
- Adapter131–137 permits one selected route and one lifecycle guard;239–240 rejects an existing compiled route;258–266 restores exactly one. Node `_state` is singleton and node201–219 fixes admission to block24. These require a deliberate multi-block API, not repeated calls to the current one-block helper.
- Qualification currently admits two stage graphs and eleven calls for one block (node46–50,138–180). Multi-block accounting must bind block identity, route device, stage and backend identity rather than simply increasing a global counter threshold. Each selected block/stage needs exact qualification, with full-clip comparison after composition.
- Installed Dynamo config121/124 defaults to `recompile_limit=8` and `accumulated_recompile_limit=256`. These are source defaults, not observed failures. Shared code objects, multiple devices/shapes and successive candidates may affect cache behavior. Preserve compiler coverage and reject unexpected fallback; do not assume all48 blocks necessarily create exactly96 independent graphs or silently raise limits.

## One persistent application for future choices

Prepare one sealed runtime exposing preregistered backend choices and bounded block sets. Key candidates by original resident owner, backend/source hashes, compiler options and selected block set; keep original modules/parameters registered and reuse clone-local routing. Use one aggregate lifecycle guard and separate per-candidate/per-block qualification records. Restore original dispatch reversibly without unloading/reloading weights or resetting global compiler state. Bound the number of retained candidates and caches explicitly.

Changing a block selector should not require an application reload. New source must still enter through a reviewed immutable packet; no hot-editing imported modules. Preserve candidate-specific failure receipts, failed output hashes, and the campaign failure latch. A numerical failure stops that campaign; a host fault halts new requests. Selecting another candidate must never silently clear either condition. No implementation is proposed for activation before screen04's outcome is recorded.
