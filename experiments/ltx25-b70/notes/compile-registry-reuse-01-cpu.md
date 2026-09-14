# Registry binding reuse: native CPU lifecycle checks

September 14, 2026. The inactive adapter candidate reuses the selected binding
returned by the complete route/placement scan, eliminating the immediate second
scan in lifecycle validation. All other per-call checks remain in place. This
is a source-backed response to the negative one-block compiler timing result.

The parent and candidate both passed the preserved native ModelPatcher.pre_run
lifecycle rejection suite, plus an unselected-block registration mutation check.
The candidate also passed returned binding equivalence for indices 0/24/47,
unchanged two-result default API and rejection of invalid indices. A test-only
call counter observed two full registry walks per parent validation versus one
per candidate validation, both during pre_run and direct native dispatch.
No timing benefit is inferred from that count.

The compiler was a dispatch spy: these tests establish lifecycle/ownership
behavior, not compiled tensor equality or GPU performance. The source delta
leaves native computation and all remaining pre/post-routing validation calls
unchanged. Independent source review found no blocker for native static registries.

Evidence: data/compile-registry-reuse-01/; complete parent/candidate/patch and
pins: patches/compile-registry-reuse-01/. Test:
scripts/test-compile-registry-reuse-cpu.py. Candidate SHA
4fe9f3e8ed962a0e50e53b00734c9095290f58e6a16dcff998db5282a819b970.
It is not deployed. PID 17769 remains idle on packet05 after 27 exact clips.
Next native qualification must preserve both stage and full-clip oracles and
measure actual sampler/full-clip effects before calling this a speed win.
