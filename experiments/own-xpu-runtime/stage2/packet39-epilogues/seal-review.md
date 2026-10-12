# Independent seal review

Harness agent read `seal.py` without executing a native binary. The seal checks
identical K0/G4 hashes, CPU fixture binary hashes, the host oracle result,
math source hashes, byte-exact SPIR-V embedding in the native executable,
assembly-to-codegen hash binding and the retained offline archive hash. It
includes the wrapper and assembly selection map among source/evidence hashes,
excluding only the generated self-referential receipt/hash-list files.

Findings sent to root before final sealing (all fixed and re-reviewed):

- Compare the native timing build's recorded source hash to current
  `timing.cpp`, and require successful CPU-only compilation. A binary hash
  alone does not bind a later-edited source file to that binary.
- Validate the harness review's binary hashes and reviewed source hashes,
  plus assembly selection/count agreement. Likewise verify identity-review
  source hashes rather than checking only its `device_executed` field.
- Verify required precision flags are actually present in the compile/link
  argv, not merely copied into a descriptive receipt field.
- Prefix version/Git helper child commands with nice19/ionice3 to follow the
  literal command rule as well as inherited scheduling priority.

I re-read the final `seal.py`: native source freshness, successful CPU-only
compilation, precision flags in the actual argv, identity/harness source hashes,
binary/count agreement and low-priority helper prefixes are now checked. All
four findings are closed. The assembly review's final rows4 scope clarification
was inspected; case counts and accept/reject decisions are unchanged, and its
updated hash is recorded in `harness-review.json`. Root owns execution of the
seal. No native device executable was run during this review.
