# Screen02 terminal text preservation

2026-09-14. A separate [screen02 exporter](../scripts/export-host-embedding-screen-02.py)
is prepared at SHA256 `33a09219eed8d5a77e6d8ba53288a21959f31a2d21bc7df5ce8c4c033b89d300`.
The packet11 exporter remains untouched. Its fixed packet/schema and old
component validator cannot export packet12 unchanged. The successor reuses
the frozen bounded stable-read/text-archive helper and packet12 receipt
validator, pins the sealed packet/client/contracts, and preserves exact UTF-8
text in a hashed gzip JSON archive. It never opens media/raw tensor/model bytes.

Root reported the client terminal with five passed control requests, followed
by generation2 refusal before construction. The new helper includes all
server-root lifecycle/placement/memory receipts, campaign and request text,
capture metadata, source/provenance/graphs, cold-admission proof sources and
postflight. Partial JSON stays in the archive even when it cannot be parsed.
Stable file identity and inventory checks refuse sealing concurrent changes.

The exporter reports `exported-terminal-text` separately from the owner's
terminal declaration and the original progress status. It validates saved
retirement, old-owner release and memory receipts where possible, while
recording validation errors without suppressing failure evidence. It does
not revalidate complete raw quality, complete lifecycle or retention.
For the actual generation2 refusal, all three memory receipts and unload/release
checks pass their saved-text contracts; `completed_new_component_proof=false`
and construction `passed=false` remain explicit.

Four [focused stdlib tests](../scripts/test-export-host-embedding-screen-02-stdlib.py)
passed, including these actual partial receipts, false passed-status refusal,
missing/running/malformed progress preservation for a root-declared failed
terminal client, and malformed partial receipt handling. No exporter invocation,
packet mutation, native import, endpoint/device/process query or Git mutation
was performed by the preparation agent. [Test result](../data/host-embedding-screen-02-export-stdlib-01.json).

After root review, root's exact one-shot command is:

```bash
python3 experiments/ltx25-b70/scripts/export-host-embedding-screen-02.py --terminal-status failed
```

The fixed new destination is `data/host-embedding-screen-02-export/` in this
lane. An existing destination is refused. Keep the original failed campaign
status; saved receipt validation does not establish a completed host component,
a host-mode clip or a speed result.
