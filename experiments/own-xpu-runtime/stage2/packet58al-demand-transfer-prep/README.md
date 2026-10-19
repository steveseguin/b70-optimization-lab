# Packet58al: post-router demand-transfer preparation

CPU-only design, October 19, 2026. No build, model read, device execution,
service, settings change or queue write. Existing packets remain frozen.

The proposed packet58am is a private copy of **packet58ah chain b**, whose
one-card result is **31.66271941826957 tok/s**. Keep its full composition,
`iq3-p49-split32-v1`, 21,552,729,600-byte cache, target-only decoding and BF16
KV. The record is 128-token scoped; strict512 is false.

**Decision at preparation: do not build before a valid census decision.**
The ready-to-launch [build brief](briefs/build.md) contains the conditional
decision and all preparation gates. It authorizes preparing a new packet,
not running or queuing it. See [DECISION.md](DECISION.md) for every census
outcome and the latest observation in [evidence/poll.json](evidence/poll.json).

There are two important corrections to the starting hypothesis:

- Packet58ai's retained source and readiness identify **packet58ad/58ab**,
  not packet58ah's HC-wide / wide64+halfcache / other-fusion composition.
  Its ceiling is predecessor evidence unless the completed receipt proves
  otherwise. Do not relabel it a measurement of 31.663 tok/s.
- Zero-copy reads happen in the expert compute kernel on CCS. BCS can copy
  packed bytes to device staging while CCS computes resident slots. It
  cannot execute the zero-copy expert kernel. B70's single CCS offers no
  second concurrent expert-compute engine here.

[PLAN.md](PLAN.md) specifies source sites, arithmetic, events, buffer ownership,
memory and transfer accounting. [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) explains
why this differs from packet125 and the closed one-card arms. The source map
and real parent cold timing audit are retained under [evidence](evidence/).
The audit is read-only except for its explicit output inside this packet:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/audit.py </dev/null
```

No READY-for-device file belongs in this design packet. Packet58am must earn
its own READY last, after its own proofs, admission, analyzer replay and seals.
