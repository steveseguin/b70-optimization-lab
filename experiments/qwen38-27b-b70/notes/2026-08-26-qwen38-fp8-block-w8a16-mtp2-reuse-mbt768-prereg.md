# Qwen3.8 FP8 W8A16 MTP2-reuse MBT768 follow-up preregistration

The bounded MTP2-reuse screen passed sequential quality and measured
`83.646518 tok/s` for one cache-zero user, but its first c64 batch reached only
`737.190110 tok/s`. The server explicitly warned that
`max_num_batched_tokens=512` may be suboptimal with the additional draft token
slots. This follow-up tests that warning once; it does not reopen a broad
scheduler sweep.

## Frozen arm

Keep every identity and setting from the committed MTP2-reuse preregistration
except set `max_num_batched_tokens=768`. Use a fresh server process, the same
model/image/cache contents, MTP depth 2 through serial reuse of the one
publisher layer, max model length 256, 128 slots, and cache disabled.

Require `/health` and the seven exact sequential semantic cases before one
output-audited c64 batch. The batch must return 8,192 complete token IDs with
zero cached prompt tokens, no cross-base collision, and complete per-request
token identity.

The continuation hurdle is `900 tok/s` aggregate. A result below that closes
the scheduler warning as insufficient to recover the native-MTP1 aggregate
profile; do not test MBT1024. A result at or above 900 permits a separately
preregistered replication/MBT1024 comparison. No value from this screen is a
promoted service result or may be merged with MTP0/MTP1.
