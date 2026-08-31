# Qwen3.8 runtime-sitecopy GDN pad D39 preregistration

Date: 2026-08-31

Status: **preregistered before D39 model requests**

The actual server imports the site-packages GDN module. Image r1
`sha256:03da963d9d9b3b2cfc5cb7d9f1bc0aeb9ebd7e1b9495e3cad4e5b9e5dd4fc493`
patches that module; a neutral-directory receipt confirms its helper exists and
uses M=512. Image r2 patched an inactive editable copy, so its D37r negative is
not evidence against the repair.

D39 runs r1 with the non-invasive tracer from D37r. It calls the packaged
production forward unchanged, then hashes input/output after completion.
Across four fresh processes, the input hash, output hash, complete trace, and
all 64 generated token IDs must match. A pass authorizes the strict
varied-prompt determinism and independent quality gates, not a speed claim.
