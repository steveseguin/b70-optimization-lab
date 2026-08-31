# Qwen3.8 Flash-Next FP8 partition/device interaction result

Date: 2026-08-31
Status: bounded component negative; static rank remapping closed

Independent review correctly rejected the original claim that one
`446.734-us` partition-1/device-1 Latin-square cell was transient: one
observation could not separate a stable interaction from timing noise. The
corrective A2 run repeated that exact mapping four times, paired in rotating
order with partition 1 on device 0 and partition 0 on device 1.

The suspect mapping measured `406.687 / 415.895 / 418.180 / 415.718 us`.
Relative to the slower matched control in each cycle, its penalties were
`-2.075 / -5.532 / +0.881 / +0.442%`. Zero of four cycles exceeded the frozen
5% gate, versus three required. Its median penalty was `-0.817%`. Every cell
was finite and internally repeatable, and each partition kept one exact output
hash across both physical devices and all cycles.

This closes a fixed partition/card interaction and static rank remapping as the
explanation for A28's changing late-rank pattern. It does not imply that
dynamic arrival skew is solved. No model server, full checkpoint load, reboot,
or protected result changed.

A1 is retained as a pre-tensor selector-orchestration negative. A2 binds the
full runtime stage, source heads, checkpoint shard hashes, complete commands,
and physical B70 BDF/UUID map. Its external manifest SHA-256 is
`06fbfe9ae4939fa7605a4544eba134e51ea291af3b53c53bfaed0823a100152d`.
