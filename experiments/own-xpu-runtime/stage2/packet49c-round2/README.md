# Packet49c: all selected exact kernel improvements

Separate candidate derived from sealed packet49b at `192ee28f2`, plus only
packet51's winning route, HC gate/low and attention output/combine kernels.
Packet49b and packet51 remain unchanged. [Integration](INTEGRATION.md)
records production call coverage and exclusions.

Keep split32 QSA, p48b expert gate/up and down, unchanged 16-bit KV, weights,
23/25 target split, draft rank1, capacity4096, scheduling and memory guards.
All matching M=1 calls and each of the engine's two M=2 rows use the selected
kernels. Arithmetic remains `iq3-p49-split32-v1` and the [same packet49 CPU
oracle](oracle-binding.json) is hash-bound, never rebuilt or relaunched.

- [Coordinator commands and switch procedure](WINDOW.md).
- [CPU build/gates](CPU-BUILD.md).
- [Both-chain storage budget](ARTIFACT-RETENTION.md).
- [Independent kernel review](REVIEW-KERNELS.md).
- [Preparation record](../../../../notes/2026-10-17-own-runtime-packet49c.md).

CPU preparation is not device qualification. Packet51 operator gains are not
integrated model gains. Full-model windows must pass against the completed
shared oracle. The39.422 tok/s record stays unchanged until qualified matched
evidence exists. WS128 is the128-token record comparison; it does not satisfy
the separate512-token publication gate. No submission is part of this task.

Copied historical helper scripts are preserved implementation context, not
extra approved entry points. Use only the build, gates, seal and runbook
entry points listed here. Never rebuild or edit this packet after device
qualification begins; use a new packet for a later runtime change.
