# Independent interpreter and capture review

Reviewed actual candidate bodies, submission adapters, frozen v2 Core, generated checked GEMV mirrors, guard generation, and dispatch consumption. No device program was run.

New candidates use compile-time Op and Phase/Stage selection. I found no new Batch/Chain kernel, device command-descriptor loop, or pointer-indirected hot parameter block. Data/scratch/RoPE/route buffers are legitimate inputs; they are not parameter-block substitutes. The frozen Core evaluator, baseline Glue, and baseline ng::group retain their original runtime operation selection and are reference/default paths, not new candidates.

The packet6/7/8 mirror narrows each launch to a by-value descriptor and specializes weight Type on the host; no matrix-descriptor search remains in submitted bodies. Packet9's proven expert projection retains its same-shape one/two-matrix indexing and type template.

At inspection, static object symbols contained **132 capture-size instantiations across 12 objects**, maximum **744 bytes**; every inspected capture is below 1,024 bytes. This is an intermediate object snapshot while the main build continues, before the subsequent fixed-route specialization rebuild.

Findings and follow-up source review:

- **I1 (fixed_source_reviewed)** `dispatch.hpp`: Class lookup does not normalize blk.<layer>. prefix; attn.combine/ffn.combine and per-class GEMV table keys miss real plan sites unless every exact label is emitted. Reviewed class_name() prefix removal and new_for/gemv_for exact-label then class lookup in current dispatch.hpp.
- **I2 (fixed_source_reviewed)** `kernel_gate.py`: Capture recognizer accepts [&]; sizeof closure guard alone cannot mechanically enforce by-value capture. Reviewed kernel_gate.py explicit assertion rejecting [&] device closures. All other unsupported capture forms remain fail-closed through recognizer.
- **I3 (open)** `main.cpp:selected_variant`: Additional packet25 GEMV names cannot be enabled as table edit alone: only existing 0..7 variants are registered and unknown names throw. Register/link supported packet25 candidate names before advertising table-only adoption, or clearly record unavailable candidates.
- **I4 (fixed_source_reviewed)** `adapter.cpp:SimpleNew`: Production route selects SimpleNew with runtime n/top; specialised_submit fixed route<512> applies to fixture API, not production route path. Reviewed SimpleNew/submit/body FixedN/FixedTop templates and production host choice simple_new_submit<Op::route,512,10>; mini/odd shapes retain fallback.

Architecture check passed: the new candidate paths have no interpreter or parameter-block indirection. Full review remains open only for the requested future packet25 table-only integration: names are accepted by JSON but unknown implementations are correctly rejected until linked. Exact reviewed source hashes and capture symbols are in `review-interpreter.json`. This review makes no performance or arithmetic-identity claim.

Final disposition: the later independent [bridge addendum](review-bridge-addendum.md) resolves I3 for the six explicitly linked names. The original inspection above remains an intermediate snapshot. The final compiled image contains 165 capture instantiations, still at most 744 bytes, in [kernel-sizes.json](kernel-sizes.json). Unsupported packet25 names remain rejected. [Follow-up identity](review-interpreter-followup.json) binds the later evidence.
