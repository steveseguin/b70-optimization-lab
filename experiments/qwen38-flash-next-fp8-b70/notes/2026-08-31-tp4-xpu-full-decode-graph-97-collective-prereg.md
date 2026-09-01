# Qwen3.8 Flash-Next TP4 97-collective graph preregistration

Date: 2026-08-31

Status: frozen before device execution

The public oneCCL `4ceafd1` build passed the exact single-collective graph gate.
This next component reproduces one target token's collective cardinality: 97
independent BF16 `[1,2560]` buffers are reduced in order inside one `XPUGraph`,
then the graph is replayed 100 times with every rank and buffer changed before
every replay.

Every one of the 9,700 outputs per rank must equal the exact CPU-computed sum.
Each replay's composite digest must be unique, all four ranks must complete,
and the process must exit zero. The frozen library is public oneCCL `4ceafd1`,
SHA-256
`43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`,
with the protected endpoint's threshold `4096` and direct PCIe transport.

Timing includes input copies, synchronization, CPU oracle work, and output
copies and is diagnostic only. A pass authorizes the selective-UVA PLE graph
gate, not a model endpoint or performance claim. No checkpoint is loaded and
no reboot is authorized.
