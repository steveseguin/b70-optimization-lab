# Naming incident at the packet 113 launch (2026-10-08)

## What happened

The first qualification chunk of the 113 launch, `stream112-qeager-c000000`,
latched the server with a `FileExistsError` on
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/output/validation/stream112-qeager-c000000`.

Packet 113 reused packet 112's request names unchanged. That covers the
`stream112-` run-name prefix, `RUN_PREFIX`, `RUN_NAME_RE`, the qualification
names, and the capture and preview folder names. Only the server run directory
got a `-113-` name. The 112 run's captures were still under the shared
`output/validation/`, so the capture guard's exclusive create failed. The guard
did its job: it refused instead of overwriting. Nothing was lost, and the
coordinator archived the 112 outputs and relaunched.

This was a builder mistake. The 113 design kept the 112 names on purpose, so
that 112-shaped graphs would stay byte-identical and the qualification pins would
carry over. But it never checked the name spaces shared across launches:
`output/`, `output/validation/` and `requests/`, which live under the results
root rather than the run directory. The CPU tests and `--check-only` cannot see
this, because they create no outputs.

## Rule for packet 114 and later

1. **Packet-specific prefix on every name the server creates outside its run
   directory.** Use `stream114-…` for request and run names, qualification
   names, capture folders (`output/validation/<name>/`), preview folders
   (`output/<name>/`), text-node receipts, and anything under `requests/`.
   Receipts inside the run directory should use the same names.
   - The prefix appears in `stream_contract.RUN_PREFIX`, `integration.RUN_NAME_RE`,
     the client's `STREAM_DIR_RE`, the plan's setup and qualification names, and
     the graph pins.
   - Changing it therefore changes the plan SHA, so rebuild the plan.
   - Do not keep old names for graph-compatibility. Use a client flag for that
     instead.
2. **Launcher preflight that refuses on collision.** Before any device work,
   `serve-encoder.py` (or `encoder_runtime_common.prepare_start`) must list every
   name the setup and qualification requests will create. It must refuse to
   start if any of them already exists under `output/`, `output/validation/` or
   `requests/`. Also refuse if any entry there starts with the packet's stream
   prefix, since stream chunk names are not enumerable in advance.
   - Run this check in `--check-only` too, so the rehearsal catches it.
   - Add a CPU test with a fake root that holds a colliding folder.
3. Grep the packet for the previous packet's prefix before sealing. Only
   provenance files and comments may still mention it.
