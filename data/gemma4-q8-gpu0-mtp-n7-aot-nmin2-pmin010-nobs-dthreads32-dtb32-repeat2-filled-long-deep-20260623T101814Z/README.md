# Incomplete Run

This was the `p-min=0.10` repeat control for the
`MTP_DRAFT_THREADS_BATCH=32` interaction sweep.

The server stalled during startup/readiness on GPU0 while loading the model and
was killed manually. It did not run the chat canary or benchmark, so it is not a
valid speed or quality result. The partial `server.stdout.log` is kept only as a
failed-control artifact for the sweep note.
