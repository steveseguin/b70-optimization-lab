# Flash-Next post-reboot recovery Stage A3 preregistration

Date: 2026-08-28
Status: frozen before execution

## Purpose

The user explicitly rebooted after the post-A11 host-memory recovery gate
required it. This fresh gate determines only whether the four-B70 host is safe
to proceed to a new known-good Flash-Next generation canary. It grants no
speed, quality, coverage, deployment, or matrix credit and cannot lower or
replace any captured result.

The previous post-reset Stage A/A2/B evidence paths are consumed and remain
immutable. This gate uses the new path
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reboot-recovery-qualification-20260828-stage-a3`
and fails closed if it already exists.

## Frozen identity and gates

- boot ID exactly `3ce525f4-de7f-46f6-a9df-3b56af7301cf`;
- host `MemAvailable` at least `110100480 KiB`;
- external `/dev/sda2` mounted read-write at `/mnt/usb-models`;
- local-NVMe checkpoint with exactly 131 weight shards;
- clean repository `main`, clean vLLM source at
  `1372c62d975c554f4b465c8299bc5f3295301ceb`, and clean tracked kernel source
  at `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- all staged runtime files must match
  `data/runtime-stage-padding-guard-loadable.sha256`;
- no conflicting runtime process, exactly four expected B70 identities, and
  less than 256 MiB reported memory on every card before active checks;
- one exact small compute check per card;
- one four-rank XCCL all-reduce with `FI_TCP_IFACE=lo` and
  `CCL_KVS_IFACE=lo`, with all four ranks returning exactly `4.0`;
- all twelve directed cross-card peer-access queries must pass;
- no new B70 reset/fatal event, host OOM, killed process, I/O error, or TTM
  failure in the bounded kernel-journal window.

The executable is
`tools/run-post-reboot-recovery-stage-a3.sh`. It takes no arguments, owns and
hashes its evidence, and stops on the first failed gate. A pass authorizes only
a separately frozen, fresh-path TP4/EP4/eager/MTP0 configured-512 generation
canary. It does not authorize a matrix launch by itself.
