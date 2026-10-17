# Packet60 constraints

- Do not claim that the full chain is elementwise or fits independent output
  tiles without cross-workgroup dependencies. Low and gate are full dot products.
- Do not implement an unbounded spinning grid barrier or assume all workgroups
  are resident. Do not duplicate the whole low projection per output tile.
- Do not repeat packet46's four-workgroup norm/serial upper tree or four serial
  gate projections per subgroup without new evidence.
- Preserve BF16 stores before activation and sigmoid and every split/tree edge.
- CPU primitive parity is not integrated-engine parity or GPU parity. There is
  no engine binary or screen seal until the requested topology is resolved.
- Keep packet56 and the packet49 oracle sealed and untouched.
