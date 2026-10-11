# K1 attempt a: original coordinator evidence

The GEMV receipt passed 553/553. The non-GEMV process spent approximately 336 s
on device work, then printed only "ownership retained". No non-GEMV device
receipt or exception text was produced. process-state.txt records static device
cycles and no active VRAM at the observation, not proof of the original throw.

Code review proves an exception can be hidden: Device::compute stores fault_,
shutdown immediately refuses any fault, and Device's destructor parks before
the fixture's outer catch. The same chain-kernel JIT failure observed in W0 is
plausible, but unproven for this process. No external retained SYCL borrower was
found in the fixture. The repair is CPU-only and does not relabel this evidence.

Large-artifact retention: the coordinator's receipt.json is retained verbatim,
including its allocation-release ledger, as requested. Restore from this Git
commit; do not regenerate or compact it. build/k1a remains untouched.
