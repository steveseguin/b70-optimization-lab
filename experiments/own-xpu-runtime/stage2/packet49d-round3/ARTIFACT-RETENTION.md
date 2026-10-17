# Packet49d storage and retention

All new build and chain artifacts use
`/home/steve/own-xpu-runtime-results/packet49d-round3/build` on root.
No predecessor, oracle or protected-chain file is removed or changed.

| Item | Bytes |
| --- | ---: |
| Root free-space floor | 8,000,000,000 |
| Build peak and retained cap | 1,500,000,000 |
| Completed/superseded parent reserve | 0 |
| Completed oracle growth reserve | 0 |
| Early retained evidence cap | 128,000,000 |
| Model chain allowance | 5,818,804,480 |
| K2 temporary scratch peak | 2,500,000,000 |
| Required before an empty build and chain | 15,446,804,480 |

The owner explicitly retires the old 49b reserve for this preparation. 49c must
finish before 49d's coordinator windows. This is not permission to stop or clean
49c. The root check uses actual free space and does not credit external mounts.
Only `device-cards01-a` is registered; retries or additional chains are refused.

Compile one file at a time. Build admission enforces the 1.5GB cap, separately
from later device-chain output. Remove only this packet's regenerable objects
with `cleanup_objects.py` after retaining their identities. ASAN/UBSAN remain
enabled. Their exact executable bytes are retained as verified gzip archives
by `retain_sanitizers.py`, with original sizes, permissions and hashes recorded.
The seal verifies both compressed and original byte identities. Production GNU
and device binaries remain runnable. Archive restoration is possible with
`retain_sanitizers.py --restore` under the same CPU affinity and nice 19 policy.
No gate is replaced with compression or a tolerance.

Early scratch follows the inherited verified evidence-retention path; no model
output compression credit is needed for the model chain allowance. Missing
space refuses launch and preserves evidence. Run `storage_precheck.py` just
before each phase; `storage-precheck.json` records preparation's actual fit.

`rope.bf16` is a 4,194,304-byte frozen rotary fixture copied unchanged from 49c,
required by inherited build/seal paths. It is retained despite the 1MiB hygiene
review threshold, not a generated cache or downloaded weight. Restore the exact
bytes from `../packet49c-round2/rope.bf16` and verify the compiled-source hash.
Admitted input/fusion fixtures and the oracle are read-only symlinks to existing
inputs; they are neither duplicated nor edited.

Preparation observation: largest observed build 1,084,542,983 bytes; retained
build 521,796,014 bytes. Five sanitizer binaries (513,493,360 bytes) are retained
as 58,549,647 bytes of verified gzip data. See `storage-precheck.json` for the
18,853,928,960-byte root observation and 3,928,920,494-byte margin. Live admission
must repeat the check; this observation is not a future free-space guarantee.
