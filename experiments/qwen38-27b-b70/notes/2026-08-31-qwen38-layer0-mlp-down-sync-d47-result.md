# Qwen3.8 layer-0 MLP down completion D47 result

D47 rejects a completion-only repair. Across four fresh processes, MLP input,
gate/up output, and activation each had one SHA-256 value. After an explicit
device-wide synchronization following the loaded M=71 down projection, its
complete output still had **four** hashes.

The full responses continued to first differ at generated token index 60.
Because the source activation was synchronized and exact before down and the
device was synchronized again before reading its result, this is arithmetic
nondeterminism in the selected oneDNN M=71 primitive, not an unobserved
completion race.

D48 tests only this down projection at the previously stable M=512 dispatch
shape, with explicit completion around the diagnostic boundary. An async event
barrier alone is not a sufficient production fix.
