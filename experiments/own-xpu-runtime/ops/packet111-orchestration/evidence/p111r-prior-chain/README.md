# Prior active chain metadata

These are the exact active packet111 metadata bytes before packet111r selected
the already-sealed combined view. They retain the base/base chain's source,
binary, selection and submission bindings without changing any prior evidence.
The large build receipt and screen seal are required to review that complete
binding, not just a hash of it. Retain them alongside historical decision
`762f6ebd546b0092`.

Restoration source: the same leaves under
`experiments/own-xpu-runtime/stage2/packet111-record-bundle/` at commit
`40cfa4ac6cb35e568450f6ccd0d3a18ea5e3e105`; extract using `git show
40cfa4ac6cb35e568450f6ccd0d3a18ea5e3e105:<path>` and compare bytes before use.
They are historical evidence, not the current launch configuration.
