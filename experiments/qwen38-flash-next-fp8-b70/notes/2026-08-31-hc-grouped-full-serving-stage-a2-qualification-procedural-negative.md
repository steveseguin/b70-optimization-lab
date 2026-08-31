# Qwen3.8 Flash-Next grouped serving stage A2 qualification result

Date: 2026-08-31
Status: procedural negative before evidence or device work

The frozen A2 qualification exited with status 1 after about 2.73 seconds. It
created no result directory, started no device test, loaded no model weights,
and left all four B70s healthy and unowned. Static identity and stage closure
still pass in validation-only mode.

The cause is confined to the shell supervisor. `refuse_render_owners` used a
loop whose last command was a false `[[ ... ]] && fail` comparison in the
normal no-owner case. With `set -e`, the function therefore returned 1 and the
script stopped silently immediately before `mkdir`. This says nothing about
the A2 binaries or the HyperConnection grouped operation.

The original supervisor remains tracked at SHA-256
`870529a3e9c37599f77f38460795a2651e9a3ff4701c1a46d7dac73f8b8152a2`.
Its A3 successor derives the same qualification, adds an explicit successful
return to that guard, and uses a new no-clobber evidence directory. No retry,
endpoint, speed, quality, or promotion claim is attached to A2.

