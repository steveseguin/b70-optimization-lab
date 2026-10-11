# Packet 23 W0 attempt a: the card's compiler rejects a kernel (2026-10-11 16:42 UTC)

The two-card canary stopped in 28 s, before any device work, with a clean exit and a
clean kernel log. The device compiler refused the program:

    error: Total size of kernel arguments exceeds limit! Total arguments size: 6036, limit: 2048
    in kernel: packet18::(anonymous namespace)::Chain::submit(...)::lambda(nd_item<1>)

The fused chain kernel captures about 6 KB by value; this device accepts at most
2,048 bytes of kernel arguments. A compile-and-link check on the host cannot see this:
the limit is enforced when the card's compiler builds the kernel. The non-GEMV fixture
program of K1 attempt a very likely hit the same error and parked silently while
unwinding (its GEMV half, which does not use this kernel, passed 553/553).
