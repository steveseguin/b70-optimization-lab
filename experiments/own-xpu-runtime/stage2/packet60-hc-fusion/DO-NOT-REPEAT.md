# Packet60 constraints

- Do not claim that the full chain is elementwise or fits independent output
  tiles without cross-workgroup dependencies. Low and gate are full dot products.
- Do not implement an unbounded spinning grid barrier or assume all workgroups
  are resident. Do not duplicate the whole low projection per output tile.
- Do not repeat packet46's four-workgroup norm/serial upper tree or four serial
  gate projections per subgroup without new evidence.
- Preserve BF16 stores before activation and sigmoid and every split/tree edge.
- CPU parity and a diagnostic screen seal are not GPU parity or speed evidence.
  The coordinator accepted three kernels per side; do not reopen that decision.
- Keep packet56 and the packet49 oracle sealed and untouched.
