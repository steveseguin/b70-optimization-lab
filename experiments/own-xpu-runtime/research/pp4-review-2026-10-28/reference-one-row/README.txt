Current result (October28): the guarded4096-context target-only run completed
cleanly and reproduced token6343 against independent CPU16568 at the exact244-token
prefix. All48 GPU layer outputs are retained in gpu-4096/ with their identities.
This rules out speculation as the cause of this selected disagreement; it does
not resolve the six independent-reference disagreements.

CPU observer r1 failed: original and callback-off logits were bitwise equal;
callback-on cancelled graph evaluation at the cropped final layer and produced
incomplete captures/stale logits. cpu-r1/ retains that failed experiment.
CAPTURE-R2.txt documents the source-confirmed cause and corrected observer;
its full-logit neutrality gate is pending. Do not use r1 layer captures as an oracle.

Historical CPU preparation follows. The preliminary65,536-context proposal below
was superseded by the actual guarded4096 run; it is not an execution recipe.

input.json contains the exact saved technical-guide first 244 token IDs, score_from244/full_rows[243]. identity.json pins input bytes, packed little-endian int32 token hash, model identity, current df2c binary, old engine identity, context65,536, F32 precision and independent CPU top10. reference-row.json retains the original full top20 row. Reference argmax16568; historical engine6343. Current output is an observation, not a predetermined pass/fail expected sequence. No new reference execution occurred.

prepared-plan.json derives argv/environment/card mapping from the source-valid df2c final512 colocated plan, WITHOUT changing that plan. It replaces only fresh output/transport paths, --max-new1/--retain-steps1, removes draft launch flags and selects target-only request mode. The two rank model identities, dispatch, context, precision and build receipt remain inherited. Context is65,536 rather than historical4096: therefore a difference requires checking launch extent/context geometry as well as changed source, not attributing it to MTP automatically. Use fresh output paths if this proposed path exists when executed.

Existing exact API to reuse under a separately guarded, admitted coordinator:
  adapter = isolated current-build adapter with validated argv hooks
  transport = adapter.Transport(..., check=guard.check, launch_hook=registered_launch)
  result = adapter.NativeController(transport, adapter.BASE.Draft('none'),
             overlap=False, dumps=False, prefill=0, start=0).run(tokens, 1, ())
  transport.close(True)

Reuse colocated_control.py's Guard, current-receipt/source validation, passive observations, per-card exclusivity, process registration and incident cleanup. Its make_plan/bind_adapter/execute are deliberately fixed to1677/512/MTP and MUST NOT be called unchanged for this diagnostic. No ready generic guarded entry point was found; root can make a narrow separate wrapper with the above request, without modifying its final512 plan. prepared-plan is execution_ready:false and not an authorized launch document. Before execution pin the new wrapper/input and freshly validate current receipt/source hashes, actual planner floors and cards. No retry, restart or hard signal. This preparation creates no admission.

Native fixture identity: native_controller.hpp fixture(p)=max(0,p-prompt_length+2), so consumed position243 is fixture1; --retain-steps1 captures that row in both ranks. rank.hpp publish writes step1/layer-NN.bf16 even for F32 streams. Require exactly48 unique layer files across ranks, each40,960 bytes (4 streams x2,560 x4); decode little-endian F32, reject20,480-byte BF16. Do not infer BF16 from filename. Native rank publish does not write layers.jsonl; derive rank/layer ownership from native plans. Check result contains exactly one output, zero speculative guesses, correct rank trace positions0..243 and no speculative=true rows, clean exits and health. Record output alongside both reference16568 and historical6343. No timing claim for one output. Captures are end-of-layer only, not operator localization.

CPU reference command API already exists:
  GGML_CPU_EXACT_F64=1 EXACT_KV=f32 <pinned exact-logits binary> <same model GGUF> input.json <fresh-output-dir> <threads>
The saved build-hashes.txt pins the historical tool. Resolve its actual existing path and original model manifest before running; do not silently substitute an unpinned llama.cpp executable. Its existing full_rows option saves logits-243.f32; no graph callbacks are implemented. Root requested CPU preparation only: no GPU, build, reference model load, service launch or canonical edits performed.
