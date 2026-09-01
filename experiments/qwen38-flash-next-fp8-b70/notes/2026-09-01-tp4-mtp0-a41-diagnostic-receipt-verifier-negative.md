# Qwen3.8 Flash-Next FP8 A41 diagnostic-receipt verifier negative

Date: 2026-09-01
Status: preserved healthy-endpoint, zero-request negative

A41 loaded all 131 shards from local NVMe in about 78 seconds, captured the
size-1 full-decode graph on all four ranks in 51 seconds, and became healthy.
Its client then failed closed before sending a request. One inherited
pre-request identity check expected
`diagnostics=full-decode-graph-public-oneccl`, while the server receipt and the
client's later structured identity both correctly included the preregistered
`-torch-trace` suffix.

The supervisor tore down the endpoint after client rc 1. No quality or speed
measurement occurred, protected results are unchanged, no model process or
listener remains, and no reboot is needed. A client-only correction was
statically proven to be a one-line diff, but the endpoint had already been
torn down, so it was not run. A42 carries that exact correction into a fresh
full-load successor.
