# Capture implementation corrections

The original proposal remains preserved. Source inspection confirms that
`request_reset` redumps the old target before resetting. Inherited FINISH only
dumps the draft; it closes the last target evidence but does not redump target.
The bounded qualification therefore explicitly calls `state_hashes`/DUMP a second
time on the last arm before normal FINISH. The initial lifecycle mock invoked
the Writer on synthetic FINISH; its correction, old test and proof are retained
under `lineage/before-finish-test-correction`. This was not an actual Engine Host
test or a native protocol change.

The first actual NTFS pilot refused renameat2 no-replace publication before any
final file/seal. The exact errno was not captured in that first diagnostic.
Pilot b used exclusive hard-link publication and refused an old-FD link-count
check after the first successful link/unlink. Pilot c confirmed all four old
handles reported link-count2 while freshly reopened final files reported1.
Closing the original handle after verifying its identity, then reopening the
same final inode with O_NOFOLLOW and requiring single-link stable identity,
passed the actual NTFS pilot. Both failed attempts, partial files, source and
CPU receipts remain preserved; no model or GPU was involved.

Publication now links each durable partial to an exclusive final name, verifies
same inode and2links, unlinks only the partial name, and verifies a newly opened
final descriptor is the same single-link inode. Payload/index/state precede the
seal. A failure between link/unlink retains both names and is rejected as
incomplete. Final directory-fsync failure can leave a seal: a seal is necessary
but insufficient. Successful RPC and acknowledged RESET/FINISH/owner closure
remain mandatory, and any reported capture failure halts new requests.

These bundles retain all raw bytes. They reduce file-record pressure and
per-file archive overhead, not the approximately6.25GB full-suite byte budget.
Closed-bundle compression or another verified capacity recovery remains needed
when free external space cannot admit another suite plus reserve.
