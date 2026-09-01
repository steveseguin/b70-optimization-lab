# Qwen3.8 Flash-Next FP8 A49 twoshots lossless-2K preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A49 is A48's exact path-only successor after A48 stopped before model load
because the supervisor's clean child environment omitted the host AER
baselines. A49 changes attempt `48`/port `19720` to attempt `49`/port `19721`
and explicitly forwards those two numeric values. It otherwise retains the
official FP8 model revision, clean vLLM/kernel/runtime identities, TP4/EP4,
MTP0, synchronous PLE-only placement, 2,304-token cap, compilation mode NONE,
size-1 `FULL_DECODE_ONLY` graph, public graph-aware oneCCL, `twoshots`, and the
complete A48 losslessness battery.

## Frozen packet

- derived launcher SHA-256:
  `9fd3e3b0de618207ec7adfbdc9db5800467b33c8176ae2b8e5a074b812ae36ce`;
- launcher SHA-256:
  `e9b8884bf1c338daeac991c739826f66860b73316b16bf21793ca4c4fd6da67c`;
- client SHA-256:
  `626ae56cc9a8fc4965604bea29f16ea817ca7b6ccea68c97164154ea3338dc36`;
- supervisor SHA-256:
  `d314ee9e1d4f227e4858fef8315fec9cf886e28eda81a5bbda797ea5f5f36e15`;
- privileged host wrapper SHA-256:
  `4b407d90a6e2a457a6ccbce6bd3a902c5437458461689a0fa64c4aea9f6ad311`;
- path-only rewrite helper SHA-256:
  `f12ce5c491b1b854c6235eefb827c214be1ea53aa0c9c8bf9f4bd3425e914080`;
- unchanged A48 runtime verifier SHA-256:
  `a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8`.

Generator validation must reproduce all four scripts byte-for-byte. The
normalized A48/A49 diff may contain only isolated identity fields and the two
explicit AER assignments in the supervisor's `env -i` block. A valid result
still requires recovery, the accepted semantic boundary, 16/16 repeat, all
three protected short hashes, an exact cache-zero 2K needle, two identical 2K
authority hashes, nonzero size-1 graph dispatch, exact `twoshots` receipt, and
clean guarded postflight. Any failure leaves all protected results unchanged.

No reboot or one-load-per-boot rule applies.
