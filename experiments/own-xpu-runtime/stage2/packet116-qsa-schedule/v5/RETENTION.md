# Packet116 v5 retention

`build/` contains generated objects, binaries and CPU fixture scratch. It is
ignored and is not a source of published results. Restore the packet111 pinned
build first, then use `build_engine.py` and the CPU sequence documented in
README.md. `engine-commands.json`, build receipts and seals bind the exact
objects used; reused parent objects are named and hashed rather than copied.

`evidence/shape-*.tar.gz` retains the complete successful full-size CPU
capture/reset outputs, including argument comparisons, all five views and
allocation censuses. These archives are needed to review the startup evidence.
`retain_shape.py` verifies every member's original bytes before removing only
its generated scratch directory. The full-shape receipt records archive hashes,
member counts, compressed size and original size. No historical packet evidence
is removed. Failed compiler and capture-audit logs remain as focused evidence.

The CPU reports do not constitute GPU measurements or production qualification.
Any later device bracket remains conditional on both fresh micro kill gates.
