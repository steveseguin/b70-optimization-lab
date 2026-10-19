# Packet169: shared CPU report contracts

The shared rehearsal now accepts declared standalone-micro schemas and derives
one-card bracket size from the packet. Packet58aq's six-view, 32-token split
passes the full `--report` command. Packet162 still passes with identical
deterministic receipt bytes. Packet166 has no contract and fails explicitly:
`missing report contract for standalone micro schema`.

## Scope and seal check

Host: `steve-b70s`. Starting main and fetched origin/main both resolved to
`512892c10a6b200b1a25f9a8de1a4486a32856d3`; `git pull --ff-only` was already
up to date. Existing unrelated work was left alone. Paths in the brief refer
to `experiments/own-xpu-runtime/ops/`, not a top-level ops directory.
Before committing, concurrent work advanced local and remote main together to
`5fc1f574527e53381bd79bc9e6912d13d5e9300e`. Git diff checks passed with command-local
`-c core.packedGitWindowSize=16m -c core.packedGitLimit=128m`; its default packfile
mapping exceeded the process's 2 GiB virtual-memory cap. No Git or host setting
was persisted.

Before editing, shared `rehearse_entry.py` SHA256 was
`8c31ddbbc9306368367761906a47274f57a5964792099151a5063c8b817bccac`.
Searched stage2 and ops for that hash and all references to
`ops/rehearse_entry.py`, then inspected READY/seal/pin manifests. The hash
occurred in packet155's entry-report evidence and packet58aq's report-adapter
evidence. No READY/seal/pin manifest pinned the shared source bytes. Packet58aq
READY pins its report-adapter evidence (which records the historical tool
hash), not the shared source file as a current input. Packet151/157 pins refer
to their private copies. Therefore the additive shared-file edit is allowed;
all frozen manifests and evidence remain unchanged.

No GPU, model/GGUF read, service, sudo, setting change, build, or live queue
mutation. Python runs used `nice -n 19`, `taskset -c 8-15,24-31`, `python3 -B`,
closed stdin and a 2 GiB address-space limit. Report children retain their
execution/data guard. CURRENT.md was already modified by other work and was
not touched; this task changes no operational lane state.

## Change

New `ops/rehearse_report_adapters.py` validates a bounded JSON contract naming
the packet-local analyzer and fixture generator, sample/analysis stream fields,
and expected decisions. The real entry parser, report and analyzer execute in
the guarded child. Missing and malformed declarations fail closed. The legacy
packet162 analyzer is recognized by its exact source hash and retains its
unchanged fixture and receipt shape. A changed analyzer must declare a contract.

One-card counts now follow actual views and prompts. Bracket cap/order can be
declared in proposal `plan.entry_rehearsal.window` or packet
`READY-FOR-DEVICE.json`. The declaration is checked against the packet, never
treated as admission. The six-arm publication-split timing fixture is adapted
from packet58aq's existing private synthetic adapter; real report code is not
replaced. Existing 64/128-token schemas keep their defaults.

The contract format, call signatures, limitations and commands are in
[ops/README.md](../experiments/own-xpu-runtime/ops/README.md).

## Validation

- Packet162 full shared `--report --json`: PASS, including native entry and
  packaging checks. Its existing regression test passes.
- Packet58aq split proposal full shared `--report --json`: PASS; 12 smoke
  requests and 72 bracket requests. Actual six-view analyzer/window/queue
  publication completes. No packet adapter or proposal changed.
- Packet166 report: FAIL CLOSED with the missing-contract message above.
  Its current packet has no report contract; no contract was invented for it.
- New alternate-schema fixture: PASS for both declared decisions. Malformed
  contract, missing contract, wrong stream type, wrong expected decision,
  bypassed analyzer, unsafe path and caught forbidden read all fail closed.
- Existing one-card regression suite: seven tests pass, including import
  failures, cold first-view policy, corruption, publication and I/O isolation.
- Combined regression command from ops/README: 17 tests pass.
- Before/after runs used the original source saved outside the repo, the same
  scratch path and fresh interpreters: identical returned report objects and
  all five packet162 files, 58 old one-card smoke files and 158 old five-view
  bracket files. The packet162 hashes are locked into the new regression test.

Synthetic timing and output values are test fixtures only. No speed, device
correctness, READY status or publication claim changes. Packet58aq's private
all-decision-tail suite remains required; the shared fixture exercises its
build-brief report branch. Unrecognized extra diagnostic streams still need
their own fixture schema.

Retained validation summary: [packet169-report-validation.json](../experiments/own-xpu-runtime/ops/packet169-report-validation.json).
