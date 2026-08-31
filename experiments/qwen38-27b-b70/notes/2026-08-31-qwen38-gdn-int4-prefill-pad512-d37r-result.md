# Qwen3.8 packaged GDN pad D37r result

D37r is **not** a candidate-repair result. The non-invasive wrapper supplied
the same hidden input hash in four fresh processes and received four different
outputs, but a later traceback and neutral-directory import audit proved r2's
server runtime did not contain the patch. It measured the unmodified baseline.

The attempted D38 active-source trace then failed because the server imported
the site-packages module, which lacked r2's helper. This evidence resolves the
path: the actual server uses the seven-argument site-packages GDN source that
D36 traced successfully. D39 tests r1, which patches that runtime copy.
