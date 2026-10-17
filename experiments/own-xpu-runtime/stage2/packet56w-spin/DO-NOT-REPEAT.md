# Packet56w scope

- Do not add attribution timing reads as an assumed optimization: the audit
  found a rank-0 queue profiling property difference, but no different wait
  loop. Only that queue property is carried over alongside the bounded spin.
- Do not spin indefinitely or reset the spin budget after every timed sleep.
- Do not change kernels, order, arithmetic, target fixtures or the packet49 oracle.
- Do not infer a speed result from CPU timings or packet57's instrumented arm.
- Do not modify or reseal packet56, packet57 or another worker's candidate.
- The coordinator screen decides whether to pursue the full chain.
