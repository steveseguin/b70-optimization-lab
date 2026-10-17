# Packet 61: controller spin plus HC fusion

CPU preparation is complete. Packet61 combines packet56w's bounded 250 µs
mailbox/device spin and rank-0 queue profiling property with packet60's three
HC kernels per side. The target arithmetic, BF16 intermediates, full target
head, 91,392-row draft prefix, BF16 KV and packet49 oracle stay unchanged.
The engine handles both target HC sides and both serial M=2 rows.

The six copied HC source/fixture files are byte-identical to packet60. The
linked HC object is a hardlink to packet60's compiled object, preserving its
kernel order and math. `main.cpp` is packet60's integration plus packet56w's
rank-0 queue profiling condition. The controller header, device wait source
and spin helper are byte-identical to packet56w. See the
[source identity audit](evidence/source-identity.json).

Packet56x was unsealed when integration began at approximately 15:15 UTC.
Its later wait variants are not included. [The hook](wait-option.json) records
that decision and the files to substitute in a separately sealed candidate;
packet61 always uses packet56w waits. There is no unsealed environment toggle.

Passed checks:

- Host and SYCL builds; no device binary executed.
- Packet60 primitive and integrated fixture: 878,040 identical bytes.
- All 96 target fixtures and 24 generated tokens equal packet56.
- All 1,123 controller cases and five mailbox fault cases.
- All 31 chain, submission and output-boundary tests.
- Screen v1 and v3 CPU plans, full chain seal, oracle/prefix bindings and chain plan.

The build has 142,865,478 logical bytes (about 108 MiB allocated with hardlink
sharing), below the 400 MB limit. No GPU, model payload, service, sudo, power,
memory, swap, page-cache change, reboot or external submission was used.

This is a record candidate, not a measured packet61 result. The individual
48.831 and 48.873 tok/s screens motivate combination; their gains are not
assumed additive. The coordinator must run the screen and full chain before
claiming speed or device exactness.

- [Exact screen and full-chain commands](WINDOW.md).
- [Submission preparation and posting tools](SUBMISSION.md).
- [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
- [Build retention and reproduction](RETENTION.md).
- [Task note](../../../../notes/2026-10-17-own-runtime-packet61.md).

Only those documented entry points apply. Copied historical helper functions
are dependencies, not instructions to run additional experiments or rebuild a
sealed parent. The screen binary and full-chain device binary are identical:
`a8f58e768e9adca9fdee5a6e53d7ccccdba4939b0fd2098cc4f12b12ffe7e590`.
