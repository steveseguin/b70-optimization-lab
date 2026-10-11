# CPU-only r3 preparation corrections

The randomized checker found four unused uninitialized bytes at offset 4 in
card 1's result packet. The packet header is now zeroed once at initialization.

A manual review of sanitizer stderr then found alignment errors from packed
`Bound` pointer arrays. The old guard runner wrongly treated UBSan recovery exit
code 0 as a pass. Retained logs show that failure. The final layout uses natural
alignment, explicit initialized padding in Spec, and compile-time sizes.
The guard now uses `-fno-sanitize-recover=all` and rejects sanitizer error output.

The earlier full-prompt CPU oracle attempt was stopped gracefully (SIGTERM to
its identified CPU child) before rebuilding. It is not a passed gate. The old
proposed one-card source-reuse artifact is retained here only as an abandoned
idea. A fresh final-binary eight-token check is required by seal.py. No device
was involved in these corrections.
