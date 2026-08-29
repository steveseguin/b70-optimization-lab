# Flash-Next post-reboot recovery Stage B1 preregistration

Date: 2026-08-28
Status: completed; passed

Result:
[`2026-08-28-post-reboot-recovery-stage-b1-result.md`](2026-08-28-post-reboot-recovery-stage-b1-result.md)

## Authority and purpose

The fresh post-reboot Stage A3 gate passed its source, storage, four-card
compute, peer-access, four-rank collective, and bounded-journal checks. Its
external `evidence.sha256` manifest has SHA-256
`72513c03f8c14744d61c1c6d14af385a8028d57eba7699b2e4b3d01f57786f53`.

Stage B1 is one known-good TP4/EP4/eager/MTP0 configured-512 generation
canary. It grants no speed, quality, coverage, deployment, or matrix credit.
It exists only to prove that the accepted Qwen target path can load, serve one
exact response, and shut down cleanly after the reboot.

## Frozen identity

- base launcher `tools/launch-tp4-ep4-eager-mtp0-512.sh`, SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- model revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` on local NVMe;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernel source
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, and sealed staged runtime
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager/graph-off, MTP0, configured length 512, 192-MiB fixed cache,
  one sequence, 64 batched tokens, and the accepted 12.25-GiB/rank selective
  UVA placement;
- fresh external run parent
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reboot-recovery-qualification-20260828-stage-b1`,
  attempt 29, port 19667, and fresh state/cache/compile/RPC paths;
- supervisor `tools/supervise-post-reboot-mtp0-512-canary-a1.sh`, SHA-256
  `fb409d63e7557b4554f9877645d23615a09b9e9134840dde3621a337f4ae7c60`;
- client `tools/run-post-reboot-mtp0-512-canary-a1.sh`, SHA-256
  `00347d3d3dc07873cc1661692f8ec611c1e8f7418976b4bc89310195a6ac41fd`.

## Exact pass rule

Send one cache-cold, non-thinking, temperature-zero request: `Reply with
exactly: OK`. Require HTTP 200, the exact served-model identity, normal stop,
normalized output `OK`, output SHA-256
`565339bc4d33d72817b583024112eb7f5cdf3e5eef0252d6ec1b9c9a94e12bb3`,
exact usage 17 prompt / 2 completion / 19 total, and zero cached and created
cache tokens.

The client may write the exact stop sentinel only after the receipt and all
gates are durable. Then require descendant-aware shutdown, no port, process,
compile-path, or RPC-path residue, four exact cards below 256 MiB, and no new
B70 reset/fatal event in the bounded journal. Any failure stops this program
without a retry. A complete pass authorizes only a separately preregistered
next matrix arm.
