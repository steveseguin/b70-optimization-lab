# Packet73: HC gates and second expert round

Five CPU-validated views are sealed and ready for coordinator-owned in-engine
screens. No GPU, CPU model, service or live queue ran during preparation.

| View | HC gates | Experts |
| --- | --- | --- |
| production | packet70 / packet60 | packet70 wide64 |
| hc-wide | two adjacent outputs share raw inputs; original SG32 trees | wide64 |
| experts2-a | production | wide64 plus deeper IQ2 packed-load pipeline |
| experts2-b | production | wide64 plus two-block IQ4 shared loads |
| combined | hc-wide | experts2-b |

All views share one engine binary, `iq3-p49-split32-v1`, unchanged model bytes,
full BF16 KV, draft-HC, batched rollback and 24/24 placement. C++ sources were
copied from packet70 with parent hashes retained. Existing packets and shared
screen code were not edited by this task.

GNU and Intel each pass 44 small operator cases twice, including 118,784 raw
FP32 chain checks and 3,456 tree checks per run. All accepted kernels use 128
configured GRFs and show no offline spill metadata or spill/fill instructions.
IQ4 static loads fall from 79 to 43. These are compiler and byte checks;
packet73's device quality, bandwidth and speed are still unmeasured.

The private copy of `screen/v4-lanes` passes 82 mock tests, including refused
teardown cleanup and lease release before reporting. Lane A has all four
candidates between production controls. Lane B resolves the best exact,
improving A candidate and runs it between fresh controls. Plans cover all
four possible B winners. Both queue proposals pass `lanequeue.py plan` in a
private temporary copy. No job was inserted into a live queue.

The build is about 303 MB, below the 1 GB cap. Compiler peak RSS is about
709 MiB, below the 8 GB limit. All preparation used nice 19 and the requested
CPU affinity. Large local build files remain available under their seals.

- [Coordinator commands and selection rule](WINDOW.md)
- [Offline counts and mechanisms](OCCUPANCY.md)
- [Final verification](evidence/final-validation.json)
- [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md)
- [Rejected paths](DO-NOT-REPEAT.md) and [retention](RETENTION.md)
- [Task note](../../../../notes/2026-10-17-own-runtime-packet73.md)
