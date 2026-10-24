# Expanded paired-state preservation

This pending helper covers only the 24 measured MTP `state.bundle` payloads
from the closed `gsq-quality-expanded-a` run. Each corresponding same-run
target-only bundle remains canonical. The fixed scope can recover
2,660,918,016 bytes without removing any unique target-state bytes.
Initial and warmup captures, all draft bytes, JSON, index and seal files remain.

`BINDING_SHA=None` deliberately refuses every operational phase and plan until
root supplies a successful independent expanded audit, exact physical index,
terminal and full-result hashes, plus explicit release authorization. All 48
measured physical payloads must appear uniquely in that index, with equal
full-bundle hashes and exact lengths for each pair. Same-model token parity
alone does not authorize release. Manual task quality remains a separate result.

The helper privately imports the frozen blank-draft implementation's no-follow
held-file hashing, inode/path checks and exclusive durable JSON writer. It
changes only fixed file scope and extent/hash authority. Each explicit batch
first verifies both full raw files, writes a durable restore map containing
original metadata, then closes the verification receipt. A separate release
rehashes both files, requires their verified identities, writes a durable
before-unlink receipt, rechecks both held paths, removes only the MTP payload,
fsyncs its directory and checks the retained canonical path. Failure halts;
existing phase receipts prevent a retry that could conceal partial work.

Root alone may run `--verify --batch N` and later `--release-verified --batch N`
for fixed batches 0 through 23 after the actual binding is independently
reviewed. The helper requires nice19, cores within8–15/24–31,4GiB address space,
expected USB device2050, and27GB plus64MiB free on the private NVMe metadata
filesystem. It creates no compressed archives or temporary payload copies.

Restore a released file by exclusively copying its retained target-only raw
bundle, checking the recorded length/SHA, and applying recorded original
mode/uid/gid/mtime. Existing per-capture metadata remains discoverable in place;
the durable restore maps identify the new physical location. After restoration,
inode/ctime naturally differ from the historical physical index.
