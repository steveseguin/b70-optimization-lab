# Independent small-GEMV source review

Reviewer: large-GEMV implementation agent, independent of the small-GEMV author.
This review executed no device binary. Exact reviewed kernel hashes are in
`review-small-gemv.json`.

The concrete tuple members retain original format, arithmetic variant and
compile-time rows/columns. Each subgroup retains its row and split, virtual lane
indices and product order. SG32 widths 1,2,4,8,16 preserve the original tree.
Four-split members retain `(p0+p1)+(p2+p3)`. Every row has exactly one store from
lane zero and split zero. Shared scratch is local to a workgroup and initialized
by each of its four subgroups before the uniform barrier. Every workgroup enters
one uniform member branch; no barrier is hidden inside lane-divergent selection.

The pointer tuple is captured by value. Host dispatch selects a concrete tuple
instantiation. The device dispatch only selects a compile-time member body once
per workgroup, outside the row loop. There is no runtime format descriptor or
runtime format switch inside a GEMV loop. No kernel identity, write-race or
interpreter defect was found.

Integration findings were sent to the author: add explicit plan-order and
intervening-writer guards before moving siblings; extend the incumbent validation
mirror to F32 variant4 and miniature variant2; avoid one device readback per K2
repetition. The schedule and K2-copy findings have been fixed and independently re-reviewed.
The reviewed schedule rejects earlier followers, intervening source/output
writes, early reads of moved outputs and card-ownership crossings. K2 controls
now enqueue all siblings before waiting, then check bytes only at the first and
last repetitions. The scalar F32/mini incumbent validation mirror now extracts the original
packet8 constant/constant_split4 argument checks, including geometry, weight
alignment, extents and writable aliases. That source repair was independently
reviewed and closes the final integration finding. The kernel source verdict does not
substitute for fixture gates or device K1/K2.

The later scheduler guard refinement was also reviewed: readiness concerns only
`first.inputs[0]`, the actual input vector bound by `matrix(l)`. Plan metadata
also lists active/error controls, but dense GEMV and tuple kernels never consume
those pseudo-inputs. An intervening status write therefore cannot invalidate
input availability. Vector/output writer guards, output reader guards, exact
input-list matching and card/order checks remain enforced.

Final source re-review: `Member::host` is now explicitly enclosed by
`OWN_RT_HOST_ONLY`. Its arithmetic and the device member body are unchanged.
K2 now records `stage_count=times.size()` alongside each event. That count covers
all incumbent member stages, including split finalization, or the merged
submission's one stage. It changes receipt completeness checking only, with no
change to arithmetic, write ownership, timing boundaries or byte checks. Both
final files were reread, no new finding was identified, and their reviewed hashes
were refreshed. The main scheduler snippet hash remains unchanged. No compiler
or device executable was run for this audit.
