# SPEED1 evidence retention

`before-speed1.jsonl.gz` preserves the preceding seal, gate records and changed
source bytes before this repair. Its hash and exact retained byte count are in
`before-retention.json`. Restore with the packet scratch-stream JSONL reader:
`file` entries name paths, consecutive `chunk` entries contain base64 bytes, and
`end` entries delimit each retained file. Do not restore into a live runtime tree.
This archive is larger than 1 MiB because it retains the original qualification
record needed to audit the narrowly scoped evidence rebind.

`speed1-snapshot-gates.json` at the packet root is larger than 1 MiB because it
retains all 24 terminal-owner full-state hash maps and launch timing records,
including the four deliberately failed exclusion comparisons. The 18 normal
mini executions are retained in `mini-cases.json`. Their compressed scratch
archives live alongside this directory under the exact paths in the receipts.
The mini gate can regenerate them using the recorded GNU host build only.

`writer-proof.json.gz` is a compressed, checked extent-by-extent audit from
retained production metadata. It admits no exclusions: plan input/output names
do not prove complete stores, and overwrite-before-read does not preserve old
bytes after terminal rollback. Its input, source and content hashes are in
`speed1-snapshot-inventory.json`. Device-produced result and incident paths were
read only. No weights were read by the metadata audits.
