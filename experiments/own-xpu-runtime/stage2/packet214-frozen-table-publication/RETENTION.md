# P214 retained compiler inspection evidence

The large `native-symbols.log` files in the original compile attempt
`evidence/build-1792804549364710843` and corrected inspection attempt
`evidence/build-1792804797257672834` preserve the complete symbol inventories
used to investigate the missing standalone helper symbol. The latter attempt's
`native-sized-symbols.log` identifies the enclosing Engine function for targeted
disassembly. These logs document compiler inlining and distinguish the failed
inspection from a compilation failure.

The attempt receipts, final build receipt, authority tests and independent
review consume or bind these artifacts. Preserve both attempts: identical
inventories are evidence that the inspection correction used the same binary.
No duplicate is deleted or silently substituted.

The tracked logs can be restored from this packet's Git commit. The ignored
native object and ELF are locally retained and hash-bound by the receipts;
their compile recipe and exact source snapshots are retained here. Rebuilding
or inspecting a file is separate from permission to execute it. The public
entry remains disabled, and none of this evidence qualifies native execution.
