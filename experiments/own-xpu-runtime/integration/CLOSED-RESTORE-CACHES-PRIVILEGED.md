# Fixed privileged filesystem archival of closed compiler caches

The original unprivileged copy refused before creating its start receipt or
archive because 36 root-owned mode0600 cache files were unreadable. Those files
contain 582,155,334 bytes. All 8,766 candidate files are root-owned; their 1,908
immediate unlink parents are root-owned mode0755. Reading only the other files
would recover less than half the intended space and still cannot unlink them.
The original helpers, fixed metadata inventory and refusal evidence stay intact.

This additive preparation separates the normal-user coordinator from a fixed
privileged filesystem child. It neither changes original permissions/ownership
nor runs the existing whole archival helper with sudo. The child has only three
operation tokens: `copy`, `verify`, and `prune-root` with an integer0..17. It
accepts no paths, shell commands, service names, archive override or arbitrary
file list. The same SHA-pinned restore20..28 inventory fixes every source path.
Restore29, models, application metadata/logs, research results and directories
are excluded from deletion.

## Boundaries and ordering

The coordinator must run as uid1000 on nice19/helper cores. It alone reads the
three user-service configurations and exact external mount/reserve. Every child
call receives a new exclusive mode0600 admission file containing current service
proof, source/input hashes, mount/reserve proof, boot ID and monotonic timestamp.
The child refuses proofs older than120seconds or from another boot and checks
the exact restore29 configuration identity. This is a trusted coordinator's
fresh attestation, not an independent service query by root. The coordinator
checks services and mount again after every completed batch; a change halts
further work. Fifty GiB of external reserve remains mandatory.

The child uses isolated `/usr/bin/python3 -I -B` under explicit nice19/helper
placement. Its imports are the exact frozen archival primitives plus the system
standard library. It runs no subprocesses, native binaries, services or settings
commands. The coordinator passes the local sudo credential only through sudo's
stdin; it is absent from argv/environment/receipts. No child operation reads it.
All repository receipts and sibling recovery markers are written by the normal
user with explicit mode0600 and file/directory fsync. The privileged child writes
only the fixed new tar, its checksum sidecar and tiny external attempt markers;
results return as bounded structured stdout, never root-owned repository files.

The new archive is
`/mnt/usb-models/own-runtime-archives/closed-restore20-28-compiler-caches-20261023-privileged.tar`.
One copy contains all eighteen roots. Every source is hashed, copied through a
no-follow descriptor, fully read back by tar member and whole archive SHA256,
then rehashed at its original path. Original UID/GID/mode are recorded in the
copy map and tar and verified on readback. No original attributes are changed.

Prune is a separate operation. A privileged read-only verification of the
entire archive and all originals must pass first. The user then fsyncs the full
global restore map and all eighteen sibling incomplete-cache markers before
dispatching any unlink. Each root is a separate privileged batch: the child
again verifies the entire archive, holds its open descriptor, checks all recovery
markers and fixed source pins, hashes each original and checks its inode/stamp
immediately before relative unlink through a no-follow parent descriptor. Each
unlink parent is fsynced. Directories and unrelated files remain. Repeated full
archive reads trade extra sequential I/O for a simple independently checked
batch boundary; this is CPU/helper-core cleanup, not model work.

Each admission/attempt/result path is exclusive. No automatic retry, overwrite,
chmod/chown, directory removal, service restart or automatic restoration exists.
An uncertain Popen/communication timeout retains the child and coordinator;
there is no timeout kill or second launch. Root invocation is required to use
the coordinator CLI so that this exceptional retention path remains active.
CPU fixtures test that path but do not qualify an actual privileged timeout.

## Evidence and scope

Preparation uses tiny temporary files and mocked service/privilege calls only.
No real privileged copy, archive verification, cache-content read or unlink has
been executed by the implementation/review agents. The existing 4.26MB fixed
metadata inventory remains permanent admission evidence; do not regenerate it
from partially pruned trees. Source pins additionally bind these new modules,
tests and this document. A future root operation must review that exact closure.

All results use the new `closed-restore-caches-privileged-*` receipt namespace.
Small per-root batch receipts retain actual removed lists. A post-child service
or receipt failure preserves the child's completed filesystem result as failed
overall evidence; no next batch runs. Failure-receipt write errors are secondary
notes on the original error. The durable full maps cover a crash between unlink
and accounting. Successful filesystem recovery remains distinct from restoring
or starting an old application.

The source directories are not immutable. This assumes the trusted coordinator
does not concurrently reuse or reconfigure them; fixed stamps, fresh service
proofs and held descriptors reject observed drift but are not a hostile-user
security boundary or atomic filesystem transaction. Normal-user current service
proof cannot establish absence of every possible unrelated process. Historical
closure strengths and corroborating later drains remain those documented in
[the original retention record](CLOSED-RESTORE-CACHES.md).

## Root-owned operational invocation

Only after independent review, from the repository root, with the existing
external reserve and current restore29 services still admitted:

```bash
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/integration/archive_closed_restore_caches_privileged.py --plan
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/integration/archive_closed_restore_caches_privileged.py --copy-verify
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/integration/archive_closed_restore_caches_privileged.py --prune-verified
```

The plan is metadata-only, with no service/mount query or privilege request.
The other commands are proposals for the root coordinator, not executed
preparation steps. Restore only after verifying the tar and every member hash,
using a fresh separate directory and the exact recovery map; no helper performs
automatic extraction, permission changes, application restart or model launch.
