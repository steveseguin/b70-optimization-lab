# Embedded-Q8 MTP3 exact-depth R1 pre-GPU failure

R1 stopped before server or GPU launch at the runtime-closure parser. Its
terminal receipt is preserved at
`/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r1/terminal-receipt.json`
with SHA-256 `c368d3c965fda512b740477c1acb2463a98c26a86722faddffc5e6642a9cebb7`.
It contributes zero cells and authorizes no speed, quality, site, or submission
claim.

The preserved 15586 runtime did not drift. The llama-server hash, runtime
manifest hash, and all eight declared origin DSO canonical paths, sizes, and
hashes match exactly. The failure was a harness false negative: GNU `ldd`
indents dependency rows with a tab, but the runner required each SONAME at
column zero. It consequently failed on the first correct row,
`libllama-server-impl.so`.

The parser now permits leading whitespace before the SONAME and retains the
same canonical-path and closed-set checks. A regression test feeds the eight
real origin SONAME paths in tab-indented `ldd` form. The safe retry is a new
create-only campaign/root with the unchanged model, `15586e2d` binary,
runtime manifest, and eight-DSO closure. Do not rebuild or rebind the server:
that would introduce a new execution identity without fixing any runtime
problem.
