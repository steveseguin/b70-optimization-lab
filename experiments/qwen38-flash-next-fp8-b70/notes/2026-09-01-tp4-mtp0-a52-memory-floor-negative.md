# Qwen3.8 Flash-Next FP8 A52 memory-floor negative

Date: 2026-09-01
Status: bounded guard-policy negative; zero quality or speed credit

A52 loaded all 131 external checkpoint shards on every rank in
`583.19`-`583.62` seconds, initialized the 3,456-token cache, and completed
full-graph capture on all four ranks in 52 seconds. It therefore passed the
exact point where A51 stopped.

During the normal post-capture initialization interval, `MemAvailable` reached
`27,980,704 KiB`, only `19,296 KiB` below A52's `28,000,000 KiB` floor. The
one-second guard stopped and tore down the server cleanly. Disk-backed swap and
memory PSI remained zero. Local endpoint corrected count rose from `105` to
`142`, root-port count remained zero, and local NVMe read-sector movement
remained below the frozen 4 GiB limit. No fatal/recoverable link report, OOM,
device fault, endpoint, or inference request occurred.

The successful A44 endpoint took roughly another 99 seconds after its second
ordinary shared-memory busy notice to finish engine initialization. A52 was
stopped before that known interval elapsed. This is a second narrow
guard-policy negative, not evidence of resource distress or model failure.

Evidence is preserved under:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt52`

and the corresponding `-supervisor` directory.
